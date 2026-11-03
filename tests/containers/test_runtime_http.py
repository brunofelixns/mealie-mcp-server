import asyncio
import base64
import json
import time

import httpx2 as httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from mealie_mcp_server.tools.registry import definitions
from tests.containers.conftest import AUTH_TOKEN as TOKEN
from tests.containers.conftest import docker, run_arguments, unique_name
from tests.support.contracts import FIXTURES
from tests.support.fake_mealie import FakeMealie


async def test_runtime_http_auth_health_and_stop45_without_source_mount(
    runtime_image, secret_volume
):
    name = unique_name()
    image = b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024 - 8)
    encoded = base64.b64encode(image).decode()
    specs = json.loads(await asyncio.to_thread((FIXTURES / "scenarios.json").read_text))[
        "categories.basic"
    ]["requests"]
    specs.append(
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
        }
    )
    with FakeMealie(specs) as fake:
        args = run_arguments(
            runtime_image,
            "-d",
            "--name",
            name,
            "--env",
            f"MEALIE_BASE_URL={fake.docker_url}",
            "--env",
            "MEALIE_API_KEY_FILE=/run/secrets/mealie_api_key",
            "--env",
            "MCP_AUTH_TOKEN_FILE=/run/secrets/mcp_auth_token",
            "--mount",
            f"type=volume,src={secret_volume},dst=/run/secrets,readonly",
            "--env",
            "MCP_ALLOWED_HOSTS=" + name,
            "--env",
            "MEALIE_MCP_DEBUG=true",
        )
        # Keep the stopped container briefly to inspect its exit code and logs.
        args.remove("--rm")
        try:
            docker(*args, "--transport", "http", "--host", "0.0.0.0")
            async with httpx.AsyncClient(base_url=f"http://{name}:8000", timeout=40) as http:
                async with asyncio.timeout(60):
                    while True:
                        try:
                            if (await http.get("/readyz")).status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        await asyncio.sleep(0.05)
                assert (await http.get("/healthz")).json() == {"status": "ok"}
                assert (await http.post("/mcp", json={})).status_code == 401
                http.headers["Authorization"] = "Bearer " + TOKEN
                async with Client(
                    streamable_http_client(f"http://{name}:8000/mcp", http_client=http),
                    read_timeout_seconds=40,
                ) as client:
                    assert len((await client.list_tools()).tools) == len(definitions())
                    assert not (
                        await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                    ).is_error
                    assert not (
                        await client.call_tool(
                            "set_recipe_image", {"slug": "soup", "imageBase64": encoded}
                        )
                    ).is_error
            started = time.monotonic()
            docker("stop", "--time", "45", name)
            assert time.monotonic() - started < 45
            inspected = json.loads(docker("inspect", name).stdout)[0]
            assert inspected["State"]["ExitCode"] == 143
            assert inspected["HostConfig"]["ReadonlyRootfs"]
            assert not any(mount["Type"] == "bind" for mount in inspected["Mounts"])
            assert not any(
                value.startswith(("MEALIE_API_KEY=", "MCP_AUTH_TOKEN="))
                for value in inspected["Config"]["Env"]
            )
            assert all(
                not mount["RW"]
                for mount in inspected["Mounts"]
                if mount["Destination"] == "/run/secrets"
            )
            logs = docker("logs", name)
            assert "Mealie client closed" in logs.stderr
            assert TOKEN not in logs.stdout + logs.stderr
            assert "fixture-runtime-mealie-key" not in logs.stdout + logs.stderr
        finally:
            docker("rm", "--force", name, check=False)
