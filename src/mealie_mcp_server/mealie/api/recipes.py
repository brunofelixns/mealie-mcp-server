"""Recipe reads and mutations; caller workflows keep their own verification boundaries."""

from collections.abc import Mapping

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import (
    MealieClient,
    ParamValue,
    build_query_string,
    encode_path_segment,
)
from mealie_mcp_server.models.common import UNSET, JsonObject
from mealie_mcp_server.support.concurrency import map_with_concurrency


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie recipe response.")
    return value


async def get_recipes(
    client: MealieClient, params: Mapping[str, ParamValue] | None = None
) -> JsonObject:
    query = build_query_string(params or {})
    return _object(await client.request("GET", "/api/recipes" + ("?" + query if query else "")))


async def get_recipe(client: MealieClient, slug: str) -> JsonObject:
    return _object(await get_recipe_value(client, slug))


async def get_recipe_value(client: MealieClient, slug: str) -> JsonValue:
    """Leave the response shape to audit callers that report malformed details as data."""
    return await client.request("GET", "/api/recipes/" + encode_path_segment(slug, "slug"))


async def get_recipes_batch(client: MealieClient, slugs: list[str]) -> JsonObject:
    async def fetch(slug: str) -> JsonValue:
        try:
            return await get_recipe(client, slug)
        except Exception as error:
            return {"error": str(error)}

    results = await map_with_concurrency(slugs, 4, fetch)
    return dict(zip(slugs, results, strict=True))


async def create_recipe(client: MealieClient, name: str) -> str:
    value = await client.request("POST", "/api/recipes", json={"name": name})
    if not isinstance(value, str):
        raise ValueError("Mealie did not return a recipe slug.")
    return value


async def update_recipe(client: MealieClient, slug: str, data: JsonObject) -> JsonObject:
    return _object(
        await client.request("PUT", "/api/recipes/" + encode_path_segment(slug, "slug"), json=data)
    )


async def duplicate_recipe(client: MealieClient, slug: str, name: str | None = None) -> JsonValue:
    return await client.request(
        "POST",
        "/api/recipes/" + encode_path_segment(slug, "slug") + "/duplicate",
        json={"name": name} if name else UNSET,
    )


async def delete_recipe(client: MealieClient, slug: str) -> JsonValue:
    return await client.request("DELETE", "/api/recipes/" + encode_path_segment(slug, "slug"))


async def patch_recipe(client: MealieClient, slug: str, data: JsonObject) -> JsonObject:
    return _object(
        await client.request(
            "PATCH", "/api/recipes/" + encode_path_segment(slug, "slug"), json=data
        )
    )
