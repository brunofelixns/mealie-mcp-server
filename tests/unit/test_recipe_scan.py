import base64
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.support.recipe_scan import (
    InvalidCursorError,
    ScanCursor,
    decode_cursor,
    encode_cursor,
    scan_recipes_stable,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("cursor", "encoded"),
    [
        (
            ScanCursor("2026-10-28T12:00:00Z", "a", 2),
            "eyJ2IjoxLCJsYXN0Q3JlYXRlZEF0IjoiMjAyNi0xMC0yOFQxMjowMDowMFoiLCJsYXN0SWQiOiJhIiwicGFnZSI6Mn0",
        ),
        (
            ScanCursor("créé 🍅", "ñ", 1),
            "eyJ2IjoxLCJsYXN0Q3JlYXRlZEF0IjoiY3LDqcOpIPCfjYUiLCJsYXN0SWQiOiLDsSIsInBhZ2UiOjF9",
        ),
    ],
)
def test_cursor_v1_matches_original_node_bytes(cursor, encoded):
    # Values captured from upstream d027e1b / dist/lib/recipe-scan.js.
    assert encode_cursor(cursor) == encoded
    assert decode_cursor(encoded) == cursor


def payload(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (None, "not an object"),
        (2, "not an object"),
        ([], "version"),
        ({}, "version"),
        ({"v": True}, "version"),
        ({"v": "1"}, "version"),
        ({"v": 1, "lastCreatedAt": "", "lastId": "x", "page": 1}, "lastCreatedAt"),
        ({"v": 1, "lastCreatedAt": "x", "lastId": None, "page": 1}, "lastId"),
        ({"v": 1, "lastCreatedAt": "x", "lastId": "i", "page": True}, "page"),
        ({"v": 1, "lastCreatedAt": "x", "lastId": "i", "page": 0}, "page"),
        ({"v": 1, "lastCreatedAt": "x", "lastId": "i", "page": 1.5}, "page"),
    ],
)
def test_invalid_cursor_shape(value, message):
    with pytest.raises(InvalidCursorError, match=message):
        decode_cursor(payload(value))


def test_cursor_ignores_extra_fields_and_accepts_integral_json_number():
    assert decode_cursor(
        payload({"v": 1.0, "lastCreatedAt": "x", "lastId": "i", "page": 2.0, "extra": "ignored"})
    ) == ScanCursor("x", "i", 2)
    with pytest.raises(InvalidCursorError, match="base64url"):
        decode_cursor("not-json!")


async def test_scan_refetches_cursor_page_sorts_ties_and_keeps_query_contract():
    calls = []
    date = "2026-10-28T12:00:00Z"

    def handle(request):
        calls.append(request)
        assert request.url.params["perPage"] == "50"
        assert request.url.params["orderBy"] == "createdAt"
        assert request.url.params["orderDirection"] == "asc"
        if request.url.params["page"] == "1":
            items = [
                {"id": f"{i:03}", "createdAt": date, "slug": f"r{i}"} for i in reversed(range(50))
            ]
        else:
            items = [{"id": "050", "createdAt": date, "slug": "r50"}]
        return httpx.Response(200, json={"items": items, "total": 51})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = [item async for item in scan_recipes_stable(client, ScanCursor(date, "024", 1))]
    assert [item.id for item in result] == [f"{i:03}" for i in range(25, 51)]
    assert [request.url.params["page"] for request in calls] == ["1", "2"]
    assert result[-1].page == 2


async def test_scan_stops_on_empty_collection():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"items": [], "total": 0})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert [item async for item in scan_recipes_stable(client)] == []
    assert len(calls) == 1


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_cursor_rejects_non_json_numeric_constants(constant):
    raw = '{"v":1,"lastCreatedAt":"x","lastId":"i","page":1,"extra":' + constant + "}"
    token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    with pytest.raises(InvalidCursorError, match="base64url"):
        decode_cursor(token)


async def test_scan_uses_utf16_relational_order_for_non_bmp_ids():
    rows = [{"id": value, "createdAt": "date"} for value in ["\ue000", "🍅"]]

    def handle(request):
        return httpx.Response(200, json={"items": rows})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = [item.id async for item in scan_recipes_stable(client)]
    assert result == ["🍅", "\ue000"]
