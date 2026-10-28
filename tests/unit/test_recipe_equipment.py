import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_equipment import (
    update_recipe_equipment,
    update_recipe_equipment_batch,
)
from tests.support.organizer_backend import OrganizerBackend

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"tools": ["Pan"]}, ["w", "p"]),
        ({"tools": [], "mode": "replace"}, []),
        ({"add": ["Pan"], "remove": ["Whisk"]}, ["p"]),
    ],
)
async def test_legacy_and_delta_patch_only_tools(changes, expected):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_equipment(client, "one", changes)
    assert [item["id"] for item in result["tools"]["final"]] == expected
    assert list(backend.patches()[0]) == ["tools"]
    assert backend.recipe()["nutrition"] == {"keep": True}


@pytest.mark.parametrize(
    "changes", [{"tools": []}, {"tools": ["Whisk"]}, {"remove": ["Pan"]}, {"add": []}]
)
async def test_noop_skips_patch(changes):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        await update_recipe_equipment(client, "one", changes)
    assert not backend.patches()


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"mode": "merge"},
        {"tools": [], "add": []},
        {"add": ["New"], "remove": ["unknown"], "createMissing": True},
        {"add": ["Whisk"], "remove": ["w"], "createMissing": True},
    ],
)
async def test_invalid_requests_never_create_or_patch(changes):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(ValueError):
            await update_recipe_equipment(client, "one", changes)
    assert not backend.created
    assert not backend.patches()


@pytest.mark.parametrize(
    "updates",
    [
        [],
        [{"slug": str(i), "tools": []} for i in range(26)],
        [{"slug": " ", "tools": []}],
        [{"slug": "one"}, {"slug": " one "}],
    ],
)
async def test_batch_shape_rejected_before_http(updates):
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(ValueError):
            await update_recipe_equipment_batch(client, updates)
    assert not backend.calls


async def test_batch_creation_is_serialized_and_counts_are_per_recipe():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_equipment_batch(
            client,
            [
                {"slug": "one", "tools": ["New"], "createMissing": True},
                {"slug": "two", "add": ["New"], "createMissing": True},
                {"slug": "three"},
            ],
        )
    assert result["requestedCount"] == 3
    assert result["succeededCount"] == 2
    assert result["failedCount"] == 1
    assert [item["slug"] for item in result["results"]] == ["one", "two", "three"]
    assert len(backend.created) == 1


async def test_created_organizers_are_not_rolled_back_after_later_creation_failure():
    backend = OrganizerBackend()
    backend.create_fail_after = 1
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        with pytest.raises(RuntimeError):
            await update_recipe_equipment(
                client, "one", {"tools": ["New1", "New2"], "createMissing": True}
            )
    assert len(backend.created) == 1
    assert not backend.patches()
    assert not any(method == "DELETE" for method, _, _ in backend.calls)


async def test_create_missing_is_per_entry():
    backend = OrganizerBackend()
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_equipment_batch(
            client,
            [
                {"slug": "one", "tools": ["New"], "createMissing": True},
                {"slug": "two", "tools": ["New"], "createMissing": False},
            ],
        )
    assert result["succeededCount"] == result["failedCount"] == 1
    assert result["results"][1]["success"] is False
    assert len(backend.created) == 1


async def test_recipe_writers_never_exceed_five_in_flight():
    backend = OrganizerBackend()
    updates = [{"slug": f"r{i}", "tools": ["Pan"]} for i in range(12)]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_equipment_batch(client, updates)
    assert result["succeededCount"] == 12
    assert 1 < backend.peak_patches <= 5


async def test_replace_current_set_in_another_order_does_not_patch():
    backend = OrganizerBackend()
    backend.recipe()["tools"] = list(backend.catalogs["tools"])
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(backend.handle)) as client:
        result = await update_recipe_equipment(
            client,
            "one",
            {
                "tools": ["Pan", "Whisk"],
                "mode": "replace",
            },
        )
    assert [item["id"] for item in result["tools"]["final"]] == ["p", "w"]
    assert not backend.patches()
