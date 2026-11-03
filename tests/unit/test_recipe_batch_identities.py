"""A metadata batch resolves recipe aliases before any mutation is allowed."""

import asyncio
import json
from copy import deepcopy

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.inputs.recipe_jobs import UpdateRecipeMetadataBatchInput
from mealie_mcp_server.services.recipe_jobs import update_recipe_metadata_batch

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
SOUP_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SALAD_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def batch(*slugs, concurrency=2):
    return UpdateRecipeMetadataBatchInput.model_validate(
        {
            "items": [
                {
                    "slug": slug,
                    "expectedUpdatedAt": "fresh",
                    "settings": {"locked": index == 0, "public": index != 0},
                }
                for index, slug in enumerate(slugs)
            ],
            "concurrency": concurrency,
        }
    )


@pytest.mark.parametrize(
    "aliases,identities",
    [
        (("soup", SOUP_ID), (SOUP_ID, SOUP_ID)),
        (("soup", "Soup"), (SOUP_ID, SOUP_ID)),
        ((SOUP_ID, SOUP_ID.upper()), (SOUP_ID, SOUP_ID.upper())),
        (("soup", "old-soup"), (SOUP_ID, "aaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa")),
    ],
)
async def test_aliases_reject_whole_batch_before_either_gated_snapshot_can_write(
    aliases, identities
):
    """Both initial settings snapshots are taken before either GET completes."""
    stored = {
        "id": SOUP_ID,
        "slug": "soup",
        "updatedAt": "fresh",
        "settings": {"locked": False, "public": False, "future": 1},
    }
    initial_reads = []
    writes = []
    both_read = asyncio.Event()

    async def handle(request):
        if request.method == "GET":
            snapshot = deepcopy(stored)
            if len(initial_reads) < 2:
                snapshot["id"] = identities[len(initial_reads)]
                initial_reads.append(request.url.path)
                if len(initial_reads) == 2:
                    both_read.set()
                await both_read.wait()
            return httpx.Response(200, json=snapshot)
        assert request.method == "PATCH"
        writes.append(json.loads(request.content))
        stored.update(writes[-1])
        return httpx.Response(200, json=stored)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="same recipe"):
            async with asyncio.timeout(2):
                await update_recipe_metadata_batch(client, batch(*aliases))
    assert len(initial_reads) == 2
    assert writes == []
    assert stored["settings"] == {"locked": False, "public": False, "future": 1}


async def test_distinct_targets_finish_preflight_then_reread_and_patch_stable_ids_in_order():
    stored = {
        SOUP_ID: {
            "id": SOUP_ID,
            "slug": "soup",
            "updatedAt": "fresh",
            "settings": {"locked": False, "public": False, "future": 1},
            "ingredients": [{"private": "preserve"}],
        },
        SALAD_ID: {
            "id": SALAD_ID,
            "slug": "salad",
            "updatedAt": "fresh",
            "settings": {"locked": False, "public": False, "future": 2},
            "ingredients": [],
        },
    }
    aliases = {"soup": SOUP_ID, "salad": SALAD_ID}
    calls = []
    preflight = set()

    async def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        calls.append((request.method, target))
        if target in aliases:
            assert request.method == "GET"
            preflight.add(target)
            return httpx.Response(200, json=stored[aliases[target]])
        assert preflight == {"soup", "salad"}
        assert target in stored
        if request.method == "PATCH":
            stored[target].update(json.loads(request.content))
        return httpx.Response(200, json=stored[target])

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, batch("soup", "salad"))
    assert [item["slug"] for item in result["items"]] == ["soup", "salad"]
    assert [item["status"] for item in result["items"]] == ["updated", "updated"]
    assert result["atomic"] is False
    assert stored[SOUP_ID]["settings"] == {"locked": True, "public": False, "future": 1}
    assert stored[SALAD_ID]["settings"] == {"locked": False, "public": True, "future": 2}
    assert stored[SOUP_ID]["ingredients"] == [{"private": "preserve"}]
    assert calls.count(("GET", SOUP_ID)) == calls.count(("GET", SALAD_ID)) == 1
    assert sorted(target for method, target in calls if method == "PATCH") == [
        SOUP_ID,
        SALAD_ID,
    ]


