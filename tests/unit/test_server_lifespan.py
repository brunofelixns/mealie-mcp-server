from contextlib import asynccontextmanager

import httpx2 as httpx
from fastmcp import Client, FastMCP
from pydantic import BaseModel

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.contracts import ToolDefinition, register_contract_tool
from mealie_mcp_server.tools.helpers import success_result


def settings(host: str):
    return load_settings({"MEALIE_BASE_URL": host, "MEALIE_API_KEY": "fixture-key"})


def test_factory_does_not_open_the_mealie_client() -> None:
    calls = []

    @asynccontextmanager
    async def factory():
        calls.append("open")
        async with MealieClient(settings("http://mealie.test")) as client:
            yield client

    server = create_server(settings("http://mealie.test"), client_factory=factory)
    assert isinstance(server, FastMCP)
    assert calls == []


async def test_two_servers_do_not_share_state_and_close_their_own_clients() -> None:
    events = []
    servers = []

    class Empty(BaseModel):
        pass

    for host in ["http://first.test", "http://second.test"]:
        configuration = settings(host)

        @asynccontextmanager
        async def factory(configuration=configuration):
            events.append(("open", configuration.mealie_base_url))
            async with MealieClient(
                configuration,
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
            ) as client:
                yield client
            events.append(("close", configuration.mealie_base_url))

        server = create_server(configuration, client_factory=factory)

        async def probe(request, state):
            return success_result({"base": state.settings.mealie_base_url})

        register_contract_tool(
            server,
            ToolDefinition(
                "probe",
                "Read this server's state.",
                {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            ),
            Empty,
            probe,
        )
        servers.append(server)

    async with Client(servers[0]) as first, Client(servers[1]) as second:
        a = await first.call_tool("probe", {})
        b = await second.call_tool("probe", {})
        assert a.content[0].text == '{"base":"http://first.test"}'
        assert b.content[0].text == '{"base":"http://second.test"}'
    assert events.count(("open", "http://first.test")) == 1
    assert events.count(("close", "http://first.test")) == 1
    assert events.count(("open", "http://second.test")) == 1
    assert events.count(("close", "http://second.test")) == 1
