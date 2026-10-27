from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment, format_params
from mealie_mcp_server.models.common import JsonObject


async def get_categories(
    client: MealieClient, page: float | None = None, per_page: float | None = None
) -> JsonValue:
    return await client.request(
        "GET",
        "/api/organizers/categories",
        params=list(format_params({"page": page, "perPage": per_page}).items()),
    )


async def get_empty_categories(client: MealieClient) -> JsonValue:
    return await client.request("GET", "/api/organizers/categories/empty")


async def create_category(client: MealieClient, name: str) -> JsonValue:
    return await client.request("POST", "/api/organizers/categories", json={"name": name})


async def get_category(client: MealieClient, identifier: str) -> JsonValue:
    return await client.request(
        "GET", "/api/organizers/categories/" + encode_path_segment(identifier, "id")
    )


async def get_category_by_slug(client: MealieClient, slug: str) -> JsonValue:
    return await client.request(
        "GET", "/api/organizers/categories/slug/" + encode_path_segment(slug, "slug")
    )


async def update_category(client: MealieClient, identifier: str, data: JsonObject) -> JsonValue:
    return await client.request(
        "PUT", "/api/organizers/categories/" + encode_path_segment(identifier, "id"), json=data
    )


async def delete_category(client: MealieClient, identifier: str) -> JsonValue:
    return await client.request(
        "DELETE", "/api/organizers/categories/" + encode_path_segment(identifier, "id")
    )
