import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.organizer_resolution import (
    compute_delta,
    compute_final,
    resolve_organizer_values,
    resolve_values,
    to_organizer_items,
)

A = {"id": "a", "name": "Dinner", "slug": "dinner"}
B = {"id": "b", "name": "Lunch", "slug": "lunch"}


@pytest.mark.parametrize("create_missing", [False, True])
async def test_client_resolution_fetches_catalog_and_only_creates_when_requested(create_missing):
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [A]})
        return httpx.Response(200, json=B)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(handle)) as client:
        result = await resolve_organizer_values(
            client, "category", ["Dinner", "Lunch"], create_missing=create_missing
        )
    assert calls[0].url.params["perPage"] == "-1"
    assert calls[0].url.path == "/api/organizers/categories"
    assert len(calls) == (2 if create_missing else 1)
    assert result["resolved"] == ([A, B] if create_missing else [A])
    assert result["missing"] == ([] if create_missing else ["Lunch"])


async def test_resolution_priority_deduplication_missing_and_no_implicit_creation():
    async def create(name):
        pytest.fail("unrequested creation")

    collision = {"id": "dinner", "name": "other", "slug": "other"}
    result = await resolve_values(
        [" DINNER ", "A", "dinner", "missing", " "], [A, collision], False, create
    )
    assert result == {"resolved": [collision, A], "created": [], "missing": ["missing"]}


async def test_created_values_are_reused_by_id_slug_and_name():
    created = []

    async def create(name):
        created.append(name)
        return {"id": "new", "name": name, "slug": "new-slug", "extra": 1}

    result = await resolve_values(["New item", "NEW ITEM", "new", "new-slug"], [], True, create)
    assert created == ["New item"]
    assert result == {
        "resolved": [{"id": "new", "name": "New item", "slug": "new-slug"}],
        "created": [{"id": "new", "name": "New item", "slug": "new-slug"}],
        "missing": [],
    }


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("replace", {"final": [B], "added": [B], "removed": [A]}),
        ("merge", {"final": [A, B], "added": [B], "removed": []}),
    ],
)
def test_collection_modes_keep_order_and_do_not_mutate(mode, expected):
    current = [A]
    assert compute_final(mode, current, [B, B]) == expected
    assert current == [A]


def test_delta_only_reports_actual_removals_and_new_additions():
    absent = {"id": "absent", "name": "absent", "slug": "absent"}
    assert compute_delta([A, B], [B, absent], [A, absent]) == {
        "final": [B, absent],
        "added": [absent],
        "removed": [A],
    }


def test_response_projection_and_non_array():
    assert to_organizer_items(None) == []
    assert to_organizer_items([{"id": "a", "name": "A", "slug": "a", "metadata": True}]) == [
        {"id": "a", "name": "A", "slug": "a"}
    ]
