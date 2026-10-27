import asyncio
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.candidate_matching import MatchField
from mealie_mcp_server.services.multi_query_lookup import (
    LookupValidationError,
    lookup_candidates,
    lookup_with_fetch,
)

FIELDS = [MatchField("name"), MatchField("alias", True, "aliases.name")]


@pytest.mark.parametrize("queries", [[], ["q"] * 26, ["basil", " "], ["a" * 201], ["🍅" * 101]])
async def test_invalid_queries_do_not_fetch(queries):
    async def fetch(*args):
        pytest.fail("invalid input reached Mealie")

    with pytest.raises(LookupValidationError):
        await lookup_with_fetch(queries, FIELDS, 10, fetch)


async def test_duplicate_queries_preserve_positions_and_filters():
    calls = []

    async def fetch(query_filter, per_page):
        calls.append((query_filter, per_page))
        return {"items": [{"id": "b", "name": "basil"}], "total": 1}

    result = await lookup_with_fetch([" Basil ", "basil", "BASIL", "garlic"], FIELDS, 10, fetch)
    assert calls == [
        (
            '(name LIKE "%Basil%" OR aliases.name LIKE "%Basil%") OR '
            '(name LIKE "%garlic%" OR aliases.name LIKE "%garlic%")',
            200,
        )
    ]
    assert {
        k: result[k] for k in ["queryCount", "uniqueQueryCount", "matchedCount", "apiRequestCount"]
    } == {"queryCount": 4, "uniqueQueryCount": 2, "matchedCount": 3, "apiRequestCount": 1}
    assert [m["query"] for m in result["matches"]] == ["Basil", "basil", "BASIL", "garlic"]
    assert result["matches"][-1] == {"query": "garlic", "items": [], "truncated": False}


async def test_chunking_concurrency_union_deduplication_and_partial_failure():
    active = peak = 0
    calls = []

    async def fetch(filter_value, per_page):
        nonlocal active, peak
        calls.append(filter_value)
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(0.01)
        active -= 1
        if '"%q10%"' in filter_value:
            raise RuntimeError("upstream 500")
        if '"%q20%"' in filter_value:
            return {"items": [{"id": "same", "name": "q0", "new": True}], "total": 1}
        return {
            "items": [{"id": "same", "name": "q0", "new": False}, {"name": "q2"}, {"name": "q2"}],
            "total": 500,
        }

    result = await lookup_with_fetch([f"q{i}" for i in range(25)], FIELDS, 10, fetch)
    assert len(calls) == result["apiRequestCount"] == 3
    assert 1 < peak <= 4
    assert result["matches"][0]["items"][0]["new"] is True
    assert len(result["matches"][2]["items"]) == 1
    assert result["matches"][0]["truncated"] is True
    assert result["matches"][10] == {
        "query": "q10",
        "items": [],
        "truncated": False,
        "error": "Candidate lookup failed for this query: upstream 500",
    }
    assert result["matches"][20]["truncated"] is False


@pytest.mark.parametrize(
    ("count", "total", "cap", "truncated"),
    [(2, 2, 3, False), (3, 3, 3, False), (4, 4, 3, True), (1, 500, 10, True), (0, 0, 10, False)],
)
async def test_truncation_combines_local_cap_and_remote_pagination(count, total, cap, truncated):
    async def fetch(*args):
        return {"items": [{"id": str(i), "name": "basil"} for i in range(count)], "total": total}

    result = await lookup_with_fetch(["basil", "Basil"], FIELDS, cap, fetch)
    assert all(row["truncated"] is truncated for row in result["matches"])
    assert all(len(row["items"]) == min(count, cap) for row in result["matches"])


async def test_sanitized_empty_skips_requests():
    async def fetch(*args):
        pytest.fail("empty filter reached Mealie")

    result = await lookup_with_fetch(['""', "%%", "__"], FIELDS, 10, fetch)
    assert result["apiRequestCount"] == result["matchedCount"] == 0


@pytest.mark.parametrize(
    ("kind", "path", "cap", "expected"),
    [
        ("food", "/api/foods", None, 10),
        ("unit", "/api/units", 30, 25),
        ("tool", "/api/organizers/tools", 0, 1),
    ],
)
async def test_kind_wrapper_uses_exact_endpoint_pool_and_cap(kind, path, cap, expected):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json={"items": [{"id": str(i), "name": "basil"} for i in range(30)], "total": 30}
        )

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(handle)) as client:
        result = await lookup_candidates(client, kind, ["basil"], cap)
    assert calls[0].url.path == path
    assert calls[0].url.params["page"] == "1"
    assert calls[0].url.params["perPage"] == "200"
    assert len(result["matches"][0]["items"]) == expected
    assert result["matches"][0]["truncated"] is True
    json.dumps(result)  # public result contains no implementation objects
