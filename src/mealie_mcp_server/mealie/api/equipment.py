"""Kitchen equipment organizers, including household ownership on rename."""

from typing import NoReturn

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment, format_params
from mealie_mcp_server.mealie.errors import MealieApiError
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.multi_query_lookup import lookup_candidates
from mealie_mcp_server.support.strings import trim

BASE_PATH = "/api/organizers/tools"


def _identifier(value: str) -> str:
    identifier = trim(value)
    if not identifier:
        raise ValueError("toolId is required.")
    return identifier


def _wrap(context: str, error: Exception, identifier: str | None = None) -> NoReturn:
    if identifier is not None and isinstance(error, MealieApiError) and error.status == 404:
        context = f"Tool not found: {identifier}"
    raise RuntimeError(f"{context}: {error}") from error


async def get_tools(
    client: MealieClient,
    search: str | None = None,
    page: float | None = None,
    per_page: float | None = None,
) -> JsonValue:
    try:
        params = list(format_params({"search": search, "page": page, "perPage": per_page}).items())
        return await client.request("GET", BASE_PATH, params=params)
    except Exception as error:
        _wrap("Unable to retrieve tools", error)


async def get_tool(client: MealieClient, tool_id: str) -> JsonValue:
    identifier = _identifier(tool_id)
    try:
        return await client.request("GET", BASE_PATH + "/" + encode_path_segment(identifier, "id"))
    except Exception as error:
        _wrap(f"Unable to retrieve tool {identifier}", error, identifier)


async def create_tool(client: MealieClient, name: str) -> JsonValue:
    name = trim(name)
    if not name:
        raise ValueError("Tool name cannot be empty.")
    try:
        return await client.request("POST", BASE_PATH, json={"name": name})
    except Exception as error:
        _wrap("Unable to create tool", error)


async def update_tool(client: MealieClient, tool_id: str, data: JsonObject) -> JsonValue:
    identifier = _identifier(tool_id)
    if "name" not in data:
        raise ValueError("At least one field must be supplied for an update.")
    raw_name = data["name"]
    name = trim(raw_name) if isinstance(raw_name, str) else ""
    if not name:
        raise ValueError("Tool name cannot be empty.")
    try:
        path = BASE_PATH + "/" + encode_path_segment(identifier, "id")
        existing = await client.request("GET", path)
        if not isinstance(existing, dict):
            raise ValueError("Invalid Mealie tool response.")
        payload = {
            key: existing[key] for key in ("id", "name", "householdsWithTool") if key in existing
        }
        payload["name"] = name
        return await client.request("PUT", path, json=payload)
    except Exception as error:
        _wrap(f"Unable to update tool {identifier}", error, identifier)


async def delete_tool(client: MealieClient, tool_id: str) -> JsonValue:
    identifier = _identifier(tool_id)
    try:
        return await client.request(
            "DELETE", BASE_PATH + "/" + encode_path_segment(identifier, "id")
        )
    except Exception as error:
        _wrap(
            f"Unable to delete tool {identifier}. "
            "Mealie may refuse to delete a tool that cannot be removed",
            error,
            identifier,
        )


async def get_tool_matches(
    client: MealieClient, queries: list[str], max_matches: int | None = None
) -> JsonObject:
    return await lookup_candidates(client, "tool", queries, max_matches)
