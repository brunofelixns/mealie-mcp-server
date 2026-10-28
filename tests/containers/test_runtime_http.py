import asyncio
import json
import time

import httpx2 as httpx
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from tests.containers.conftest import docker, run_arguments, unique_name
from tests.support.fake_mealie import FakeMealie

TOKEN = "fixture-runtime-personal-" + "b" * 40


async def test_runtime_http_auth_health_and_stop45_without_source_mount(runtime_image):
    name = unique_name()
    with FakeMealie("categories.basic") as fake:
        args = run_arguments(
            runtime_image,
            "-d",
            "--name",
            name,
            "--env",
            f"MEALIE_BASE_URL={fake.docker_url}",
            "--env",
            "MEALIE_API_KEY=fixture-runtime-mealie-key",
            "--env",
            "MCP_AUTH_TOKEN=" + TOKEN,
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
                    assert len((await client.list_tools()).tools) == 78
                    assert not (
                        await client.call_tool("get_categories", {"page": 1, "perPage": 20})
                    ).is_error
            started = time.monotonic()
            docker("stop", "--time", "45", name)
            assert time.monotonic() - started < 45
            inspected = json.loads(docker("inspect", name).stdout)[0]
            assert inspected["State"]["ExitCode"] == 143
            assert inspected["HostConfig"]["ReadonlyRootfs"]
            assert not any(mount["Type"] == "bind" for mount in inspected["Mounts"])
            logs = docker("logs", name)
            assert "Mealie client closed" in logs.stderr
            assert TOKEN not in logs.stdout + logs.stderr
            assert "fixture-runtime-mealie-key" not in logs.stdout + logs.stderr
        finally:
            docker("rm", "--force", name, check=False)
