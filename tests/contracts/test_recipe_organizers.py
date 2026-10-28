import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("recipe_organizers")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_recipe_organizers_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:5], ids=lambda case: case.tool)
async def test_unknown_inputs_do_not_call_provider(case):
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
        ("update_recipe_tools", {"slug": "one", "tools": [" "]}),
        ("update_recipe_tools_batch", {"updates": []}),
        (
            "update_recipe_tools_batch",
            {"updates": [{"slug": str(i), "tools": []} for i in range(26)]},
        ),
        ("update_recipe_taxonomy_batch", {"updates": [{"slug": "one", "unknown": True}]}),
    ],
)
async def test_nested_unknown_fields_and_tools_limits_reject_before_http(tool, arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert tool in {item.name for item in await client.list_tools()}
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests
