"""New tools exercise the MCP boundary and exact native request contracts."""

import json

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server

FOOD = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REF = "11111111-1111-4111-8111-111111111111"
INGREDIENT = {
    "referenceId": REF,
    "food": {"id": FOOD, "name": "Salt"},
    "note": "Keep",
    "unit": None,
    "substitutions": [],
}
STEP = {
    "id": FOOD,
    "text": "Cook",
    "durationSeconds": None,
    "ingredientReferences": [{"referenceId": REF}],
    "noteReferences": [],
}
RECIPE = {
    "slug": "soup",
    "updatedAt": "snapshot",
    "recipeIngredient": [INGREDIENT],
    "recipeInstructions": [STEP],
}
ORIGINAL_FOOD = {
    "id": FOOD,
    "name": "Salt",
    "aliases": [],
    "extras": {"keep": True},
    "substitutions": [],
}
CASES = [
    (
        "search_recipes",
        {"search": "soup", "tools": ["pot"], "requireAllTools": False, "page": 2, "perPage": 3},
        [("GET", "/api/recipes", None)],
        {"search": "soup", "tools": "pot", "requireAllTools": "false", "page": "2", "perPage": "3"},
    ),
    (
        "get_recipe_suggestions",
        {"foods": [FOOD], "maxMissingFoods": 0, "includeSubstitutions": False},
        [("GET", "/api/recipes/suggestions", None)],
        {"foods": FOOD, "maxMissingFoods": "0", "includeSubstitutions": "false"},
    ),
    (
        "parse_recipe_ingredient",
        {"parser": "brute", "ingredient": "1 tsp Salt"},
        [("POST", "/api/parser/ingredient", {"parser": "brute", "ingredient": "1 tsp Salt"})],
        {},
    ),
    (
        "parse_recipe_ingredients",
        {"parser": "nlp", "ingredients": ["Salt", "Pepper"]},
        [("POST", "/api/parser/ingredients", {"parser": "nlp", "ingredients": ["Salt", "Pepper"]})],
        {},
    ),
    (
        "update_recipe_ingredient_substitutions",
        {
            "slug": "soup",
            "expectedUpdatedAt": "snapshot",
            "updates": [{"referenceId": REF, "substitutions": [{"substituteFoodId": SUB}]}],
        },
        [
            ("GET", "/api/recipes/soup", None),
            ("GET", f"/api/foods/{SUB}", None),
            (
                "PATCH",
                "/api/recipes/soup",
                {
                    "recipeIngredient": [
                        {**INGREDIENT, "substitutions": [{"substituteFoodId": SUB}]}
                    ]
                },
            ),
        ],
        {},
    ),
    (
        "update_food_substitutions",
        {"foodId": FOOD, "substitutions": [{"substituteFoodId": SUB, "note": None}]},
        [
            ("GET", f"/api/foods/{FOOD}", None),
            ("GET", f"/api/foods/{SUB}", None),
            (
                "PUT",
                f"/api/foods/{FOOD}",
                {**ORIGINAL_FOOD, "substitutions": [{"substituteFoodId": SUB, "note": None}]},
            ),
        ],
        {},
    ),
    (
        "update_recipe_instruction_durations",
        {
            "slug": "soup",
            "expectedUpdatedAt": "snapshot",
            "updates": [{"index": 0, "durationSeconds": 60}],
        },
        [
            ("GET", "/api/recipes/soup", None),
            (
                "PATCH",
                "/api/recipes/soup",
                {
                    "recipeInstructions": [
                        {
                            "text": "Cook",
                            "durationSeconds": 60,
                            "ingredientReferences": [{"referenceId": REF}],
                            "noteReferences": [],
                        }
                    ]
                },
            ),
        ],
        {},
    ),
]


@pytest.mark.parametrize("name,arguments,expected,query", CASES, ids=[row[0] for row in CASES])
async def test_recipe_advanced_mcp_positive(name, arguments, expected, query):
    requests = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.method, request.url.path, body))
        if len(requests) == 1:
            assert dict(request.url.params) == query
        if request.url.path.startswith("/api/foods/"):
            food = (
                {"id": SUB, "name": "Pepper"} if request.url.path.endswith(SUB) else ORIGINAL_FOOD
            )
            return httpx.Response(200, json={**food, **(body or {})})
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json={**RECIPE, **(body or {})})
        if request.url.path == "/api/parser/ingredients":
            return httpx.Response(
                200, json=[{"ingredient": {"note": "Salt"}}, {"ingredient": {"note": "Pepper"}}]
            )
        return httpx.Response(
            200,
            json={"ingredient": {"note": "Salt"}} if request.method == "POST" else {"items": []},
        )

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        result = await client.call_tool(name, arguments)
    assert not result.is_error
    assert requests == expected
    assert json.loads(result.content[0].text) is not None


@pytest.mark.parametrize("name,arguments,expected,query", CASES, ids=[row[0] for row in CASES])
async def test_recipe_advanced_unknown_input_rejected_before_http(name, arguments, expected, query):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(500)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        assert name in {tool.name for tool in await client.list_tools()}
        result = await client.call_tool(
            name, {**arguments, "unexpected": True}, raise_on_error=False
        )
    assert result.is_error and not requests


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("get_recipe_suggestions", {"foods": ["not-a-uuid"]}),
        ("search_recipes", {"perPage": True}),
        ("search_recipes", {"perPage": 0}),
        ("parse_recipe_ingredient", {"ingredient": "Salt", "parser": "automatic"}),
        (
            "update_recipe_ingredient_substitutions",
            {"slug": "soup", "updates": [{"referenceId": REF, "substitutions": []}]},
        ),
        (
            "update_food_substitutions",
            {
                "foodId": FOOD,
                "substitutions": [{"substituteFoodId": SUB, "substituteFood": {"name": "unsafe"}}],
            },
        ),
        (
            "update_recipe_instruction_durations",
            {
                "slug": "soup",
                "expectedUpdatedAt": "snapshot",
                "updates": [{"index": 0, "durationSeconds": 0}],
            },
        ),
        (
            "update_recipe_instruction_durations",
            {
                "slug": "soup",
                "expectedUpdatedAt": "snapshot",
                "updates": [{"index": True, "durationSeconds": 1}],
            },
        ),
    ],
)
async def test_recipe_advanced_nested_validation_prevents_http(name, arguments):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(500)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        assert name in {tool.name for tool in await client.list_tools()}
        result = await client.call_tool(name, arguments, raise_on_error=False)
    assert result.is_error and not requests


@pytest.mark.parametrize("kind", ["ingredient", "food"])
async def test_recipe_advanced_mixed_text_substitutions_mcp(kind):
    alternatives = [
        {"substituteFoodId": SUB, "note": None},
        {"note": "Use stock"},
        {"substituteFoodId": None, "note": "Use water"},
    ]
    calls = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.url.path.endswith(SUB):
            return httpx.Response(200, json={"id": SUB, "name": "Pepper"})
        if kind == "food":
            result = {**ORIGINAL_FOOD, **(body or {})}
        else:
            result = {**RECIPE, **(body or {})}
        return httpx.Response(200, json=result)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    name = (
        "update_food_substitutions" if kind == "food" else "update_recipe_ingredient_substitutions"
    )
    arguments = (
        {"foodId": FOOD, "substitutions": alternatives}
        if kind == "food"
        else {
            "slug": "soup",
            "expectedUpdatedAt": "snapshot",
            "updates": [{"referenceId": REF, "substitutions": alternatives}],
        }
    )
    async with Client(server) as client:
        result = await client.call_tool(name, arguments)
    assert not result.is_error
    assert [(method, path) for method, path, body in calls] == [
        ("GET", f"/api/foods/{FOOD}" if kind == "food" else "/api/recipes/soup"),
        ("GET", f"/api/foods/{SUB}"),
        (
            "PUT" if kind == "food" else "PATCH",
            f"/api/foods/{FOOD}" if kind == "food" else "/api/recipes/soup",
        ),
    ]
    assert (
        calls[-1][2]["substitutions"]
        if kind == "food"
        else calls[-1][2]["recipeIngredient"][0]["substitutions"]
    ) == alternatives


@pytest.mark.parametrize(
    "item",
    [
        {},
        {"note": None},
        {"note": ""},
        {"substituteFoodId": None, "note": "  "},
        {"substituteFoodId": "invalid", "note": "Valid text"},
    ],
)
async def test_recipe_advanced_invalid_text_alternative_prevents_http(item):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(500)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        result = await client.call_tool(
            "update_food_substitutions",
            {"foodId": FOOD, "substitutions": [item]},
            raise_on_error=False,
        )
    assert result.is_error and not calls
