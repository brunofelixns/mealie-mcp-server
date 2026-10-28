"""Shopping endpoints retain their native bulk, query and body semantics."""

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment, format_params
from mealie_mcp_server.models.common import UNSET, JsonObject, UnsetType

LISTS = "/api/households/shopping/lists"
ITEMS = "/api/households/shopping/items"


def _list_path(list_id: str) -> str:
    return LISTS + "/" + encode_path_segment(list_id, "shopping list ID")


def _item_path(item_id: str) -> str:
    return ITEMS + "/" + encode_path_segment(item_id, "item ID")


async def get_shopping_lists(
    client: MealieClient, page: float | None = None, per_page: float | None = None
) -> JsonValue:
    return await client.request(
        "GET", LISTS, params=list(format_params({"page": page, "perPage": per_page}).items())
    )


async def create_shopping_list(client: MealieClient, name: str) -> JsonValue:
    return await client.request("POST", LISTS, json={"name": name})


async def get_shopping_list(client: MealieClient, list_id: str) -> JsonValue:
    return await client.request("GET", _list_path(list_id))


async def update_shopping_list(client: MealieClient, list_id: str, data: JsonObject) -> JsonValue:
    return await client.request("PUT", _list_path(list_id), json=data)


async def delete_shopping_list(client: MealieClient, list_id: str) -> JsonValue:
    return await client.request("DELETE", _list_path(list_id))


async def add_recipe_to_shopping_list(
    client: MealieClient,
    list_id: str,
    recipe_id: str,
    recipe_increment_quantity: float | None = None,
) -> JsonValue:
    body: JsonObject | UnsetType = (
        {"recipeIncrementQuantity": recipe_increment_quantity}
        if recipe_increment_quantity is not None
        else UNSET
    )
    return await client.request(
        "POST",
        _list_path(list_id) + "/recipe/" + encode_path_segment(recipe_id, "recipe ID"),
        json=body,
    )


async def remove_recipe_from_shopping_list(
    client: MealieClient, list_id: str, recipe_id: str
) -> JsonValue:
    return await client.request(
        "POST",
        _list_path(list_id) + "/recipe/" + encode_path_segment(recipe_id, "recipe ID") + "/delete",
    )


async def get_shopping_list_items(
    client: MealieClient,
    page: float | None = None,
    per_page: float | None = None,
    search: str | None = None,
) -> JsonValue:
    return await client.request(
        "GET",
        ITEMS,
        params=list(format_params({"page": page, "perPage": per_page, "search": search}).items()),
    )


async def create_shopping_list_item(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", ITEMS, json=data)


async def create_shopping_list_items_bulk(
    client: MealieClient, items: list[JsonObject]
) -> JsonValue:
    body: list[JsonValue] = list(items)
    return await client.request("POST", ITEMS + "/create-bulk", json=body)


async def update_shopping_list_item(
    client: MealieClient, item_id: str, data: JsonObject
) -> JsonValue:
    return await client.request("PUT", _item_path(item_id), json=data)


async def delete_shopping_list_item(client: MealieClient, item_id: str) -> JsonValue:
    return await client.request("DELETE", _item_path(item_id))


async def delete_shopping_list_items_bulk(client: MealieClient, item_ids: list[str]) -> JsonValue:
    return await client.request("DELETE", ITEMS, params=[("ids", ",".join(item_ids))])
