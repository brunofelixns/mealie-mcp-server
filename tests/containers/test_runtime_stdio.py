import json

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from mealie_mcp_server.tools.registry import definitions
from tests.containers.conftest import run_arguments
from tests.support.fake_mealie import FakeMealie


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_installed_runtime_stdio_without_source_mount_or_tty(runtime_image, mode):
    with FakeMealie("categories.basic") as fake:
        args = run_arguments(
            runtime_image,
            "-i",
            "--env",
            f"MEALIE_BASE_URL={fake.docker_url}",
            "--env",
            "MEALIE_API_KEY=fixture-runtime-mealie-key",
            "--env",
            "MCP_AUTH_TOKEN_FILE=/missing/ignored-in-stdio",
        )
        async with Client(
            StdioServerParameters(command="docker", args=args), mode=mode, read_timeout_seconds=40
        ) as client:
            assert len((await client.list_tools()).tools) == len(definitions())
            assert len((await client.get_prompt("weekly-meal-plan")).messages) == 2
            result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
            assert not result.is_error
            assert json.loads(result.content[0].text)["total"] == 1
        assert fake.authorization_headers == ["Bearer fixture-runtime-mealie-key"]
