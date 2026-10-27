import pytest
from fastmcp import Client
from pydantic import Field, field_validator

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.base import JsonInteger, ToolInput
from mealie_mcp_server.server import create_server
from mealie_mcp_server.support.strings import trim
from mealie_mcp_server.tools.contracts import ToolDefinition, register_contract_tool
from mealie_mcp_server.tools.helpers import success_result


class LookupInput(ToolInput):
    queries: list[str]
    max_matches: JsonInteger = Field(alias="maxMatches")

    @field_validator("queries")
    @classmethod
    def trim_queries(cls, value: list[str]) -> list[str]:
        return [trim(query) for query in value]


@pytest.mark.parametrize("maximum", [1, 1.0])
async def test_transforms_run_before_public_schema_bounds(maximum):
    schema = {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string", "minLength": 1, "maxLength": 200},
            },
            "maxMatches": {"type": "integer", "minimum": 1, "maximum": 25},
        },
        "required": ["queries", "maxMatches"],
        "additionalProperties": False,
    }
    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(settings)

    async def handler(request, state):
        return success_result(provided_fields(request))

    register_contract_tool(
        server,
        ToolDefinition("transform_probe", "Original Zod transformations.", schema),
        LookupInput,
        handler,
    )
    arguments = {"queries": [" " + "a" * 200 + " "], "maxMatches": maximum}
    async with Client(server) as client:
        result = await client.call_tool("transform_probe", arguments, raise_on_error=False)
    assert not result.is_error
    assert result.content[0].text == '{"queries":["' + "a" * 200 + '"],"maxMatches":1}'
    assert arguments["queries"][0].startswith(" ")
