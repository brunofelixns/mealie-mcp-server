"""Provider operations without MCP dependencies, retries or local ownership guesses."""

import base64
import binascii
from uuid import UUID

from pydantic import JsonValue

from mealie_mcp_server.mealie.api.recipes import get_recipe
from mealie_mcp_server.mealie.client import (
    MealieClient,
    ParamValue,
    encode_path_segment,
    format_params,
)
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.recipe_image import RECIPE_IMAGE_MAX_BYTES, validate_image_bytes

TIMELINE = "/api/recipes/timeline/events"
MAX_IMAGE_BASE64_LENGTH = 4 * ((RECIPE_IMAGE_MAX_BYTES + 2) // 3)


async def _recipe_id(client: MealieClient, slug: str) -> str:
    recipe = await get_recipe(client, slug)
    value = recipe.get("id")
    if not isinstance(value, str):
        raise ValueError("Mealie recipe response has no valid recipe ID.")
    try:
        parsed = UUID(value)
    except ValueError:
        raise ValueError("Mealie recipe response has no valid recipe ID.") from None
    if parsed.version != 4:
        raise ValueError("Mealie recipe response has no valid recipe ID.")
    return value


async def get_recipe_comments(client: MealieClient, slug: str) -> JsonValue:
    return await client.request(
        "GET", "/api/recipes/" + encode_path_segment(slug, "slug") + "/comments"
    )


async def create_recipe_comment(client: MealieClient, slug: str, text: str) -> JsonValue:
    recipe_id = await _recipe_id(client, slug)
    return await client.request("POST", "/api/comments", json={"recipeId": recipe_id, "text": text})


async def update_recipe_comment(client: MealieClient, comment_id: str, text: str) -> JsonValue:
    return await client.request(
        "PUT",
        "/api/comments/" + encode_path_segment(comment_id, "comment ID"),
        json={"id": comment_id, "text": text},
    )


async def delete_recipe_comment(client: MealieClient, comment_id: str) -> JsonValue:
    return await client.request(
        "DELETE", "/api/comments/" + encode_path_segment(comment_id, "comment ID")
    )


async def get_recipe_share_links(client: MealieClient, slug: str) -> JsonValue:
    recipe_id = await _recipe_id(client, slug)
    return await client.request("GET", "/api/shared/recipes", params=[("recipe_id", recipe_id)])


async def create_recipe_share_link(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonValue:
    recipe_id = await _recipe_id(client, slug)
    return await client.request(
        "POST", "/api/shared/recipes", json={**changes, "recipeId": recipe_id}
    )


async def delete_recipe_share_link(client: MealieClient, token_id: str) -> JsonValue:
    return await client.request(
        "DELETE", "/api/shared/recipes/" + encode_path_segment(token_id, "token ID")
    )


async def get_recipe_timeline(
    client: MealieClient, slug: str, pagination: dict[str, ParamValue]
) -> JsonValue:
    recipe_id = await _recipe_id(client, slug)
    params = format_params({**pagination, "queryFilter": f"recipeId={recipe_id}"})
    return await client.request("GET", TIMELINE, params=list(params.items()))


async def create_recipe_timeline_event(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonValue:
    recipe_id = await _recipe_id(client, slug)
    return await client.request("POST", TIMELINE, json={**changes, "recipeId": recipe_id})


async def update_recipe_timeline_event(
    client: MealieClient, event_id: str, changes: JsonObject
) -> JsonValue:
    return await client.request(
        "PUT", TIMELINE + "/" + encode_path_segment(event_id, "event ID"), json=changes
    )


async def delete_recipe_timeline_event(client: MealieClient, event_id: str) -> JsonValue:
    return await client.request(
        "DELETE", TIMELINE + "/" + encode_path_segment(event_id, "event ID")
    )


async def set_recipe_timeline_event_image(
    client: MealieClient, event_id: str, payload: str, extension: str | None
) -> JsonValue:
    path = TIMELINE + "/" + encode_path_segment(event_id, "event ID") + "/image"
    if not payload or len(payload) > MAX_IMAGE_BASE64_LENGTH:
        raise ValueError("Image exceeds the 10 MB limit or is empty.")
    try:
        data = base64.b64decode(payload, validate=True)
    except ValueError, binascii.Error:
        raise ValueError("imageBase64 is not valid base64-encoded data.") from None
    detected = validate_image_bytes(data)
    if extension is not None and ("jpg" if extension == "jpeg" else extension) != detected:
        raise ValueError("Image extension does not match its data.")
    return await client.request(
        "PUT",
        path,
        data={"extension": detected},
        files={"image": (f"image.{detected}", data, "application/octet-stream")},
    )
