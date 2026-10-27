from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from icu import Collator, Locale  # type: ignore[import-untyped]

from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.strings import trim


@dataclass(frozen=True)
class MatchField:
    key: str
    is_alias: bool = False
    query_filter_attr: str | None = None


def classify_and_rank(
    query: str, candidates: list[JsonObject], fields: Sequence[MatchField | str]
) -> list[JsonObject]:
    collator = Collator.createInstance(Locale("en_US"))

    def sort_key(value: object) -> bytes:
        return cast(bytes, collator.getSortKey(value if isinstance(value, str) else ""))

    normalized = trim(query).lower()
    specifications = [
        MatchField(field, field == "alias") if isinstance(field, str) else field for field in fields
    ]
    ranked: list[tuple[int, JsonObject]] = []
    for item in candidates:
        best: tuple[int, str, str, str] | None = None
        for index, field in enumerate(specifications):
            if field.is_alias:
                aliases = item.get("aliases")
                values = (
                    [alias.get("name") for alias in aliases if isinstance(alias, dict)]
                    if isinstance(aliases, list)
                    else []
                )
            else:
                values = [item.get(field.key)]
            names = [value for value in values if isinstance(value, str) and trim(value)]
            if field.is_alias:
                names.sort(key=sort_key)
            exact = next((name for name in names if trim(name).lower() == normalized), None)
            substring = next((name for name in names if normalized in trim(name).lower()), None)
            hit = exact if exact is not None else substring
            if hit is None:
                continue
            match_type = "exact" if exact is not None else "substring"
            rank = index + (0 if exact is not None else len(specifications))
            if best is None or rank < best[0]:
                best = (rank, field.key, match_type, hit)
        if best is not None:
            rank, matched_by, match_type, matched_value = best
            ranked.append(
                (
                    rank,
                    {
                        **item,
                        "matchedBy": matched_by,
                        "matchType": match_type,
                        "matchedValue": matched_value,
                    },
                )
            )
    ranked.sort(key=lambda row: (row[0], sort_key(row[1].get("name")), sort_key(row[1].get("id"))))
    return [item for _, item in ranked]
