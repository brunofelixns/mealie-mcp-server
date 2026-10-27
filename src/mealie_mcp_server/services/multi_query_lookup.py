import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, format_params
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.candidate_matching import MatchField, classify_and_rank
from mealie_mcp_server.support.concurrency import map_with_concurrency
from mealie_mcp_server.support.query_filter import (
    build_combined_like_filter,
    sanitize_for_like_filter,
)
from mealie_mcp_server.support.strings import trim, utf16_length

type FetchCandidates = Callable[[str, int], Awaitable[JsonObject]]


class LookupValidationError(ValueError):
    pass


@dataclass
class _Chunk:
    keys: list[str]
    requested: bool
    items: list[JsonObject] = field(default_factory=list)
    truncated: bool = False
    error: str | None = None


async def lookup_with_fetch(
    queries: list[str], fields: Sequence[MatchField], max_matches: int, fetch: FetchCandidates
) -> JsonObject:
    if not queries:
        raise LookupValidationError("At least one query is required.")
    if len(queries) > 25:
        raise LookupValidationError(
            f"At most 25 queries are allowed per call (got {len(queries)})."
        )
    trimmed = [trim(query) for query in queries]
    if any(not query for query in trimmed):
        raise LookupValidationError("Queries cannot be blank.")
    if any(utf16_length(query) > 200 for query in trimmed):
        raise LookupValidationError("Each query must be at most 200 characters.")
    unique: dict[str, str] = {}
    for query in trimmed:
        unique.setdefault(query.lower(), query)
    entries = list(unique.items())
    chunks = [entries[i : i + 10] for i in range(0, len(entries), 10)]

    async def fetch_chunk(chunk: list[tuple[str, str]]) -> _Chunk:
        keys = [key for key, _ in chunk]
        query_filter = build_combined_like_filter(
            [spec.query_filter_attr or spec.key for spec in fields],
            [sanitize_for_like_filter(query) for _, query in chunk],
        )
        if not query_filter:
            return _Chunk(keys, False)
        try:
            page = await fetch(query_filter, 200)
            raw_items, total = page["items"], page["total"]
            if not isinstance(raw_items, list) or not isinstance(total, (int, float)):
                raise ValueError("Invalid Mealie candidate response.")
            items = [item for item in raw_items if isinstance(item, dict)]
            return _Chunk(keys, True, items, total > len(raw_items))
        except Exception as error:
            return _Chunk(keys, True, error=str(error))

    results = await map_with_concurrency(chunks, 4, fetch_chunk)
    candidates: dict[str, JsonObject] = {}
    failed: dict[str, str] = {}
    truncated: set[str] = set()
    for result in results:
        if result.error is not None:
            failed.update(dict.fromkeys(result.keys, result.error))
            continue
        if result.truncated:
            truncated.update(result.keys)
        for item in result.items:
            identifier = item.get("id")
            key = (
                identifier
                if isinstance(identifier, str)
                else json.dumps(item, ensure_ascii=False, separators=(",", ":"))
            )
            candidates[key] = item
    pool = list(candidates.values())
    matches: list[JsonValue] = []
    matched_count = 0
    for query in trimmed:
        key = query.lower()
        if failure := failed.get(key):
            matches.append(
                {
                    "query": query,
                    "items": [],
                    "truncated": False,
                    "error": f"Candidate lookup failed for this query: {failure}",
                }
            )
            continue
        ranked = classify_and_rank(query, pool, fields)
        selected: list[JsonValue] = list(ranked[:max_matches])
        matched_count += bool(selected)
        matches.append(
            {
                "query": query,
                "items": selected,
                "truncated": key in truncated or len(ranked) > max_matches,
            }
        )
    return {
        "matches": matches,
        "queryCount": len(trimmed),
        "uniqueQueryCount": len(unique),
        "matchedCount": matched_count,
        "apiRequestCount": sum(result.requested for result in results),
    }


async def lookup_candidates(
    client: MealieClient,
    kind: Literal["food", "unit", "tool"],
    queries: list[str],
    max_matches: int | None = None,
) -> JsonObject:
    fields = [MatchField("name"), MatchField("pluralName")]
    if kind == "unit":
        fields += [MatchField("abbreviation"), MatchField("pluralAbbreviation")]
    fields += [MatchField("alias", True, "aliases.name")]
    path = {"food": "/api/foods", "unit": "/api/units", "tool": "/api/organizers/tools"}[kind]
    if kind == "tool":
        fields = [MatchField("name"), MatchField("slug")]

    async def fetch(query_filter: str, per_page: int) -> JsonObject:
        response = await client.request(
            "GET",
            path,
            params=list(
                format_params({"queryFilter": query_filter, "perPage": per_page, "page": 1}).items()
            ),
        )
        if not isinstance(response, dict):
            raise ValueError("Invalid Mealie candidate response.")
        return response

    cap = min(25, max(1, max_matches if max_matches is not None else 10))
    return await lookup_with_fetch(queries, fields, cap, fetch)
