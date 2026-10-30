"""Run the portable deployment bundle against the installed runtime image."""

import json
import os
from pathlib import Path

import httpx2 as httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.containers.conftest import AUTH_TOKEN, MEALIE_KEY, docker, unique_name
from tests.support.fake_mealie import FakeMealie

COMPOSE = Path(__file__).resolve().parents[2] / "docker/compose.yaml"


def deployment(tmp_path, image, fake, *, http):
    project = unique_name()
    hostname = project + "-mealie-mcp-1"
    environment = tmp_path / ".env"
    environment.write_text(
        f"MEALIE_MCP_IMAGE={image}\n"
        f"MEALIE_BASE_URL={fake.docker_url}\n"
        f"MEALIE_API_KEY={MEALIE_KEY}\n"
        f"MCP_AUTH_TOKEN={AUTH_TOKEN if http else ''}\n"
        f"MCP_PUBLIC_URL=https://{hostname}/mcp\n"
        "MCP_PUBLISHED_PORT=0\n"
    )
    override = tmp_path / "network.json"
    override.write_text(
        json.dumps(
            {
                # ARM under QEMU starts in ~33s; short retries must not declare it
                # unhealthy before startup. The Compose wait remains bounded at 60s.
                "services": {
                    "mealie-mcp": {
                        "healthcheck": {
                            "interval": "2s",
                            "start_period": "60s",
                            "timeout": "10s",
                        }
                    }
                },
                "networks": {
                    "default": {
                        "external": True,
                        "name": os.environ.get(
                            "MCP_TEST_NETWORK", "mealie-mcp-development_default"
                        ),
                    }
                },
            }
        )
    )
    return [
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(environment),
        "-f",
        str(COMPOSE),
        "-f",
        str(override),
    ], hostname


async def test_portable_compose_http_auth_and_provider_credentials(runtime_image, tmp_path):
    with FakeMealie("categories.basic") as fake:
        compose, hostname = deployment(tmp_path, runtime_image, fake, http=True)
        try:
            docker(
                *compose,
                "up",
                "--detach",
                "--wait",
                "--wait-timeout",
                "60",
                "--pull",
                "never",
                "--no-build",
                "mealie-mcp",
            )
            # Match the installed-runtime tests: MCP initialization under QEMU
            # can exceed httpx's default five-second read timeout.
            async with httpx.AsyncClient(base_url=f"http://{hostname}:8000", timeout=40) as http:
                assert (await http.get("/readyz")).json() == {"status": "ok"}
                assert (await http.post("/mcp", json={})).status_code == 401
                http.headers["Authorization"] = "Bearer " + AUTH_TOKEN
                async with Client(
                    streamable_http_client(f"http://{hostname}:8000/mcp", http_client=http),
                    read_timeout_seconds=40,
                ) as client:
                    assert len((await client.list_tools()).tools) == 78
                    result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                    assert not result.is_error
                    assert json.loads(result.content[0].text)["total"] == 1
            assert fake.authorization_headers == ["Bearer " + MEALIE_KEY]
            inspected = json.loads(docker("inspect", hostname).stdout)[0]
            assert inspected["HostConfig"]["ReadonlyRootfs"]
            assert inspected["Config"]["User"] == "10001:10001"
        finally:
            docker(*compose, "down", "--timeout", "45", check=False)


async def test_portable_compose_stdio_without_http_token(runtime_image, tmp_path):
    with FakeMealie("categories.basic") as fake:
        compose, _ = deployment(tmp_path, runtime_image, fake, http=False)
        try:
            async with Client(
                StdioServerParameters(
                    command="docker",
                    args=[
                        *compose,
                        "--profile",
                        "stdio",
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "--pull",
                        "never",
                        "stdio",
                    ],
                ),
                read_timeout_seconds=40,
            ) as client:
                assert len((await client.list_tools()).tools) == 78
                assert len((await client.get_prompt("weekly-meal-plan")).messages) == 2
                assert not (
                    await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                ).is_error
            assert fake.authorization_headers == ["Bearer " + MEALIE_KEY]
        finally:
            docker(*compose, "down", "--timeout", "45", check=False)
