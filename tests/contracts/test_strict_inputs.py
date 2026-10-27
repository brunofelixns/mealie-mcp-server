from typing import Any

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.contracts import ToolDefinition, register_contract_tool
from mealie_mcp_server.tools.helpers import success_result

SCHEMA = {
    "type": "object",
    "properties": {
        "nested": {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        "open": {"type": "object", "additionalProperties": True},
    },
    "required": ["nested"],
    "additionalProperties": False,
}


class Nested(ToolInput):
    value: int


class Input(ToolInput):
    nested: Nested
    open: dict[str, Any] | None = None


@pytest.mark.parametrize(
    "arguments",
    [
        {"nested": {"value": 1, "unexpected": True}},
        {"nested": {"value": 1}, "unexpected": True},
        {"nested": {"value": "1"}},
        {"nested": {"value": True}},
        {"nested": {}},
        {},
    ],
)
async def test_unknown_fields_and_coercions_do_not_reach_upstream(arguments) -> None:
    calls = []
    configuration = load_settings(
        {"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"}
    )

    async def handle_http(request):
        calls.append(request)
        return httpx.Response(200, json={})

    server = create_server(
        configuration,
        client_factory=lambda: MealieClient(
            configuration, transport=httpx.MockTransport(handle_http)
        ),
    )

    async def handler(request, state):
        await state.client.request("POST", "/api/recipes", json=provided_fields(request))
        return success_result({})

    register_contract_tool(
        server, ToolDefinition("probe", "Strict input probe.", SCHEMA), Input, handler
    )
    async with Client(server) as client:
        result = await client.call_tool("probe", arguments, raise_on_error=False)
    assert result.is_error
    assert calls == []
    if "unexpected" in str(arguments):
        assert "unexpected" in result.content[0].text
    if arguments == {"nested": {}}:
        assert "value" in result.content[0].text
    if arguments == {}:
        assert "nested" in result.content[0].text


async def test_declared_open_map_preserves_arbitrary_nested_data() -> None:
    configuration = load_settings(
        {"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(configuration)

    async def handler(request, state):
        return success_result(provided_fields(request))

    register_contract_tool(
        server, ToolDefinition("probe", "Open map probe.", SCHEMA), Input, handler
    )
    async with Client(server) as client:
        result = await client.call_tool(
            "probe", {"nested": {"value": 1}, "open": {"custom": {"unknown": True}}}
        )
    assert result.content[0].text == '{"nested":{"value":1},"open":{"custom":{"unknown":true}}}'
    assert result.structured_content is None
