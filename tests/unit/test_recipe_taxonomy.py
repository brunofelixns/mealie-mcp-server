import copy

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_taxonomy import (
    build_taxonomy_patch,
    update_recipe_taxonomy,
    update_recipe_taxonomy_batch,
)
from tests.support.organizer_backend import OrganizerBackend

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("changes", "final", "added", "removed"),
    [
        ({"categories": ["Dessert"]}, ["a", "b"], ["b"], []),
        ({"categories": ["Dessert"], "mode": "replace"}, ["b"], ["b"], ["a"]),
        ({"categories": [], "mode": "replace"}, [], [], ["a"]),
        ({"addCategories": ["Dessert"], "removeCategories": ["Dinner"]}, ["b"], ["b"], ["a"]),
    ],
)
async def test_category_merge_replace_delta_and_unrelated_fields(changes, final, added, removed):
    backend = OrganizerBackend()
    before = copy.deepcopy(backend.recipe())
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_taxonomy(client, "one", changes)
    assert [item["id"] for item in result["categories"]["final"]] == final
    assert [item["id"] for item in result["categories"]["added"]] == added
    assert [item["id"] for item in result["categories"]["removed"]] == removed
    assert list(backend.patches()[0]) == ["recipeCategory"]
    assert backend.recipe()["nutrition"] == before["nutrition"]
    assert backend.recipe()["recipeIngredient"] == before["recipeIngredient"]
    assert backend.recipe()["tags"] == before["tags"]


@pytest.mark.parametrize(
    "changes",
    [
        {"categories": []},
        {"categories": ["Dinner"]},
        {"addCategories": []},
        {"removeCategories": ["Dessert"]},
    ],
)
async def test_noop_skips_patch(changes):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_taxonomy(client, "one", changes)
    assert result["categories"]["added"] == result["categories"]["removed"] == []
    assert not backend.patches()


@pytest.mark.parametrize(
    "changes",
    [
        {"categories": [], "addCategories": []},
        {"addCategories": [], "mode": "merge"},
        {"addCategories": ["Dinner"], "removeCategories": ["a"], "createMissing": True},
        {"addCategories": ["New"], "removeCategories": ["unknown"], "createMissing": True},
        {"categories": ["New"], "removeTags": ["unknown"], "createMissing": True},
    ],
)
async def test_invalid_mutation_never_creates_or_patches(changes):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(ValueError):
            await update_recipe_taxonomy(client, "one", changes)
    assert not backend.created
    assert not backend.patches()


async def test_build_without_collections_does_not_fetch_or_refetch():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await build_taxonomy_patch(client, copy.deepcopy(backend.recipe()), {})
    assert result == {"patchFields": {}}
    assert not backend.calls


async def test_create_missing_is_not_promoted_to_sibling_entries():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        results = await update_recipe_taxonomy_batch(
            client,
            [
                {"slug": "one", "categories": ["New"], "createMissing": True},
                {"slug": "two", "categories": ["New"], "createMissing": False},
            ],
        )
    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "do not exist" in results[1]["error"]
    assert len(backend.created) == 1


async def test_batch_has_no_25_cap_isolates_errors_and_bounds_five():
    backend = OrganizerBackend()
    updates = [{"slug": f"r{i}", "categories": ["Dinner"]} for i in range(26)] + [
        {"slug": "missing", "tags": ["Quick"]}
    ]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_taxonomy_batch(client, updates)
    assert len(result) == 27
    assert [item["slug"] for item in result] == [item["slug"] for item in updates]
    assert all(item["success"] for item in result[:-1])
    assert result[-1]["success"] is False
    assert 1 < backend.peak_reads <= 5
    assert not backend.patches()


async def test_batch_duplicate_slugs_rejected_before_http():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(ValueError, match="Duplicate recipe slug"):
            await update_recipe_taxonomy_batch(client, [{"slug": "one"}, {"slug": " one "}])
    assert not backend.calls


async def test_batch_serializes_creation_and_retains_created_organizer_after_failed_patch():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        results = await update_recipe_taxonomy_batch(
            client,
            [
                {"slug": "one", "categories": ["New"], "createMissing": True},
                {"slug": "two", "categories": ["New"], "createMissing": True},
            ],
        )
    assert all(result["success"] for result in results)
    assert len(backend.created) == 1
    backend.patch_fail = True
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(RuntimeError):
            await update_recipe_taxonomy(
                client, "three", {"tags": ["Another"], "createMissing": True}
            )
    assert len(backend.created) == 2
    assert backend.created[-1][1]["name"] == "Another"
    assert not any(method == "DELETE" for method, _, _ in backend.calls)
