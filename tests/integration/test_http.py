import base64
import json
from contextlib import asynccontextmanager

import httpx2 as httpx
import pytest
from fastmcp import Client as FastMCPClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.http import create_http_app
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.registry import definitions
from tests.support.fake_mealie import FakeMealie
from tests.support.http_server import serve_http

TOKEN = "fixture-personal-" + "a" * 40
AUTH = {"Authorization": "Bearer " + TOKEN}


def settings_for(fake, **extra):
    return load_settings(
        {
            "MEALIE_BASE_URL": fake.server_url,
            "MEALIE_API_KEY": "fixture-mealie-key",
            "MCP_TRANSPORT": "http",
            "MCP_AUTH_TOKEN": TOKEN,
            **extra,
        }
    )


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("kind", ["official", "fastmcp"])
async def test_http_catalog_prompt_effects_and_separate_credentials(mode, kind):
    with FakeMealie("categories.basic") as fake:
        settings = settings_for(fake)
        async with serve_http(create_http_app(create_server(settings), settings)) as url:
            async with httpx.AsyncClient(headers=AUTH) as http:
                transport = streamable_http_client(url + "/mcp", http_client=http)
                client = (
                    Client(transport, mode=mode, read_timeout_seconds=20)
                    if kind == "official"
                    else FastMCPClient(url + "/mcp", auth=TOKEN, mode=mode)
                )
                async with client:
                    catalog = await client.list_tools()
                    tools = catalog.tools if kind == "official" else catalog
                    assert len(tools) == len(definitions())
                    assert tools[0].name == "get_recipes"
                    prompt = await client.get_prompt(
                        "weekly-meal-plan", {"preferences": "vegetarian"}
                    )
                    assert [message.role for message in prompt.messages] == ["assistant", "user"]
                    result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                    assert not result.is_error
        assert fake.authorization_headers == ["Bearer fixture-mealie-key"]


async def test_http_auth_guard_health_and_malformed_requests():
    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)
        async with serve_http(create_http_app(create_server(settings), settings)) as url:
            async with httpx.AsyncClient(base_url=url) as client:
                for path in ("/healthz", "/readyz"):
                    response = await client.get(path)
                    assert response.status_code == 200 and response.json() == {"status": "ok"}
                for headers in (
                    {},
                    {"Authorization": "Bearer wrong"},
                    {"Authorization": "Bearer fixture-mealie-key"},
                ):
                    response = await client.post("/mcp", headers=headers, json={})
                    assert response.status_code == 401
                    assert response.headers["www-authenticate"].startswith("Bearer")
                    assert TOKEN not in response.text
                for extra, status in (
                    ({"Host": "evil.test"}, 421),
                    ({"Origin": "https://evil.test"}, 403),
                ):
                    response = await client.post("/mcp", headers={**AUTH, **extra}, json={})
                    assert response.status_code == status
                response = await client.post(
                    "/mcp",
                    headers={
                        **AUTH,
                        "MCP-Protocol-Version": "2026-07-28",
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                    },
                    content=b"{",
                )
                assert response.status_code == 400
                assert (await client.get("/sse", headers=AUTH)).status_code == 404


async def test_readiness_tracks_lifespan_without_mealie_probe():
    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)
        app = create_http_app(create_server(settings), settings)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as http:
            assert (await http.get("/readyz")).status_code == 503
            async with app.router.lifespan_context(app):
                assert (await http.get("/readyz")).status_code == 200
            assert (await http.get("/readyz")).status_code == 503


async def test_two_protocol_clients_share_exactly_one_owned_pool():
    events = []
    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)

        @asynccontextmanager
        async def factory():
            async with MealieClient(settings) as client:
                events.append("opened")
                try:
                    yield client
                finally:
                    events.append("closed")

        server = create_server(settings, client_factory=factory)
        async with serve_http(create_http_app(server, settings)) as url:
            async with (
                FastMCPClient(url + "/mcp", auth=TOKEN, mode="legacy") as legacy,
                FastMCPClient(url + "/mcp", auth=TOKEN) as modern,
            ):
                assert (
                    len(await legacy.list_tools())
                    == len(await modern.list_tools())
                    == len(definitions())
                )
                assert events == ["opened"]
        assert events == ["opened", "closed"]


async def test_explicit_public_host_and_browser_origin_are_accepted():
    with FakeMealie("no_requests") as fake:
        settings = settings_for(
            fake,
            MCP_PUBLIC_URL="https://mcp.example.test",
            MCP_REQUIRE_HTTPS="true",
            MCP_ALLOWED_ORIGINS="https://client.example.test",
        )
        async with serve_http(create_http_app(create_server(settings), settings)) as url:
            async with httpx.AsyncClient(
                headers={
                    **AUTH,
                    "Host": "mcp.example.test",
                    "Origin": "https://client.example.test",
                }
            ) as http:
                async with Client(streamable_http_client(url + "/mcp", http_client=http)) as client:
                    assert len((await client.list_tools()).tools) == len(definitions())


async def test_http_body_limit_counts_chunked_bytes_and_rejects_declared_oversize():
    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)
        app = create_http_app(create_server(settings), settings)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as local,
        ):
            response = await local.post(
                "/mcp", headers={**AUTH, "Content-Length": str(32 * 1024 * 1024 + 1)}, content=b""
            )
            assert response.status_code == 413
        async with serve_http(app) as url, httpx.AsyncClient(base_url=url, timeout=30) as client:

            async def chunks():
                for _ in range(33):
                    yield b"x" * (1024 * 1024)

            response = await client.post("/mcp", headers=AUTH, content=chunks())
            assert response.status_code == 413


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_http_full_image_and_large_sse_result(mode):
    image = b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 - 8)
    encoded = base64.b64encode(image).decode()
    payload = "á" * (2 * 1024 * 1024)
    specs = [
        {
            "method": "PUT",
            "path": "/api/recipes/soup/image",
            "query": {},
            "body": {
                "fields": {"extension": "png"},
                "files": {
                    "image": {
                        "filename": "image.png",
                        "content_type": "application/octet-stream",
                        "base64": encoded,
                    }
                },
            },
            "response": {"image": "v1"},
        },
        {
            "method": "GET",
            "path": "/api/recipes/soup",
            "query": {},
            "body": None,
            "response": {"slug": "soup", "description": payload},
        },
    ]
    with FakeMealie(specs) as fake:
        settings = settings_for(fake)
        async with (
            serve_http(create_http_app(create_server(settings), settings)) as url,
            httpx.AsyncClient(headers=AUTH) as http,
        ):
            async with Client(
                streamable_http_client(
                    url + "/mcp", http_client=http, max_sse_event_size=32 * 1024 * 1024
                ),
                read_timeout_seconds=30,
                mode=mode,
            ) as client:
                result = await client.call_tool(
                    "set_recipe_image", {"slug": "soup", "imageBase64": encoded}
                )
                assert not result.is_error
                result = await client.call_tool("get_recipe_detailed", {"slug": "soup"})
                assert not result.is_error, result.content
                assert json.loads(result.content[0].text)["description"] == payload
