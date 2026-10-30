"""Run the portable deployment bundle against the installed runtime image."""

import json
import os
import platform
import shutil
from pathlib import Path

import httpx2 as httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.containers.conftest import AUTH_TOKEN, MEALIE_KEY, docker, unique_name
from tests.support.fake_mealie import FakeMealie

COMPOSE = Path(__file__).resolve().parents[2] / "docker/compose.yaml"
STDIO_COMPOSE = COMPOSE.with_name("compose.stdio.yaml")
EMULATED_ARM = os.environ.get("MCP_TEST_ARCH") == "arm64" and platform.machine() not in {
    "aarch64",
    "arm64",
}
STARTUP_TIMEOUT = 120 if EMULATED_ARM else 60
READ_TIMEOUT = 90 if EMULATED_ARM else 40


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
    # env_file is resolved beside the Compose file, also after copying the bundle
    # to another machine. Exercise that portable layout with an isolated .env.
    source = COMPOSE if http else STDIO_COMPOSE
    compose_file = tmp_path / source.name
    shutil.copyfile(source, compose_file)
    override = tmp_path / "network.json"
    override.write_text(
        json.dumps(
            {
                # The previous Compose also takes ~59s under current QEMU load.
                # Allow its next health probe; native budgets remain unchanged.
                "services": {
                    "mealie-mcp": {
                        "healthcheck": {
                            "interval": "2s",
                            "start_period": f"{STARTUP_TIMEOUT}s",
                            "timeout": "10s",
                        }
                    }
                }
                if http
                else {},
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
        str(compose_file),
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
                str(STARTUP_TIMEOUT),
                "--pull",
                "never",
                "--no-build",
                "mealie-mcp",
                timeout=STARTUP_TIMEOUT + 15,
            )
            # Match the installed-runtime tests: MCP initialization under QEMU
            # can exceed httpx's default five-second read timeout.
            async with httpx.AsyncClient(
                base_url=f"http://{hostname}:8000", timeout=READ_TIMEOUT
            ) as http:
                assert (await http.get("/readyz")).json() == {"status": "ok"}
                assert (await http.post("/mcp", json={})).status_code == 401
                http.headers["Authorization"] = "Bearer " + AUTH_TOKEN
                async with Client(
                    streamable_http_client(f"http://{hostname}:8000/mcp", http_client=http),
                    read_timeout_seconds=READ_TIMEOUT,
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
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "--pull",
                        "never",
                        "stdio",
                    ],
                ),
                read_timeout_seconds=READ_TIMEOUT,
            ) as client:
                assert len((await client.list_tools()).tools) == 78
                assert len((await client.get_prompt("weekly-meal-plan")).messages) == 2
                assert not (
                    await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                ).is_error
            assert fake.authorization_headers == ["Bearer " + MEALIE_KEY]
        finally:
            docker(*compose, "down", "--timeout", "45", check=False)


def test_portable_compose_files_each_expose_only_the_selected_transport(runtime_image, tmp_path):
    with FakeMealie([]) as fake:
        for http in (True, False):
            directory = tmp_path / ("http" if http else "stdio")
            directory.mkdir()
            compose, _ = deployment(directory, runtime_image, fake, http=http)
            config = json.loads(docker(*compose, "config", "--format", "json").stdout)
            service_name = "mealie-mcp" if http else "stdio"
            assert set(config["services"]) == {service_name}
            service = config["services"][service_name]
            assert not service.get("profiles")
            assert service["read_only"] is True
            assert service["cap_drop"] == ["ALL"]
            assert service["pids_limit"] == 256
            if not http:
                assert not service.get("ports")
                assert not service.get("healthcheck")
                assert "MCP_AUTH_TOKEN" not in service["environment"]
                assert not service.get("restart")
