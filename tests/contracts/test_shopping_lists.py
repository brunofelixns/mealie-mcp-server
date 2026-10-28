import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("shopping_lists")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_shopping_lists_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:13], ids=lambda case: case.tool)
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
        ("get_shopping_list_items", {"listId": "40000000-0000-4000-8000-000000000001"}),
        (
            "create_shopping_list_items_bulk",
            {"items": [{"shoppingListId": "plain-id", "unknown": True}]},
        ),
        (
            "create_shopping_list_items_bulk",
            {
                "items": [
                    {
                        "shoppingListId": "plain-id",
                        "recipeReferences": [{"recipeId": "recipe", "unknown": True}],
                    }
                ]
            },
        ),
        (
            "create_shopping_list_items_bulk",
            {"items": [{"shoppingListId": "plain-id", "position": False}]},
        ),
        (
            "update_shopping_list_item",
            {"itemId": "40000000-0000-4000-8000-000000000002", "checked": 0},
        ),
        (
            "create_shopping_list_item",
            {"shoppingListId": "40000000-0000-4000-8000-000000000001", "note": None},
        ),
    ],
)
async def test_strict_nested_records_and_types_do_not_reach_mealie(tool, arguments):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert tool in {item.name for item in await client.list_tools()}
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests
