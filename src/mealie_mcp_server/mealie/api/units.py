from pydantic import JsonValue

from mealie_mcp_server.mealie.api._vocabulary import Vocabulary
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.multi_query_lookup import lookup_candidates

VOCABULARY = Vocabulary(
    "unit",
    (
        "id",
        "name",
        "pluralName",
        "description",
        "extras",
        "fraction",
        "abbreviation",
        "pluralAbbreviation",
        "useAbbreviation",
        "aliases",
        "standardQuantity",
        "standardUnit",
    ),
)


async def get_units(
    client: MealieClient,
    search: str | None = None,
    page: float | None = None,
    per_page: float | None = None,
) -> JsonValue:
    return await VOCABULARY.list(client, search, page, per_page)


async def get_unit(client: MealieClient, unit_id: str) -> JsonValue:
    return await VOCABULARY.get(client, unit_id)


async def create_unit(client: MealieClient, data: JsonObject) -> JsonValue:
    return await VOCABULARY.create(client, data)


async def update_unit(client: MealieClient, unit_id: str, data: JsonObject) -> JsonValue:
    return await VOCABULARY.update(client, unit_id, data)


async def delete_unit(client: MealieClient, unit_id: str) -> JsonValue:
    return await VOCABULARY.delete(client, unit_id)


async def get_unit_matches(
    client: MealieClient, queries: list[str], max_matches: int | None = None
) -> JsonObject:
    return await lookup_candidates(client, "unit", queries, max_matches)
