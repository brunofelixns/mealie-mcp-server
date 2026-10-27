from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment, format_params
from mealie_mcp_server.models.common import JsonObject


async def get_tags(
    client: MealieClient, page: float | None = None, per_page: float | None = None
) -> JsonValue:
    return await client.request(
        "GET",
        "/api/organizers/tags",
        params=list(format_params({"page": page, "perPage": per_page}).items()),
    )


async def get_empty_tags(client: MealieClient) -> JsonValue:
    return await client.request("GET", "/api/organizers/tags/empty")


async def create_tag(client: MealieClient, name: str) -> JsonValue:
    return await client.request("POST", "/api/organizers/tags", json={"name": name})


async def get_tag(client: MealieClient, identifier: str) -> JsonValue:
    return await client.request(
        "GET", "/api/organizers/tags/" + encode_path_segment(identifier, "id")
    )


async def get_tag_by_slug(client: MealieClient, slug: str) -> JsonValue:
    return await client.request(
        "GET", "/api/organizers/tags/slug/" + encode_path_segment(slug, "slug")
    )


async def update_tag(client: MealieClient, identifier: str, data: JsonObject) -> JsonValue:
    return await client.request(
        "PUT", "/api/organizers/tags/" + encode_path_segment(identifier, "id"), json=data
    )


async def delete_tag(client: MealieClient, identifier: str) -> JsonValue:
    return await client.request(
        "DELETE", "/api/organizers/tags/" + encode_path_segment(identifier, "id")
    )