@pytest.mark.parametrize("failure", ["timeout", "server", "missing", "malformed", "bad-id"])
async def test_failed_identity_read_has_failed_outcome_and_distinct_recipe_still_updates(failure):
    calls = []

    def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        calls.append((request.method, target))
        if target == "unresolved":
            assert request.method == "GET"
            if failure == "timeout":
                raise httpx.ReadTimeout("private signed-url secret")
            if failure in {"server", "missing"}:
                return httpx.Response(500 if failure == "server" else 404, text="secret")
            if failure == "malformed":
                return httpx.Response(200, json=[])
            return httpx.Response(200, json={"id": "private-secret/not-id"})
        assert target in {"soup", SOUP_ID}
        original = {"id": SOUP_ID, "slug": "soup", "updatedAt": "fresh", "settings": {}}
        if request.method == "PATCH":
            original.update(json.loads(request.content))
        return httpx.Response(200, json=original)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, batch("unresolved", "soup"))
    assert [item["status"] for item in result["items"]] == ["failed", "updated"]
    assert [target for method, target in calls if method == "PATCH"] == [SOUP_ID]
    assert calls.count(("GET", "unresolved")) == 1
    error = result["items"][0]["error"]
    assert "unknown" not in error.lower() and "retry" not in error.lower()
    assert "private" not in error and "secret" not in error and "signed-url" not in error


@pytest.mark.parametrize("identity", [None, False, [], "", "../secret", "not-uuid", "0" * 32])
async def test_invalid_resolved_identity_never_reaches_patch(identity):
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json={"id": identity, "updatedAt": "fresh"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, batch("soup"))
    assert result["items"][0]["status"] == "failed"
    assert calls == ["GET"]


async def test_stable_id_reread_still_rejects_snapshot_changed_after_preflight():
    calls = []

    def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        calls.append((request.method, target))
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={
                "id": SOUP_ID,
                "updatedAt": "fresh" if target == "soup" else "changed",
                "settings": {"locked": False},
            },
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, batch("soup"))
    assert result["items"][0]["status"] == "rejected"
    assert calls == [("GET", "soup"), ("GET", SOUP_ID)]


async def test_uppercase_resolved_uuid_is_normalized_for_fresh_read_and_patch():
    calls = []

    def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        calls.append((request.method, target))
        original = {"id": SOUP_ID.upper(), "updatedAt": "fresh", "settings": {}}
        if request.method == "PATCH":
            original.update(json.loads(request.content))
        return httpx.Response(200, json=original)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, batch("soup"))
    assert result["items"][0]["status"] == "updated"
    assert calls == [("GET", "soup"), ("GET", SOUP_ID), ("PATCH", SOUP_ID)]


async def test_cancellation_during_identity_resolution_cancels_reads_without_any_patch():
    entered = asyncio.Event()
    finished = []
    calls = []

    async def handle(request):
        calls.append(request.method)
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            finished.append(request.method)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_metadata_batch(client, batch("soup", "salad")))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert calls and set(calls) == {"GET"}
    assert finished == calls


async def test_cancellation_after_patch_propagates_without_replaying_write():
    writing = asyncio.Event()
    calls = []
    closed = []

    async def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        calls.append((request.method, target))
        if request.method == "GET":
            return httpx.Response(200, json={"id": SOUP_ID, "updatedAt": "fresh"})
        assert request.method == "PATCH"
        writing.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(target)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_metadata_batch(client, batch("soup")))
        await writing.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert calls == [("GET", "soup"), ("GET", SOUP_ID), ("PATCH", SOUP_ID)]
    assert closed == [SOUP_ID]
