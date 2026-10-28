"""Legacy discovery resolution: exact name, alternate name, then unique search hit."""

import asyncio
from dataclasses import dataclass

from mealie_mcp_server.mealie.api.foods import get_foods
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import to_organizer_item
from mealie_mcp_server.support.recipe_scan import id_string, is_number, to_array
from mealie_mcp_server.support.strings import trim


@dataclass(frozen=True)
class ResolvedIngredient:
    query: str
    food_id: str
    food_name: str
    match_type: str

    def as_json(self) -> JsonObject:
        return {
            "query": self.query,
            "foodId": self.food_id,
            "foodName": self.food_name,
            "matchType": self.match_type,
        }


def _name(row: JsonObject) -> str:
    value = row.get("name")
    return value if isinstance(value, str) else ""


def _choose(
    query: str, candidates: list[JsonObject], match_type: str
) -> ResolvedIngredient | JsonObject:
    if len(candidates) == 1:
        row = candidates[0]
        identifier = row.get("id")
        food_id = id_string(identifier) if is_number(identifier) else to_organizer_item(row)["id"]
        return ResolvedIngredient(query, food_id, _name(row), match_type)
    return {
        "query": query,
        "reason": "ambiguous",
        "candidates": [_name(row) for row in candidates[:8]],
    }


async def resolve_ingredients(
    client: MealieClient, queries: list[str]
) -> tuple[list[ResolvedIngredient], list[JsonObject]]:
    unique = list(dict.fromkeys(value for query in queries if (value := trim(query))))

    async def resolve_one(query: str) -> ResolvedIngredient | JsonObject:
        try:
            page = await get_foods(client, search=query, per_page=25)
            if not isinstance(page, dict):
                raise ValueError("Invalid Mealie food response.")
            candidates = to_array(page.get("items"))
            if not candidates:
                return {"query": query, "reason": "not-found"}
            key = query.lower()
            exact = [row for row in candidates if _name(row).lower() == key]
            if exact:
                return _choose(query, exact, "exact-name")

            def alternate(row: JsonObject) -> bool:
                plural = row.get("pluralName")
                return (
                    isinstance(plural, str)
                    and plural.lower() == key
                    or any(_name(alias).lower() == key for alias in to_array(row.get("aliases")))
                )

            alternate_matches = [row for row in candidates if alternate(row)]
            if alternate_matches:
                return _choose(query, alternate_matches, "exact-alternate-name")
            return _choose(query, candidates, "unique-search-match")
        except Exception as error:
            return {"query": query, "reason": "lookup-failed", "error": str(error)}

    outcomes = await asyncio.gather(*(resolve_one(query) for query in unique))
    return (
        [item for item in outcomes if isinstance(item, ResolvedIngredient)],
        [item for item in outcomes if isinstance(item, dict)],
    )
