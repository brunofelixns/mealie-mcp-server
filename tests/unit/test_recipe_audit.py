import asyncio
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_audit import (
    audit_recipe,
    classify_ingredient,
    count_ingredient_states,
    scan_audited_recipes,
)
from mealie_mcp_server.support.recipe_scan import ScanCursor, decode_cursor

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("row", "state"),
    [
        ({}, "unparsed"),
        ({"title": "Sauce"}, "section"),
        ({"title": "Sauce", "originalText": "Sauce", "quantity": 0}, "section"),
        ({"title": "Sauce", "originalText": "2 salt"}, "unparsed"),
        ({"title": "Sauce", "note": "salt"}, "unparsed"),
        ({"food": {"id": "eggs"}, "quantity": 2, "unit": None}, "partial"),
        ({"food": {}, "unit": {}, "quantity": 2}, "structured"),
        ({"food": [], "quantity": True}, "structured"),
        ({"food": {"id": "salt"}, "quantity": 0}, "structured"),
        ({"food": {"id": "salt"}, "quantity": "2"}, "structured"),
        ({"food": {"id": "salt"}, "quantity": -1}, "structured"),
    ],
)
def test_schema_only_ingredient_states(row, state):
    assert classify_ingredient(row) == state


def test_sections_are_orthogonal_to_parsing_counts():
    result = count_ingredient_states(
        [
            {"title": "Sauce"},
            {"title": "Dough", "note": "flour"},
            {"food": {}, "quantity": 2},
            {"food": {}, "unit": {}},
        ]
    )
    assert result == {
        "totalCount": 4,
        "structuredCount": 1,
        "partialCount": 1,
        "unparsedCount": 1,
        "sectionCount": 2,
    }


def test_audit_counts_reference_links_without_interpreting_text():
    result = audit_recipe(
        {
            "recipeIngredient": [
                {"referenceId": "known", "title": "Sauce"},
                {"food": {}, "unit": {}, "referenceId": "second"},
            ],
            "recipeInstructions": [
                {
                    "title": "Prepare",
                    "ingredientReferences": [{"referenceId": "known"}, {"referenceId": "missing"}],
                },
                {"ingredientReferences": []},
                {"ingredientReferences": [{"referenceId": "second"}]},
            ],
            "tools": [{}, {}],
            "recipeCategory": [{}],
            "tags": [],
            "image": " image ",
        }
    )
    assert result == {
        "ingredients": {
            "totalCount": 2,
            "structuredCount": 1,
            "partialCount": 0,
            "unparsedCount": 0,
            "sectionCount": 1,
        },
        "instructions": {
            "instructionCount": 3,
            "referencedInstructionCount": 2,
            "referenceCount": 3,
            "danglingReferenceCount": 1,
            "sectionCount": 1,
        },
        "toolCount": 2,
        "categoryCount": 1,
        "tagCount": 0,
        "hasImage": True,
    }


async def test_sparse_deadline_keeps_has_more_and_cursor():
    clock = iter([0.0, 30000.0])
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/recipes":
            return httpx.Response(
                200,
                json={"items": [{"id": "a", "slug": "one", "createdAt": "2026-10-28"}], "total": 1},
            )
        return httpx.Response(200, json={"id": "a", "slug": "one", "recipeIngredient": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await scan_audited_recipes(
            client,
            None,
            25,
            lambda audit: False,
            lambda detail, audit: detail,
            now=lambda: next(clock),
            deadline_ms=20000,
        )
    assert result.items == [] and result.has_more
    assert result.stop_reason == "deadline" and result.scanned_count == 1
    assert decode_cursor(result.next_cursor) == ScanCursor("2026-10-28", "a", 1)
    assert all(method == "GET" for method, _ in calls)


async def test_detail_failure_isolated_and_limit_cursor_tracks_processed_not_prefetched():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/api/recipes":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": str(i), "slug": f"r{i}", "createdAt": "2026-10-28"} for i in range(3)
                    ],
                    "total": 3,
                },
            )
        if request.url.path.endswith("/r0"):
            return httpx.Response(404, json={"detail": "private"})
        return httpx.Response(200, json={"slug": request.url.path.rsplit("/", 1)[-1]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await scan_audited_recipes(
            client, None, 1, lambda audit: True, lambda detail, audit: detail
        )
    assert len(result.items) == len(result.failures) == 1
    assert result.scanned_count == 2
    assert result.has_more and result.stop_reason == "limit"
    assert decode_cursor(result.next_cursor).last_id == "1"
    assert set(calls) == {"/api/recipes", "/api/recipes/r0", "/api/recipes/r1", "/api/recipes/r2"}


@pytest.mark.parametrize("detail", [None, [], "not a recipe"])
async def test_invalid_detail_response_is_failure_data(detail):
    def handle(request):
        if request.url.path == "/api/recipes":
            return httpx.Response(
                200, json={"items": [{"id": "a", "slug": "one", "createdAt": "date"}], "total": 1}
            )
        return httpx.Response(200, content=json.dumps(detail))

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await scan_audited_recipes(
            client, None, 25, lambda audit: True, lambda recipe, audit: recipe
        )
    assert result.items == []
    assert result.failures == [
        {"slug": "one", "id": "a", "error": "Recipe detail response was empty or invalid"}
    ]


async def test_audit_fetches_batches_of_twenty_with_at_most_four_active_reads():
    active = peak = 0
    detail_calls = []
    four_active = asyncio.Event()
    release = asyncio.Event()
    clock = iter([0.0, 30000.0])

    async def handle(request):
        nonlocal active, peak
        assert request.method == "GET"
        if request.url.path == "/api/recipes":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": f"{i:02}", "slug": f"r{i}", "createdAt": "date"} for i in range(30)
                    ],
                    "total": 30,
                },
            )
        active += 1
        peak = max(peak, active)
        detail_calls.append(request.url.path)
        if active == 4:
            four_active.set()
        try:
            await release.wait()
            return httpx.Response(200, json={"slug": request.url.path.rsplit("/", 1)[-1]})
        finally:
            active -= 1

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(
            scan_audited_recipes(
                client,
                None,
                25,
                lambda audit: False,
                lambda recipe, audit: recipe,
                now=lambda: next(clock),
            )
        )
        try:
            await asyncio.wait_for(four_active.wait(), 2)
            assert len(detail_calls) == peak == 4
        finally:
            release.set()
        result = await asyncio.wait_for(task, 2)
    assert peak == 4 and active == 0 and len(detail_calls) == 20
    assert result.scanned_count == 20 and result.has_more
    assert decode_cursor(result.next_cursor) == ScanCursor("date", "19", 1)
