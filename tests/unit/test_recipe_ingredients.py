import asyncio
import json

import anyio
import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_ingredients import (
    IngredientVerificationError,
    update_recipe_ingredients,
    update_recipe_ingredients_batch,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
FOOD = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REF = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
ORIGINAL = {
    "id": "own",
    "slug": "soup",
    "recipeIngredient": [{"referenceId": OTHER, "note": "Keep", "food": None, "unit": None}],
    "other": {"preserve": True},
}
CHANGES = {"ingredients": [{"referenceId": REF, "foodId": FOOD, "foodName": "Salt"}]}


@pytest.mark.parametrize("rollback_fails", [False, True])
async def test_wrong_entity_name_is_verified_and_rollback_outcome_is_explicit(rollback_fails):
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        body = json.loads(request.content)
        writes.append(body)
        if len(writes) == 1:
            return httpx.Response(
                200,
                json={**ORIGINAL, "recipeIngredient": [{"food": {"id": FOOD, "name": "Pepper"}}]},
            )
        return httpx.Response(
            503 if rollback_fails else 200,
            json={"detail": "private"} if rollback_fails else ORIGINAL,
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(IngredientVerificationError) as caught:
            await update_recipe_ingredients(client, "soup", CHANGES)
    assert len(writes) == 2
    assert writes[1] == {
        "recipeIngredient": [{**ORIGINAL["recipeIngredient"][0], "referenceId": REF}]
    }
    assert caught.value.rollback_succeeded is not rollback_fails
    assert caught.value.rollback_error == ("Mealie API error 503." if rollback_fails else None)
    assert "Pepper" in str(caught.value) and "private" not in str(caught.value)


async def test_delta_rollback_restores_snapshot_without_positional_reference_replacement():
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        return httpx.Response(
            200, json={**ORIGINAL, "recipeIngredient": []} if len(writes) == 1 else ORIGINAL
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(IngredientVerificationError):
            await update_recipe_ingredients(
                client,
                "soup",
                {
                    "addIngredients": [
                        {
                            "referenceId": REF,
                            "foodId": FOOD,
                            "foodName": "Salt",
                            "insertBeforeReferenceId": OTHER,
                        }
                    ]
                },
            )
    assert writes[1] == {"recipeIngredient": ORIGINAL["recipeIngredient"]}


async def test_unknown_subrecipe_never_writes_and_self_reference_is_rejected():
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        return (
            httpx.Response(200, json=ORIGINAL)
            if request.url.path.endswith("/soup")
            else httpx.Response(404, json={"detail": "private"})
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="does not match any recipe"):
            await update_recipe_ingredients(
                client, "soup", {"ingredients": [{"referencedRecipeId": "missing"}]}
            )
        with pytest.raises(ValueError, match="cannot reference itself"):
            await update_recipe_ingredients(
                client, "soup", {"ingredients": [{"referencedRecipeId": "OWN"}]}
            )
    assert all(method == "GET" for method, path in calls)


async def test_invalid_pair_rejected_before_even_reading_recipe():
    def handle(request):
        pytest.fail("No request should be made")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="foodId was given without foodName"):
            await update_recipe_ingredients(client, "soup", {"ingredients": [{"foodId": FOOD}]})


@pytest.mark.parametrize("stage", ["read", "write", "rollback"])
async def test_cancellation_before_write_or_during_verified_mutation(stage):
    entered = asyncio.Event()
    release = asyncio.Event()
    writes = []
    active = 0

    async def handle(request):
        nonlocal active
        active += 1
        try:
            if request.method == "GET":
                if stage == "read":
                    entered.set()
                    await release.wait()
                return httpx.Response(200, json=ORIGINAL)
            writes.append(json.loads(request.content))
            if (stage == "write" and len(writes) == 1) or (
                stage == "rollback" and len(writes) == 2
            ):
                entered.set()
                await release.wait()
            return httpx.Response(
                200, json={**ORIGINAL, "recipeIngredient": []} if len(writes) == 1 else ORIGINAL
            )
        finally:
            active -= 1

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_ingredients(client, "soup", CHANGES))
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
    assert active == 0
    assert len(writes) == (0 if stage == "read" else 2)


async def test_cancelled_write_cleanup_deadline_is_bounded_and_does_not_retry():
    entered = asyncio.Event()
    writes = []
    active = 0

    async def handle(request):
        nonlocal active
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        active += 1
        writes.append(request)
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(
            update_recipe_ingredients(client, "soup", CHANGES, cleanup_timeout=0.02)
        )
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
    assert active == 0 and len(writes) == 1


async def test_batch_has_five_workers_and_preserves_input_order():
    active = peak = 0
    entered = asyncio.Event()
    release = asyncio.Event()

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
        return httpx.Response(200, json={"slug": slug, "recipeIngredient": []})

    updates = [{"slug": f"r{i}", "ingredients": []} for i in range(9)]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(update_recipe_ingredients_batch(client, updates))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert peak == 5
        finally:
            release.set()
        result = await asyncio.wait_for(task, 2)
    assert result["succeededCount"] == 9 and result["apiRequestCount"] == 18
    assert [item["slug"] for item in result["results"]] == [item["slug"] for item in updates]
    assert peak == 5 and active == 0


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"removeIngredientReferenceIds": [OTHER, OTHER]}, "Duplicate removal"),
        ({"updateIngredients": [{"referenceId": OTHER}]}, "changes no fields"),
        (
            {
                "updateIngredients": [
                    {"referenceId": OTHER, "note": "X"},
                    {"referenceId": OTHER, "note": "Y"},
                ]
            },
            "Duplicate update",
        ),
        (
            {
                "updateIngredients": [{"referenceId": OTHER, "note": "X"}],
                "removeIngredientReferenceIds": [OTHER],
            },
            "both updated and removed",
        ),
        ({"addIngredients": [{"referenceId": OTHER}]}, "already exists"),
        ({"addIngredients": [{"referenceId": REF}, {"referenceId": REF}]}, "among additions"),
        (
            {
                "addIngredients": [{"insertAfterReferenceId": OTHER}],
                "removeIngredientReferenceIds": [OTHER],
            },
            "being removed",
        ),
    ],
)
async def test_invalid_delta_is_collected_before_any_write(changes, message):
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match=message):
            await update_recipe_ingredients(client, "soup", changes)
    assert calls == ["GET"]


