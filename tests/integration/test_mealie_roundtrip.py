"""All public tools through installed Docker runtimes and real disposable Mealie."""

import os

import httpx2 as httpx
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.e2e.context import Context
from tests.e2e.scenarios import Scenario

pytestmark = pytest.mark.live


@pytest.mark.parametrize("mode,protocol", [("auto", "2026-07-28"), ("legacy", "2025-11-25")])
@pytest.mark.parametrize("transport", ["stdio", "http"])
async def test_all_tools_with_real_mealie_and_runtime_containers(transport, mode, protocol):
    if os.environ.get("MCP_E2E_ALLOW_WRITES") != "local-disposable":
        pytest.skip("Use uv run python -m tests.e2e.runner for the disposable Docker stack")
    context = Context.load()
    async with context.observer() as observer:
        if transport == "stdio":
            name = context.project + "-stdio-" + mode
            parameters = StdioServerParameters(
                command="docker",
                args=[
                    *context.compose,
                    "--profile",
                    "stdio",
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--pull",
                    "never",
                    "--name",
                    name,
                    "mcp-stdio",
                ],
                env=context.environment,
            )
            async with Client(parameters, mode=mode, read_timeout_seconds=60) as client:
                context.assert_stdio(name)
                await Scenario(context, client, observer, transport, protocol).run()
        else:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as http:
                assert (
                    await http.get(context.http_url.removesuffix("/mcp") + "/readyz")
                ).json() == {"status": "ok"}
                for token in (None, "fixture-wrong-personal-token-0123456789", context.api_key):
                    headers = {"Authorization": "Bearer " + token} if token else {}
                    assert (
                        await http.post(context.http_url, headers=headers, json={})
                    ).status_code == 401
                http.headers["Authorization"] = "Bearer " + context.bearer
                async with Client(
                    streamable_http_client(
                        context.http_url, http_client=http, max_sse_event_size=32 * 1024 * 1024
                    ),
                    mode=mode,
                    read_timeout_seconds=60,
                ) as client:
                    scenario = Scenario(context, client, observer, transport, protocol)
                    scenario.report["checks"].append("http_auth_401")
                    await scenario.run()
