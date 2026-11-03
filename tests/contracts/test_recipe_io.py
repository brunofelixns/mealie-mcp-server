"""Positive/rejection evidence for every native recipe IO MCP handler."""

import base64
import json
from io import BytesIO
from zipfile import ZipFile

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server

ARCHIVE = BytesIO()
with ZipFile(ARCHIVE, "w") as file:
    file.writestr("recipe.json", '{"name":"Soup"}')

CASES = [
    (
        "upload_recipe_asset",
        {
            "slug": "soup",
            "name": "Guide",
            "icon": "mdi-file",
            "extension": "pdf",
            "fileBase64": "JVBERg==",
        },
        "POST",
        "/api/recipes/soup/assets",
        {"name": "Guide", "icon": "mdi-file", "fileName": "guide.pdf"},
    ),
    (
        "create_recipe_asset_from_url",
        {"slug": "soup", "url": "https://recipes.test/image.png"},
        "POST",
        "/api/recipes/soup/assets/url",
        {"name": "image", "icon": "mdi-file-image", "fileName": "image.png"},
    ),
    (
        "import_recipe_from_url",
        {"url": "https://recipes.test/soup", "includeTags": False},
        "POST",
        "/api/recipes/create/url",
        "soup",
    ),
    (
        "import_recipe_from_html_or_json",
        {"data": '{"name":"Soup"}', "url": None, "includeCategories": False},
        "POST",
        "/api/recipes/create/html-or-json",
        "soup",
    ),
    (
        "import_recipe_from_zip",
        {"archiveBase64": base64.b64encode(ARCHIVE.getvalue()).decode()},
        "POST",
        "/api/recipes/create/zip",
        "soup",
    ),
    (
        "get_recipe_export_formats",
        {},
        "GET",
        "/api/recipes/exports",
        {"json": ["json"], "zip": ["zip"], "provider": True},
    ),
    (
        "export_recipe",
        {"slug": "soup", "templateName": "json"},
        "GET",
        "/api/recipes/soup/exports",
        {"filename": "soup.json", "mediaType": "application/json", "size": 2, "dataBase64": "e30="},
    ),
]


@pytest.mark.parametrize(
    "name,arguments,method,path,expected", CASES, ids=[case[0] for case in CASES]
)
async def test_recipe_io_mcp_positive(name, arguments, method, path, expected):
    calls = []

    def respond(request):
        calls.append(request)
        assert request.method == method and request.url.path == path
        assert request.headers["authorization"] == "Bearer fixture"
        if name == "export_recipe":
            assert request.url.params["template_name"] == "json"
            return httpx.Response(
                200,
                content=b"{}",
                headers={
                    "content-type": "application/json",
                    "content-disposition": 'attachment; filename="soup.json"',
                },
            )
        if name in {
            "create_recipe_asset_from_url",
            "import_recipe_from_url",
            "import_recipe_from_html_or_json",
        }:
            assert json.loads(request.content) == {
                key: value for key, value in arguments.items() if key != "slug"
            }
        if name == "import_recipe_from_zip":
            assert b'name="archive"' in request.content
        return httpx.Response(200, json=expected)

    settings = load_settings(
        {"MEALIE_BASE_URL": "https://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(respond)),
    )
    async with Client(server) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)
    assert not result.is_error
    assert json.loads(result.content[0].text) == expected
    assert len(calls) == 1


@pytest.mark.parametrize(
    "name,arguments,method,path,expected", CASES, ids=[case[0] for case in CASES]
)
async def test_recipe_io_mcp_rejection(name, arguments, method, path, expected):
    def respond(_):
        pytest.fail("Rejected arguments reached provider")

    settings = load_settings(
        {"MEALIE_BASE_URL": "https://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(respond)),
    )
    async with Client(server) as client:
        result = await client.call_tool(
            name, {**arguments, "unexpected": True}, raise_on_error=False
        )
    assert result.is_error


@pytest.mark.parametrize(
    "name,arguments,method,path,expected", CASES[:5], ids=[case[0] for case in CASES[:5]]
)
async def test_recipe_io_mcp_write_errors_are_confidential_without_retry(
    name, arguments, method, path, expected
):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(403, text="private recipe body https://files.test?signature=secret")

    settings = load_settings(
        {"MEALIE_BASE_URL": "https://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(respond)),
    )
    async with Client(server) as client:
        result = await client.call_tool(name, arguments, raise_on_error=False)
    assert result.is_error
    assert "403" in result.content[0].text and "private" not in result.content[0].text
    assert "signature" not in result.content[0].text and len(calls) == 1
