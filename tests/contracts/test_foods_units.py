import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("foods_units")


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("update_food", {"foodId": "20000000-0000-4000-8000-000000000001", "aliases": None}),
        ("update_unit", {"unitId": "20000000-0000-4000-8000-000000000001", "useAbbreviation": 0}),
        ("create_unit", {"name": "x", "standardQuantity": False}),
        ("get_food_matches", {"queries": ["🍅" * 101]}),
        ("get_unit_matches", {"queries": ["cup"], "maxMatchesPerQuery": True}),
    ],
)
async def test_invalid_types_and_utf16_bounds_do_not_call_provider(tool, arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_foods_units_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:13], ids=lambda case: case.tool)
async def test_unknown_fields_never_call_mealie(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert case.tool in {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error
        assert "unexpected" in result.content[0].text
        assert not fake.recorded_requests
