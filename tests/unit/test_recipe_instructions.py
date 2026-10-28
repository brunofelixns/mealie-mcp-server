import asyncio
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_instructions import (
    InstructionVerificationError,
    StaleInstructionSnapshotError,
    update_recipe_instructions,
    update_recipe_instructions_batch,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
REF = "11111111-1111-4111-8111-111111111111"
NOTE = "22222222-2222-4222-8222-222222222222"
TOKEN = "2026-10-28T10:00:00Z"
STEP = {
    "id": "unstable",
    "text": "Original",
    "title": None,
    "summary": None,
    "ingredientReferences": [{"referenceId": REF, "extra": True}],
    "noteReferences": [{"referenceId": NOTE, "extra": True}],
    "providerExtra": {"keep": True},
}
ORIGINAL = {
    "slug": "soup",
    "updatedAt": TOKEN,
    "recipeInstructions": [STEP],
    "recipeIngredient": [{"referenceId": REF}],
}
CHANGES = {"expectedUpdatedAt": TOKEN, "instructions": [{"text": "Changed"}]}


async def test_stale_snapshot_is_rejected_before_any_patch():
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(StaleInstructionSnapshotError):
            await update_recipe_instructions(
                client, "soup", {**CHANGES, "expectedUpdatedAt": "old"}
            )
    assert calls == ["GET"]


async def test_delta_keeps_untouched_dangling_references_notes_and_unknown_fields():
    snapshot = {**ORIGINAL, "recipeIngredient": []}
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=snapshot)
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**snapshot, **writes[-1]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_instructions(
            client,
            "soup",
            {"expectedUpdatedAt": TOKEN, "updateInstructions": [{"index": 0, "text": "New"}]},
        )
    step = result["recipeInstructions"][0]
    assert step["ingredientReferences"] == STEP["ingredientReferences"]
    assert step["noteReferences"] == STEP["noteReferences"]
    assert step["providerExtra"] == STEP["providerExtra"]
    assert "id" not in step and set(writes[0]) == {"recipeInstructions"}


@pytest.mark.parametrize("rollback", ["restored", "mismatch", "api_error"])
async def test_rollback_is_itself_verified_by_content(rollback):
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        if len(writes) == 1:
            return httpx.Response(200, json={**ORIGINAL, "recipeInstructions": []})
        if rollback == "api_error":
            return httpx.Response(503, json={"detail": "private"})
        rows = [{**STEP, "id": "new-id"}] if rollback == "restored" else []
        return httpx.Response(200, json={**ORIGINAL, "recipeInstructions": rows})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(InstructionVerificationError) as caught:
            await update_recipe_instructions(client, "soup", CHANGES)
    assert caught.value.rollback_succeeded is (rollback == "restored")
    if rollback == "api_error":
        assert caught.value.rollback_error == "Mealie API error 503."
    if rollback == "mismatch":
        assert "after rollback did not match" in caught.value.rollback_error
    assert writes[1] == {
        "recipeInstructions": [{key: value for key, value in STEP.items() if key != "id"}]
    }
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("stage", ["read", "write", "rollback"])
async def test_cancelled_request_finishes_issued_write_verification(stage):
    entered = asyncio.Event()
    release = asyncio.Event()
    writes = []

    async def handle(request):
        if request.method == "GET":
            if stage == "read":
                entered.set()
                await release.wait()
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        if stage == "write" and len(writes) == 1 or stage == "rollback" and len(writes) == 2:
            entered.set()
            await release.wait()
        return httpx.Response(
            200, json={**ORIGINAL, "recipeInstructions": []} if len(writes) == 1 else ORIGINAL
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_instructions(client, "soup", CHANGES))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            await asyncio.sleep(0)
            if stage != "read":
                assert not task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
    assert len(writes) == (0 if stage == "read" else 2)


async def test_batch_keeps_stale_noop_and_change_results_in_input_order():
    def handle(request):
        slug = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            return httpx.Response(200, json={**ORIGINAL, "slug": slug})
        return httpx.Response(200, json={**ORIGINAL, **json.loads(request.content), "slug": slug})

    updates = [
        {"slug": "stale", **CHANGES, "expectedUpdatedAt": "old"},
        {
            "slug": "noop",
            "expectedUpdatedAt": TOKEN,
            "updateInstructions": [{"index": 0, "text": "Original"}],
        },
        {"slug": "changed", **CHANGES},
    ]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_instructions_batch(client, updates)
    assert result["apiRequestCount"] == 4
    assert result["succeededCount"] == 2 and result["failedCount"] == 1
    assert result["results"][0]["error"]["stale"] is True
    assert result["results"][1] == {
        "slug": "noop",
        "success": True,
        "instructionCount": 1,
        "changed": False,
    }
    assert result["results"][2] == {
        "slug": "changed",
        "success": True,
        "instructionCount": 1,
        "changed": True,
    }


@pytest.mark.parametrize(
    "delta",
    [
        {"updateInstructions": [{"index": 0, "text": "X"}, {"index": 0, "text": "Y"}]},
        {"removeInstructionIndexes": [0, 0]},
        {"removeInstructionIndexes": [0], "updateInstructions": [{"index": 0, "text": "X"}]},
        {
            "removeInstructionIndexes": [0],
            "addInstructions": [{"text": "X", "insertAfterIndex": 0}],
        },
    ],
)
async def test_conflicting_index_delta_is_rejected_before_write(delta):
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="Invalid instruction request"):
            await update_recipe_instructions(client, "soup", {"expectedUpdatedAt": TOKEN, **delta})
    assert calls == ["GET"]


async def test_batch_runs_at_most_five_recipes_and_keeps_result_order():
    entered = asyncio.Event()
    release = asyncio.Event()
    active = peak = 0

    async def handle(request):
        nonlocal active, peak
        slug = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            active += 1
            peak = max(peak, active)
            if active == 5:
                entered.set()
            try:
                await release.wait()
            finally:
                active -= 1
            return httpx.Response(200, json={**ORIGINAL, "slug": slug})
        return httpx.Response(200, json={**ORIGINAL, **json.loads(request.content), "slug": slug})

    updates = [{"slug": f"r{i}", **CHANGES} for i in range(8)]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_instructions_batch(client, updates))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert peak == 5
        finally:
            release.set()
        result = await asyncio.wait_for(task, 2)
    assert peak == 5 and active == 0
    assert result["apiRequestCount"] == 16 and result["succeededCount"] == 8
    assert [item["slug"] for item in result["results"]] == [item["slug"] for item in updates]
