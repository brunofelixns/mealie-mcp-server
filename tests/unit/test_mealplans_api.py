import asyncio
import json

import httpx2 as httpx

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.mealplans import (
    create_mealplan_bulk,
    get_mealplan_with_recipes,
    patch_mealplan,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


async def test_bulk_concurrency_order_projection_and_independent_failure():
    active = peak = 0
    calls = []

    async def handle(request):
        nonlocal active, peak
        body = json.loads(request.content)
        calls.append(body)
        active += 1
        peak = max(peak, active)
        index = int(body["title"])
        await asyncio.sleep(0.02 if index == 0 else 0.005)
        active -= 1
        if index == 3:
            return httpx.Response(500, json={"detail": "private body"})
        return httpx.Response(200, json={"id": index, **body, "providerExtra": "excluded"})

    entries = [{"date": "2026-10-28", "entryType": "breakfast", "title": str(i)} for i in range(11)]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await create_mealplan_bulk(client, entries)
    assert len(calls) == 11
    assert 1 < peak <= 4
    assert result["created"] == 10 and result["failed"] == 1
    assert [item["index"] for item in result["results"]] == list(range(11))
    assert result["results"][0]["entry"]["id"] == 0
    assert "providerExtra" not in result["results"][0]["entry"]
    assert result["results"][3] == {"index": 3, "success": False, "error": "Mealie API error 500."}


async def test_patch_runs_complete_delete_then_replace_then_append_phases():
    events = []
    completed_deletes = set()
    completed_replaces = set()
    put_bodies = []

    async def handle(request):
        method, path = request.method, request.url.path
        identifier = path.rsplit("/", 1)[-1]
        events.append(("begin", method, identifier))
        if method == "DELETE":
            await asyncio.sleep(0.005)
            completed_deletes.add(identifier)
            events.append(("end", method, identifier))
            return httpx.Response(204)
        if method == "GET":
            assert completed_deletes == {"d1", "d2"}
            return httpx.Response(
                200,
                json={
                    "id": identifier,
                    "date": "2026-10-28",
                    "entryType": "dinner",
                    "recipeId": "keep",
                    "title": "old",
                    "extra": {"keep": True},
                },
            )
        if method == "PUT":
            body = json.loads(request.content)
            put_bodies.append(body)
            await asyncio.sleep(0.005)
            completed_replaces.add(identifier)
            events.append(("end", method, identifier))
            return httpx.Response(200, json=body)
        assert method == "POST" and completed_replaces == {"r1", "r2"}
        return httpx.Response(200, json={"id": "new", **json.loads(request.content)})

    actions = [
        {"action": "append", "date": "2026-10-29", "entryType": "breakfast"},
        {"action": "replace", "id": "r1", "title": ""},
        {"action": "delete", "id": "d1"},
        {"action": "replace", "id": "r2", "entryType": "lunch"},
        {"action": "delete", "id": "d2"},
    ]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await patch_mealplan(client, actions)
    assert result["summary"] == {"deleted": 2, "replaced": 2, "appended": 1, "failed": 0}
    assert [entry["action"] for entry in result["results"]] == [
        "delete",
        "delete",
        "replace",
        "replace",
        "append",
    ]
    assert [entry.get("id") for entry in result["results"][:4]] == ["d1", "d2", "r1", "r2"]
    assert all(
        body["extra"] == {"keep": True} and body["recipeId"] == "keep" for body in put_bodies
    )
    assert next(body for body in put_bodies if body["id"] == "r1")["entryType"] == "dinner"


async def test_embed_collects_pages_filters_dates_and_deduplicates_references():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/api/households/mealplans":
            assert request.url.params["start_date"] == "2026-10-01"
            assert request.url.params["perPage"] == "100"
            if request.url.params["page"] == "1":
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {"id": 1, "date": "2026-10-28", "recipeId": "r1"},
                            {"id": 2, "date": "2026-10-29", "recipeId": "r1"},
                            {"id": 3, "date": "2026-09-01", "recipeId": "excluded"},
                        ],
                        "total": 1000,
                    },
                )
            return httpx.Response(200, json={"items": [], "total": 1000})
        assert request.url.path == "/api/recipes/r1"
        return httpx.Response(200, json={"slug": "r1", "nutrition": {"keep": True}})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await get_mealplan_with_recipes(client, "2026-10-01", "2026-10-31")
    assert [entry["id"] for entry in result] == [1, 2]
    assert all(entry["recipe"]["nutrition"] == {"keep": True} for entry in result)
    assert len(calls) == 3
