import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("ratings_dates")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_ratings_dates_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:2], ids=lambda case: case.tool)
async def test_unknown_arguments_rejected_before_http(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert case.tool in {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("set_recipe_rating", {"slug": "soup", "rating": 0}),
        ("set_recipe_rating", {"slug": "soup", "rating": 2.3}),
        ("set_recipe_rating", {"slug": "soup", "rating": 5.5}),
        ("set_recipe_rating", {"slug": "soup", "rating": True}),
        ("set_recipe_rating", {"slug": "soup", "isFavorite": None}),
        ("mark_recipe_last_made", {"slug": "soup", "timestamp": None}),
    ],
)
async def test_rating_scale_and_timestamp_null_rejected_before_http(tool, arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error and not fake.recorded_requests
