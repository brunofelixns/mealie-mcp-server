import json

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie

ID = "22222222-2222-4222-8222-222222222222"
COOKBOOKS = "/api/households/cookbooks"
ACTIONS = "/api/households/recipe-actions"


def spec(method, path, body=None, query=None, response=None):
    return {
        "method": method,
        "path": path,
        "body": body,
        "query": query or {},
        "response": response,
    }


COOKBOOK = {
    "id": ID,
    "name": "Old",
    "slug": "old",
    "public": True,
    "position": 0,
    "unknown": [],
    "householdId": ID,
}
ACTION = {
    "id": ID,
    "title": "Old",
    "actionType": "post",
    "url": "https://hooks.example.test/a",
    "groupId": ID,
    "householdId": ID,
    "unknown": False,
}
CASES = {
    "get_recipe_household": (
        {"slug": "soup"},
        [
            spec(
                "GET",
                "/api/households/self/recipes/soup",
                response={
                    "recipeId": ID,
                    "lastMade": "2026-11-03T15:20:30+01:00",
                    "unknown": False,
                },
            )
        ],
    ),
    "get_cookbooks": (
        {"page": 2, "perPage": 5, "orderDirection": "asc"},
        [
            spec(
                "GET",
                COOKBOOKS,
                query={"page": ["2"], "perPage": ["5"], "orderDirection": ["asc"]},
                response={"items": [COOKBOOK], "total": 1},
            )
        ],
    ),
    "create_cookbook": (
        {"name": "Weeknight", "public": False, "position": 0},
        [
            spec(
                "POST",
                COOKBOOKS,
                {"name": "Weeknight", "public": False, "position": 0},
                response=COOKBOOK,
            )
        ],
    ),
    "get_cookbook": (
        {"cookbookId": "weeknight"},
        [spec("GET", COOKBOOKS + "/weeknight", response=COOKBOOK)],
    ),
    "update_cookbook": (
        {"cookbookId": "old", "changes": {"public": False, "name": " New "}},
        [
            spec("GET", f"{COOKBOOKS}/old", response=COOKBOOK),
            spec(
                "PUT",
                f"{COOKBOOKS}/{ID}",
                {**COOKBOOK, "public": False, "name": " New "},
                response={**COOKBOOK, "public": False, "name": "New", "slug": "new"},
            ),
        ],
    ),
    "delete_cookbook": (
        {"cookbookId": "old"},
        [
            spec("GET", f"{COOKBOOKS}/old", response=COOKBOOK),
            spec("DELETE", f"{COOKBOOKS}/{ID}", response=COOKBOOK),
        ],
    ),
    "get_recipe_favorites": (
        {},
        [
            spec(
                "GET",
                "/api/users/self/favorites",
                response={"ratings": [{"favorite": True, "unknown": 0}]},
            )
        ],
    ),
    "get_recipe_ratings": (
        {},
        [
            spec(
                "GET",
                "/api/users/self/ratings",
                response={"ratings": [{"rating": 0, "unknown": None}]},
            )
        ],
    ),
    "list_recipe_comments": (
        {"queryFilter": "text~soup", "paginationSeed": "seed"},
        [
            spec(
                "GET",
                "/api/comments",
                query={"queryFilter": ["text~soup"], "paginationSeed": ["seed"]},
                response={"items": [], "total": 0},
            )
        ],
    ),
    "get_recipe_comment": (
        {"commentId": ID},
        [spec("GET", f"/api/comments/{ID}", response={"id": ID, "text": "", "unknown": False})],
    ),
    "get_recipe_timeline_event": (
        {"eventId": ID},
        [
            spec(
                "GET",
                f"/api/recipes/timeline/events/{ID}",
                response={"id": ID, "eventMessage": None},
            )
        ],
    ),
    "get_recipe_share_link": (
        {"tokenId": ID},
        [spec("GET", f"/api/shared/recipes/{ID}", response={"id": ID, "expiresAt": None})],
    ),
    "get_recipe_actions": ({}, [spec("GET", ACTIONS, response={"items": [ACTION], "total": 1})]),
    "create_recipe_action": (
        {"actionType": "post", "title": "Notify", "url": "https://hooks.example.test/a"},
        [
            spec(
                "POST",
                ACTIONS,
                {"actionType": "post", "title": "Notify", "url": "https://hooks.example.test/a"},
                response=ACTION,
            )
        ],
    ),
    "get_recipe_action": ({"actionId": ID}, [spec("GET", f"{ACTIONS}/{ID}", response=ACTION)]),
    "update_recipe_action": (
        {"actionId": ID, "changes": {"title": "New"}},
        [
            spec("GET", f"{ACTIONS}/{ID}", response=ACTION),
            spec(
                "PUT",
                f"{ACTIONS}/{ID}",
                {**ACTION, "title": "New"},
                response={**ACTION, "title": "New"},
            ),
        ],
    ),
    "delete_recipe_action": (
        {"actionId": ID},
        [spec("DELETE", f"{ACTIONS}/{ID}", response=ACTION)],
    ),
    "trigger_recipe_action": (
        {"actionId": ID, "slug": "soup", "recipe_scale": 2},
        [
            spec(
                "POST",
                f"{ACTIONS}/{ID}/trigger/soup",
                {"recipe_scale": 2},
                response={"message": "Triggered"},
            )
        ],
    ),
}


@pytest.mark.parametrize("tool_name", CASES)
async def test_recipe_collections_mcp_positive(tool_name):
    arguments, requests = CASES[tool_name]
    with FakeMealie(requests) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        assert not result.is_error
        assert json.loads(result.content[0].text) == requests[-1]["response"]
        assert len(fake.recorded_requests) == len(requests)


@pytest.mark.parametrize("tool_name", CASES)
async def test_recipe_collections_unknown_field_no_http(tool_name):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                tool_name, {**CASES[tool_name][0], "unexpected": True}, raise_on_error=False
            )
        assert result.is_error
        assert fake.recorded_requests == []


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_recipe_comment", {"commentId": "../escape"}),
        ("get_recipe_household", {"slug": "../soup"}),
        ("get_recipe_household", {"slug": ""}),
        ("get_recipe_household", {"slug": "soup", "householdId": ID}),
        ("get_cookbook", {"cookbookId": "../escape"}),
        ("update_cookbook", {"cookbookId": ID, "changes": {}}),
        ("update_cookbook", {"cookbookId": ID, "changes": {"public": None}}),
        ("create_cookbook", {"name": "Cookbook", "slug": None}),
        ("create_cookbook", {"name": "Cookbook", "slug": "ignored-custom-slug"}),
        ("update_cookbook", {"cookbookId": ID, "changes": {"slug": None}}),
        ("update_cookbook", {"cookbookId": ID, "changes": {"slug": "ignored-custom-slug"}}),
        ("update_recipe_action", {"actionId": ID, "changes": {"householdId": ID}}),
        ("trigger_recipe_action", {"actionId": ID, "slug": "soup", "recipe_scale": 0}),
    ],
)
async def test_recipe_collections_invalid_no_http(name, args):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(name, args, raise_on_error=False)
        assert result.is_error
        assert fake.recorded_requests == []