async def test_delta_preserves_anchor_order_and_untouched_provider_fields():
    snapshot = {
        **ORIGINAL,
        "recipeIngredient": [
            {**ORIGINAL["recipeIngredient"][0], "providerExtra": {"keep": True}, "title": "Sauce"}
        ],
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=snapshot)
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**snapshot, **writes[-1]})

    changes = {
        "addIngredients": [
            {"note": "after1", "insertAfterReferenceId": OTHER},
            {"note": "before1", "insertBeforeReferenceId": OTHER},
            {"note": "after2", "insertAfterReferenceId": OTHER},
            {"note": "before2", "insertBeforeReferenceId": OTHER},
            {"note": "last"},
        ]
    }
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_ingredients(client, "soup", changes)
    rows = result["recipeIngredient"]
    assert [row["note"] for row in rows] == [
        "before1",
        "before2",
        "Keep",
        "after1",
        "after2",
        "last",
    ]
    assert rows[2] == snapshot["recipeIngredient"][0]
    assert set(writes[0]) == {"recipeIngredient"}


async def test_anyio_level_cancellation_allows_rollback_to_finish():
    entered = asyncio.Event()
    release = asyncio.Event()
    writes = []

    async def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=ORIGINAL)
        writes.append(json.loads(request.content))
        if len(writes) == 1:
            entered.set()
            await release.wait()
            return httpx.Response(200, json={**ORIGINAL, "recipeIngredient": []})
        return httpx.Response(200, json=ORIGINAL)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        async with anyio.create_task_group() as group:
            group.start_soon(update_recipe_ingredients, client, "soup", CHANGES)
            await asyncio.wait_for(entered.wait(), 2)
            group.cancel_scope.cancel()
            release.set()
    assert len(writes) == 2


@pytest.mark.parametrize(
    "updates",
    [
        [],
        [{"slug": f"r{i}", "ingredients": []} for i in range(26)],
        [{"slug": " ", "ingredients": []}],
    ],
)
async def test_batch_shape_rejected_before_requests(updates):
    def handle(request):
        pytest.fail("No request should be made")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await update_recipe_ingredients_batch(client, updates)
