from pydantic import JsonValue

from mealie_mcp_server.mealie.api._vocabulary import Vocabulary
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.multi_query_lookup import lookup_candidates

VOCABULARY = Vocabulary(
    "food",
    (
        "id",
        "name",
        "pluralName",
        "description",
        "extras",
        "labelId",
        "aliases",
        "substitutions",
        "householdsWithIngredientFood",
    ),
)


async def get_foods(
    client: MealieClient,
    search: str | None = None,
    page: float | None = None,
    per_page: float | None = None,
) -> JsonValue:
    return await VOCABULARY.list(client, search, page, per_page)


async def get_food(client: MealieClient, food_id: str) -> JsonValue:
    return await VOCABULARY.get(client, food_id)


async def create_food(client: MealieClient, data: JsonObject) -> JsonValue:
    return await VOCABULARY.create(client, data)


async def update_food(client: MealieClient, food_id: str, data: JsonObject) -> JsonValue:
    return await VOCABULARY.update(client, food_id, data)


async def delete_food(client: MealieClient, food_id: str) -> JsonValue:
    return await VOCABULARY.delete(client, food_id)


async def get_food_matches(
    client: MealieClient, queries: list[str], max_matches: int | None = None
) -> JsonObject:
    return await lookup_candidates(client, "food", queries, max_matches)


async def merge_foods(client: MealieClient, from_food_id: str, to_food_id: str) -> JsonValue:
    from mealie_mcp_server.mealie.client import encode_path_segment
    from mealie_mcp_server.mealie.errors import MealieApiError
    from mealie_mcp_server.support.strings import trim

    from_id, to_id = trim(from_food_id), trim(to_food_id)
    if not from_id:
        raise ValueError("fromFoodId is required.")
    if not to_id:
        raise ValueError("toFoodId is required.")
    if from_id == to_id:
        raise ValueError("fromFoodId and toFoodId must be different foods.")
    await get_food(client, from_id)
    await get_food(client, to_id)
    try:
        await client.request("PUT", "/api/foods/merge", json={"fromFood": from_id, "toFood": to_id})
    except Exception as error:
        raise RuntimeError(
            f"Unable to merge food {from_id} into {to_id}. "
            "If shopping list items still reference the from-food, "
            f"Mealie fails the merge; remove those items and retry: {error}"
        ) from error
    try:
        await client.request("GET", "/api/foods/" + encode_path_segment(from_id, "id"))
    except Exception as error:
        if isinstance(error, MealieApiError) and error.status == 404:
            return await get_food(client, to_id)
        raise RuntimeError(
            f"Merged, but unable to verify that food {from_id} is gone: {error}"
        ) from error
    raise RuntimeError(f"Mealie reported a successful merge, but food {from_id} still exists.")
