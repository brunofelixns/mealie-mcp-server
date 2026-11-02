import asyncio

import httpx2 as httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.skills import SkillsClientExtension

from tests.containers.conftest import AUTH_TOKEN, docker, run_arguments, unique_name
from tests.support.fake_mealie import FakeMealie
from tests.support.skills import assert_skill_bytes


@pytest.mark.parametrize("transport", ["stdio", "http"])
async def test_installed_skills_without_checkout_or_source_mount(runtime_image, transport):
    with FakeMealie("no_requests") as fake:
        args = run_arguments(
            runtime_image,
            "-i" if transport == "stdio" else "-d",
            "--env",
            f"MEALIE_BASE_URL={fake.docker_url}",
            "--env",
            "MEALIE_API_KEY=fixture-runtime-mealie-key",
        )
        if transport == "stdio":
            async with Client(
                StdioTransport(command="docker", args=args),
                extensions=[SkillsClientExtension()],
                timeout=45,
            ) as client:
                await assert_skill_bytes(client)
        else:
            name = unique_name()
            image = args.pop()
            args.extend(
                [
                    "--name",
                    name,
                    "--env",
                    "MCP_AUTH_TOKEN=" + AUTH_TOKEN,
                    "--env",
                    "MCP_ALLOWED_HOSTS=" + name,
                    image,
                ]
            )
            docker(*args, "--transport", "http", "--host", "0.0.0.0")
            try:
                url = f"http://{name}:8000"
                async with httpx.AsyncClient(timeout=5) as http:
                    async with asyncio.timeout(60):
                        while True:
                            try:
                                if (await http.get(url + "/readyz")).status_code == 200:
                                    break
                            except httpx.ConnectError:
                                pass
                            await asyncio.sleep(0.05)
                async with Client(
                    url + "/mcp",
                    auth=AUTH_TOKEN,
                    extensions=[SkillsClientExtension()],
                    timeout=45,
                ) as client:
                    await assert_skill_bytes(client)
            finally:
                docker("rm", "--force", name, check=False)
        assert fake.recorded_requests == []
