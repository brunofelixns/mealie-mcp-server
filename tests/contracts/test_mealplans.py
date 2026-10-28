import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("mealplans")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_mealplans_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:6], ids=lambda case: case.tool)
async def test_unknown_inputs_do_not_call_mealie(case):
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


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_all_mealplans", {"startDate": "٢٠٢٦-١٠-٢٨"}),
        ("get_all_mealplans", {"startDate": "2026-10-28\n"}),
        ("get_mealplan_with_recipes", {"startDate": "2026/10/28", "endDate": "2026-10-29"}),
        ("create_mealplan_bulk", {"entries": [{"date": "2026-10-28", "unknown": True}]}),
        ("patch_mealplan", {"actions": [{"action": "delete", "id": "1", "date": "2026-10-28"}]}),
        ("patch_mealplan", {"actions": []}),
    ],
)
async def test_nested_unknown_fields_and_date_format_rejected_before_http(tool, arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert tool in {item.name for item in await client.list_tools()}
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests
