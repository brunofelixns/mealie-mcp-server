import asyncio

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.inputs.recipe_queues import (
    FindRecipesForIngredientsInput,
    GetRecipesForClassificationInput,
)
from mealie_mcp_server.services.ingredient_resolution import resolve_ingredients
from mealie_mcp_server.services.recipe_classification import get_recipes_for_classification
from mealie_mcp_server.services.recipe_discovery import find_recipes_for_ingredients

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


async def test_resolution_does_not_trim_provider_names_or_guess_between_aliases():
    def handle(request):
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a", "name": " salt ", "aliases": [{"name": "sal"}]},
                    {"id": "b", "name": "Other", "aliases": [{"name": "SAL"}]},
                ]
            },
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        resolved, unresolved = await resolve_ingredients(client, [" salt ", "sal"])
    assert resolved == []
    assert unresolved == [
        {"query": "salt", "reason": "ambiguous", "candidates": [" salt ", "Other"]},
        {"query": "sal", "reason": "ambiguous", "candidates": [" salt ", "Other"]},
    ]


async def test_lookup_failure_stays_data_and_is_never_silently_text_searched():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(503, json={"detail": "provider secret"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await find_recipes_for_ingredients(
            client, FindRecipesForIngredientsInput(ingredients=["salt"])
        )
    assert result["matchSource"] == "none" and result["recipes"] == []
    assert result["unresolvedIngredients"] == [
        {
            "query": "salt",
            "reason": "lookup-failed",
            "error": "Unable to retrieve foods: Mealie API error 503.",
        }
    ]
    assert calls == ["/api/foods"]


async def test_partial_suggestions_failure_retains_other_ingredient_results():
    def handle(request):
        assert request.method == "GET"
        if request.url.path == "/api/foods":
            name = request.url.params["search"]
            return httpx.Response(200, json={"items": [{"id": name, "name": name}]})
        if request.url.params["foods"] == "bad":
            return httpx.Response(503, json={"detail": "private"})
        return httpx.Response(
            200, json={"items": [{"recipe": {"slug": "good"}, "missingFoods": []}]}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await find_recipes_for_ingredients(
            client, FindRecipesForIngredientsInput(ingredients=["good", "bad"])
        )
    assert result["matchSource"] == "suggestions"
    assert result["notes"] == [
        "Recipe suggestions lookup failed for: bad (other ingredients still searched)."
    ]
    assert result["recipes"][0]["matchedIngredients"] == ["good"]


@pytest.mark.parametrize("phase", ["foods", "suggestions"])
async def test_cancellation_propagates_and_no_write_is_attempted(phase):
    entered = asyncio.Event()
    calls = []

    async def handle(request):
        calls.append(request.method)
        if phase == "suggestions" and request.url.path == "/api/foods":
            return httpx.Response(200, json={"items": [{"id": "salt", "name": "salt"}]})
        entered.set()
        await asyncio.Event().wait()

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(
            find_recipes_for_ingredients(
                client, FindRecipesForIngredientsInput(ingredients=["salt"])
            )
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert set(calls) == {"GET"}


async def test_classification_sparse_deadline_does_not_fetch_filtered_details():
    clock = iter([0.0, 30000.0])

    def handle(request):
        assert request.url.path == "/api/recipes"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "a",
                        "slug": "complete",
                        "createdAt": "date",
                        "recipeCategory": [{}],
                        "tags": [{}],
                    }
                ]
            },
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await get_recipes_for_classification(
            client, GetRecipesForClassificationInput(), now=lambda: next(clock)
        )
    assert result["hasMore"] and result["scannedCount"] == 1
    assert result["returnedCount"] == 0 and result["nextCursor"]


async def test_numeric_food_id_uses_javascript_scalar_text():
    def handle(request):
        return httpx.Response(200, json={"items": [{"id": 1.0, "name": "Salt"}]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        resolved, unresolved = await resolve_ingredients(client, ["salt"])
    assert not unresolved
    assert resolved[0].food_id == "1"
