import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.models.inputs.base import ToolInput
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.contracts import ToolDefinition, register_contract_tool
from mealie_mcp_server.tools.helpers import error_result, success_result


class Empty(ToolInput):
    pass


@pytest.mark.parametrize(
    ("data", "text"),
    [
        ("slug-value", '"slug-value"'),
        ([1, False, None], "[1,false,null]"),
        (None, "null"),
        ({"value": 0, "flag": False}, '{"value":0,"flag":false}'),
    ],
)
async def test_result_content_is_not_wrapped_or_automatically_structured(data, text) -> None:
    configuration = load_settings(
        {"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(configuration)

    async def handler(request, state):
        return success_result(data)

    definition = ToolDefinition(
        "probe",
        "Content probe.",
        {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    register_contract_tool(server, definition, Empty, handler)
    async with Client(server) as client:
        result = await client.call_tool("probe", {})
    assert result.content[0].text == text
    assert result.structured_content is None
    assert not result.is_error


async def test_tool_error_preserves_is_error_without_framework_prefix() -> None:
    configuration = load_settings(
        {"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"}
    )
    server = create_server(configuration)

    async def handler(request, state):
        return error_result(ValueError("visible-error"))

    register_contract_tool(
        server,
        ToolDefinition(
            "probe",
            "Error probe.",
            {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        Empty,
        handler,
    )
    async with Client(server) as client:
        result = await client.call_tool("probe", {}, raise_on_error=False)
    assert result.is_error
    assert result.content[0].text == "visible-error"
