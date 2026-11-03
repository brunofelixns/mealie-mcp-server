import copy
import json

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_metadata import UpdateRecipeMetadataInput
from mealie_mcp_server.services.recipe_metadata import update_recipe_metadata

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
TOKEN = "2026-11-03T10:00:00Z"
ORIGINAL = {
    "slug": "soup",
    "updatedAt": TOKEN,
    "nutrition": {"calories": "100", "proteinContent": "5", "future": "keep"},
    "settings": {"public": False, "showNutrition": True, "future": "keep"},
    "extras": {"keep": {"nested": 0}, "remove": "old"},
    "recipeIngredient": [{"note": "original"}],
    "notes": [{"title": "Original", "text": "Keep"}],
}


async def test_metadata_merges_nested_fields_and_preserves_false_zero_null_and_unknowns():
    original = copy.deepcopy(ORIGINAL)
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=original)
        payload = json.loads(request.content)
        writes.append(payload)
        return httpx.Response(200, json={**original, **payload})

    args = UpdateRecipeMetadataInput.model_validate(
        {
            "slug": "soup",
            "expectedUpdatedAt": TOKEN,
            "prepTime": "",
            "cookTime": None,
            "recipeServings": 0,
            "nutrition": {"calories": "0", "sodiumContent": None},
            "settings": {"showNutrition": False},
            "extras": {"new": None},
            "removeExtraKeys": ["remove"],
        }
    )
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata(client, "soup", provided_fields(args))
    assert len(writes) == 1
    patch = writes[0]
    assert patch["nutrition"] == {**original["nutrition"], "calories": "0", "sodiumContent": None}
    assert patch["settings"] == {**original["settings"], "showNutrition": False}
    assert patch["extras"] == {"keep": {"nested": 0}, "new": None}
    assert patch["recipeServings"] == 0 and patch["prepTime"] == "" and patch["cookTime"] is None
    assert "slug" not in patch and "expectedUpdatedAt" not in patch
    assert (
        result["notes"] == original["notes"]
        and result["recipeIngredient"] == original["recipeIngredient"]
    )
    assert original == ORIGINAL


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"expectedUpdatedAt": "stale", "prepTime": "PT10M"}, "Stale snapshot"),
        ({"expectedUpdatedAt": TOKEN}, "at least one"),
        ({"expectedUpdatedAt": TOKEN, "extras": {"same": 1}, "removeExtraKeys": ["same"]}, "both"),
    ],
)
async def test_metadata_rejects_stale_empty_or_conflicting_changes_without_writing(changes, match):
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match=match):
            await update_recipe_metadata(client, "soup", changes)
    assert all(method == "GET" for method in calls)


async def test_metadata_noop_skips_patch_and_explicit_null_clears_nutrition():
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**ORIGINAL, **writes[-1]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await update_recipe_metadata(
            client, "soup", {"expectedUpdatedAt": TOKEN, "settings": {"public": False}}
        )
        assert writes == []
        result = await update_recipe_metadata(
            client, "soup", {"expectedUpdatedAt": TOKEN, "nutrition": None}
        )
    assert writes == [{"nutrition": None}] and result["nutrition"] is None


@pytest.mark.parametrize("failure", ["http", "timeout", "mismatch"])
async def test_metadata_failure_is_not_retried_and_private_body_is_not_exposed(failure):
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        if failure == "http":
            return httpx.Response(403, json={"detail": "private-sentinel"})
        if failure == "timeout":
            raise httpx.ReadTimeout("private-sentinel")
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(Exception) as caught:
            await update_recipe_metadata(
                client, "soup", {"expectedUpdatedAt": TOKEN, "prepTime": "PT5M"}
            )
    assert len(writes) == 1
    assert "private-sentinel" not in str(caught.value)
    if failure == "mismatch":
        assert "verification failed" in str(caught.value) and "Inspect" in str(caught.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("settings", {"public": None}),
        ("nutrition", {"invented": "1"}),
        ("settings", {"showNutrition": "false"}),
        ("recipeServings", True),
    ],
)
def test_metadata_nested_inputs_are_strict(field, value):
    with pytest.raises(ValidationError):
        UpdateRecipeMetadataInput.model_validate(
            {"slug": "soup", "expectedUpdatedAt": TOKEN, field: value}
        )


@pytest.mark.parametrize("before,after", [(False, 0), (True, 1), (0, False), ([False], [0])])
async def test_metadata_extras_type_changes_are_not_mistaken_for_noops(before, after):
    original = {**ORIGINAL, "extras": {"value": before}}
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=original)
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**original, **writes[-1]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await update_recipe_metadata(
            client,
            "soup",
            {
                "expectedUpdatedAt": TOKEN,
                "extras": {"value": after},
            },
        )
    assert len(writes) == 1
    assert type(writes[0]["extras"]["value"]) is type(after)


@pytest.mark.parametrize("field", ["recipeServings", "recipeYieldQuantity"])
def test_null_yield_numbers_reject_before_provider_coerces_them_to_zero(field):
    with pytest.raises(ValidationError):
        UpdateRecipeMetadataInput.model_validate(
            {
                "slug": "soup",
                "expectedUpdatedAt": TOKEN,
                field: None,
            }
        )
