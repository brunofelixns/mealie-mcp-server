"""Real TCP disconnect after PATCH must not replay or skip verification/recovery."""

import asyncio
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.http import create_http_app
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server
from tests.integration.test_http import AUTH, settings_for
from tests.support.contracts import FIXTURES, load_cases
from tests.support.fake_mealie import FakeMealie
from tests.support.http_server import serve_http


@pytest.mark.parametrize("family", ["recipe_ingredients", "recipe_instructions"])
async def test_tcp_disconnect_finishes_verification_and_rollback_without_replay(family):
    case = next(case for case in load_cases(family) if case.scenario.endswith(".rollback"))
    requests = json.loads((FIXTURES / "scenarios.json").read_text())[case.scenario]["requests"]
    observed = []
    entered, release, restored = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handle(request):
        index = len(observed)
        assert index < len(requests), "Unexpected replay"
        expected = requests[index]
        assert request.method == expected["method"]
        assert request.url.path == expected["path"]
        assert (json.loads(request.content) if request.content else None) == expected.get("body")
        observed.append(request.method)
        if request.method == "PATCH" and observed.count("PATCH") == 1:
            entered.set()
            await release.wait()
        if len(observed) == len(requests):
            restored.set()
        return httpx.Response(expected.get("status", 200), json=expected.get("response"))

    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)
        server = create_server(
            settings,
            client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
        )
        async with (
            serve_http(create_http_app(server, settings)) as url,
            httpx.AsyncClient(timeout=20) as http,
        ):
            task = asyncio.create_task(
                http.post(
                    url + "/mcp",
                    headers={
                        **AUTH,
                        "MCP-Protocol-Version": "2026-07-28",
                        "Mcp-Method": "tools/call",
                        "Mcp-Name": case.tool,
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": case.tool,
                            "arguments": case.arguments,
                            "_meta": {
                                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                                "io.modelcontextprotocol/clientCapabilities": {},
                            },
                        },
                    },
                )
            )
            try:
                waiting = asyncio.create_task(entered.wait())
                await asyncio.wait([task, waiting], timeout=3, return_when=asyncio.FIRST_COMPLETED)
                if task.done():
                    response = task.result()
                    pytest.fail(
                        f"Request ended before PATCH: {response.status_code} {response.text}"
                    )
                assert waiting.done(), "PATCH not reached"
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
                if not waiting.done():
                    waiting.cancel()
                    await asyncio.gather(waiting, return_exceptions=True)
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            await asyncio.wait_for(restored.wait(), 3)
        assert observed == [request["method"] for request in requests]
        assert observed.count("PATCH") == 2
