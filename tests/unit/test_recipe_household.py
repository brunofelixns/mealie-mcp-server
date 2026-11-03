import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.inputs.recipe_collections import GetRecipeHouseholdInput
from mealie_mcp_server.services import recipe_collections as service

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
ID = "22222222-2222-4222-8222-222222222222"


@pytest.mark.parametrize("last_made", [None, "2026-11-03T15:20:30+01:00"])
async def test_recipe_household_uses_self_household_and_preserves_native_timestamp(last_made):
    calls = []
    expected = {"recipeId": ID, "lastMade": last_made, "unknown": False}

    def handle(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.path == "/api/households/self/recipes/soup"
        assert not request.content
        assert not request.url.query
        return httpx.Response(200, json=expected)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.get_recipe_household(client, "soup") == expected
    assert len(calls) == 1


@pytest.mark.parametrize(
    "arguments",
    [
        {"slug": "../soup"},
        {"slug": "soup/one"},
        {"slug": ".."},
        {"slug": ""},
        {"slug": 1},
        {"slug": "soup", "householdId": ID},
    ],
)
def test_recipe_household_strict_slug_and_no_caller_selected_household(arguments):
    with pytest.raises(ValidationError):
        GetRecipeHouseholdInput.model_validate(arguments)


async def test_recipe_household_invalid_path_rejected_before_http():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="Invalid"):
            await service.get_recipe_household(client, "../soup")
    assert not calls


async def test_recipe_household_propagates_safe_native_permission_error():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(403, json={"detail": "Not permitted", "private": "not-for-output"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError) as caught:
            await service.get_recipe_household(client, "soup")
    assert caught.value.status == 403
    assert "not-for-output" not in str(caught.value)
    assert len(calls) == 1


async def test_recipe_household_transport_error_is_safe_and_not_retried():
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("private-provider-response", request=request)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError) as caught:
            await service.get_recipe_household(client, "soup")
    assert "private-provider-response" not in str(caught.value)
    assert len(calls) == 1
