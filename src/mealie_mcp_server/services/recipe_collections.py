"""Native collection operations; permissions and failures belong to Mealie."""

from typing import cast
from uuid import UUID

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import (
    MealieClient,
    ParamValue,
    encode_path_segment,
    scalar_string,
)
from mealie_mcp_server.models.common import JsonObject

COOKBOOKS = "/api/households/cookbooks"
ACTIONS = "/api/households/recipe-actions"


def query_pairs(values: JsonObject) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, list):
            pairs.extend((key, str(item)) for item in value)
        else:
            scalar = cast(ParamValue, value)
            if isinstance(scalar, (str, int, float, bool)):
                pairs.append((key, scalar_string(scalar)))
    return pairs


def object_response(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie object response.")
    return value


async def update_preserving(client: MealieClient, path: str, changes: JsonObject) -> JsonObject:
    current = object_response(await client.request("GET", path))
    merged = {**current, **changes}
    result = object_response(await client.request("PUT", path, json=merged))
    if any(key not in result or result[key] != value for key, value in changes.items()):
        raise ValueError(
            "Mealie response did not retain the requested changes; do not replay the write."
        )
    return result


async def get_cookbooks(client: MealieClient, query: JsonObject) -> JsonValue:
    return await client.request("GET", COOKBOOKS, params=query_pairs(query))


async def create_cookbook(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", COOKBOOKS, json=data)


async def get_cookbook(client: MealieClient, cookbook_id: str) -> JsonValue:
    return await client.request("GET", f"{COOKBOOKS}/{encode_path_segment(cookbook_id)}")


async def _resolve_cookbook(client: MealieClient, cookbook_id: str) -> tuple[JsonObject, str]:
    current = object_response(await get_cookbook(client, cookbook_id))
    identifier = current.get("id")
    if not isinstance(identifier, str):
        raise ValueError("Invalid Mealie cookbook identifier.")
    try:
        parsed = UUID(identifier)
    except ValueError:
        raise ValueError("Invalid Mealie cookbook identifier.") from None
    if parsed.version != 4:
        raise ValueError("Invalid Mealie cookbook identifier.")
    # Only GET resolves slugs. Provider PUT/DELETE match their primary UUID.
    return current, f"{COOKBOOKS}/{parsed}"


async def update_cookbook(
    client: MealieClient, cookbook_id: str, changes: JsonObject
) -> JsonObject:
    if "slug" in changes:
        raise ValueError("Cookbook slug is derived by Mealie and cannot be edited.")
    current, path = await _resolve_cookbook(client, cookbook_id)
    result = object_response(await client.request("PUT", path, json={**current, **changes}))
    # Mealie strips names and derives collision-aware slugs from those names.
    # Other fields retain exact requested values, including whitespace and falsy values.
    expected = {
        key: value.strip() if key == "name" and isinstance(value, str) else value
        for key, value in changes.items()
    }
    if any(key not in result or result[key] != value for key, value in expected.items()):
        raise ValueError(
            "Mealie response did not retain the requested changes; do not replay the write."
        )
    return result


async def delete_cookbook(client: MealieClient, cookbook_id: str) -> JsonValue:
    _, path = await _resolve_cookbook(client, cookbook_id)
    return await client.request("DELETE", path)


async def get_recipe_favorites(client: MealieClient) -> JsonValue:
    return await client.request("GET", "/api/users/self/favorites")


async def get_recipe_ratings(client: MealieClient) -> JsonValue:
    return await client.request("GET", "/api/users/self/ratings")


async def get_recipe_household(client: MealieClient, slug: str) -> JsonValue:
    return await client.request(
        "GET", f"/api/households/self/recipes/{encode_path_segment(slug, 'recipe slug')}"
    )


async def list_recipe_comments(client: MealieClient, query: JsonObject) -> JsonValue:
    return await client.request("GET", "/api/comments", params=query_pairs(query))


async def get_recipe_comment(client: MealieClient, comment_id: str) -> JsonValue:
    return await client.request("GET", f"/api/comments/{encode_path_segment(comment_id)}")


async def get_recipe_timeline_event(client: MealieClient, event_id: str) -> JsonValue:
    return await client.request(
        "GET", f"/api/recipes/timeline/events/{encode_path_segment(event_id)}"
    )


async def get_recipe_share_link(client: MealieClient, token_id: str) -> JsonValue:
    return await client.request("GET", f"/api/shared/recipes/{encode_path_segment(token_id)}")


async def get_recipe_actions(client: MealieClient, query: JsonObject) -> JsonValue:
    return await client.request("GET", ACTIONS, params=query_pairs(query))


async def create_recipe_action(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", ACTIONS, json=data)


async def get_recipe_action(client: MealieClient, action_id: str) -> JsonValue:
    return await client.request("GET", f"{ACTIONS}/{encode_path_segment(action_id)}")


async def update_recipe_action(
    client: MealieClient, action_id: str, changes: JsonObject
) -> JsonObject:
    return await update_preserving(client, f"{ACTIONS}/{encode_path_segment(action_id)}", changes)


async def delete_recipe_action(client: MealieClient, action_id: str) -> JsonValue:
    return await client.request("DELETE", f"{ACTIONS}/{encode_path_segment(action_id)}")


async def trigger_recipe_action(
    client: MealieClient, action_id: str, slug: str, data: JsonObject
) -> JsonValue:
    path = f"{ACTIONS}/{encode_path_segment(action_id)}/trigger/{encode_path_segment(slug)}"
    return await client.request("POST", path, json=data)
