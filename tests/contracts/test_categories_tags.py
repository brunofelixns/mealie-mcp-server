import json

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("categories_tags")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_categories_tags_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:14], ids=lambda case: case.tool)
async def test_unknown_input_does_not_call_mealie(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert case.tool in names
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error
        assert "unexpected" in result.content[0].text
        assert not fake.recorded_requests


async def test_catalog_keeps_exact_original_schemas():
    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with Client(create_server(settings)) as client:
        tools = await client.list_tools()
    from tests.support.contracts import FIXTURES

    original = {
        tool["name"]: tool for tool in json.loads((FIXTURES / "catalog.json").read_text())["tools"]
    }
    assert {case.tool for case in CASES[:14]} <= {tool.name for tool in tools}
    for tool in tools:
        assert tool.input_schema == original[tool.name]["inputSchema"]
