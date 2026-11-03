"""Bounded recipe media reads resolved from Mealie's own current identities."""

import base64
from email.message import Message
from uuid import UUID

from mealie_mcp_server.mealie.api.recipes import get_recipe
from mealie_mcp_server.mealie.client import BinaryResponse, MealieClient, encode_path_segment
from mealie_mcp_server.models.common import JsonObject

MAX_MEDIA_BYTES = 20 * 1024 * 1024


def _identity(value: object) -> str:
    try:
        parsed = UUID(value) if isinstance(value, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.version != 4:
        raise ValueError("Mealie returned an invalid recipe identity.")
    return str(parsed)


def binary_file_result(response: BinaryResponse, fallback: str) -> JsonObject:
    message = Message()
    message["content-disposition"] = response.content_disposition or ""
    filename = message.get_filename() or fallback
    if (
        filename in {".", ".."}
        or len(filename) > 255
        or any(char in filename for char in ("/", "\\"))
        or any(ord(char) < 32 or ord(char) == 127 for char in filename)
    ):
        filename = fallback
    return {
        "filename": filename,
        "mediaType": response.content_type,
        "size": len(response.content),
        "dataBase64": base64.b64encode(response.content).decode("ascii"),
    }


async def get_recipe_assets(client: MealieClient, slug: str) -> JsonObject:
    recipe = await get_recipe(client, slug)
    return {key: recipe[key] for key in ("id", "slug", "updatedAt", "assets") if key in recipe}


async def download_recipe_asset(client: MealieClient, slug: str, file_name: str) -> JsonObject:
    encoded_name = encode_path_segment(file_name, "asset file name")
    recipe = await get_recipe(client, slug)
    recipe_id = _identity(recipe.get("id"))
    assets = recipe.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Mealie returned an invalid recipe assets collection.")
    matches = [row for row in assets if isinstance(row, dict) and row.get("fileName") == file_name]
    if len(matches) != 1:
        raise ValueError("Asset is missing or ambiguous on the selected recipe.")
    response = await client.get_binary(
        f"/api/media/recipes/{recipe_id}/assets/{encoded_name}", max_bytes=MAX_MEDIA_BYTES
    )
    return binary_file_result(response, file_name)


async def download_recipe_image(client: MealieClient, slug: str, file_name: str) -> JsonObject:
    recipe = await get_recipe(client, slug)
    recipe_id = _identity(recipe.get("id"))
    response = await client.get_binary(
        f"/api/media/recipes/{recipe_id}/images/" + encode_path_segment(file_name),
        max_bytes=MAX_MEDIA_BYTES,
    )
    return binary_file_result(response, file_name)


async def download_recipe_timeline_image(
    client: MealieClient, slug: str, event_id: str, file_name: str
) -> JsonObject:
    recipe = await get_recipe(client, slug)
    recipe_id = _identity(recipe.get("id"))
    encoded_event = encode_path_segment(event_id, "event ID")
    event = await client.request("GET", "/api/recipes/timeline/events/" + encoded_event)
    if not isinstance(event, dict) or event.get("recipeId") != recipe_id:
        raise ValueError("Timeline event does not belong to the selected recipe.")
    response = await client.get_binary(
        f"/api/media/recipes/{recipe_id}/images/timeline/{encoded_event}/"
        + encode_path_segment(file_name),
        max_bytes=MAX_MEDIA_BYTES,
    )
    return binary_file_result(response, file_name)


async def get_shared_recipe(client: MealieClient, token_id: str) -> JsonObject:
    result = await client.request(
        "GET", "/api/recipes/shared/" + encode_path_segment(token_id, "share token")
    )
    if not isinstance(result, dict):
        raise ValueError("Mealie returned an invalid shared recipe.")
    return result


async def download_shared_recipe(client: MealieClient, token_id: str) -> JsonObject:
    response = await client.get_binary(
        "/api/recipes/shared/" + encode_path_segment(token_id, "share token") + "/zip",
        max_bytes=MAX_MEDIA_BYTES,
    )
    return binary_file_result(response, "shared-recipe.zip")
