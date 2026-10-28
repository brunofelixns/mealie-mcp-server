"""User identity and rating operations, with identity state confined to the client."""

import asyncio

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment
from mealie_mcp_server.models.common import JsonObject


async def get_self(client: MealieClient) -> JsonObject:
    value = await client.request("GET", "/api/users/self")
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie user response.")
    return value


async def get_self_user_id(client: MealieClient) -> str:
    async def load() -> str:
        user = await get_self(client)
        identifier = user.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("GET /api/users/self returned no user id.")
        return identifier

    def release_failure(task: asyncio.Task[str]) -> None:
        failed = task.cancelled() or task.exception() is not None
        if failed and client.self_user_id_task is task:
            client.self_user_id_task = None

    if client.self_user_id_task is None:
        client.self_user_id_task = asyncio.create_task(load())
        client.self_user_id_task.add_done_callback(release_failure)
    return await asyncio.shield(client.self_user_id_task)


async def update_user_rating(
    client: MealieClient, user_id: str, slug: str, update: JsonObject
) -> None:
    await client.request(
        "POST",
        "/api/users/"
        + encode_path_segment(user_id, "user ID")
        + "/ratings/"
        + encode_path_segment(slug, "slug"),
        json=update,
    )


async def get_self_rating(client: MealieClient, recipe_id: str) -> JsonObject:
    value = await client.request(
        "GET", "/api/users/self/ratings/" + encode_path_segment(recipe_id, "recipe ID")
    )
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie rating response.")
    return value
