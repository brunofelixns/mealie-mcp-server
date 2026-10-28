import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("recipe_ingredients")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_recipe_ingredients_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:2], ids=lambda case: case.tool)
async def test_unknown_inputs_rejected_before_mealie(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert case.tool in {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests


@pytest.mark.parametrize(
    "arguments",
    [
        {"slug": "soup", "ingredients": [{"quantity": "2"}]},
        {"slug": "soup", "ingredients": [{"foodId": "not-a-uuid", "foodName": "Salt"}]},
        {"slug": "soup", "ingredients": [{"unknown": True}]},
        {
            "slug": "soup",
            "ingredients": [
                {
                    "foodId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "referencedRecipeId": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                }
            ],
        },
        {"slug": "soup", "ingredients": None},
    ],
)
async def test_nested_input_rejected_before_requests(arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                "update_recipe_ingredients", arguments, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests
