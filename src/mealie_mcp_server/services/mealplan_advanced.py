"""Advanced native planning operations with field-preserving PUTs."""

import base64

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.mealplan_advanced import validate_week
from mealie_mcp_server.services.recipe_collections import (
    object_response,
    query_pairs,
    update_preserving,
)

ENTRIES = "/api/households/mealplans"
RULES = f"{ENTRIES}/rules"
ICAL = f"{ENTRIES}/ical"


async def list_mealplan_entries(client: MealieClient, query: JsonObject) -> JsonValue:
    return await client.request("GET", ENTRIES, params=query_pairs(query))


async def create_mealplan_entry(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", ENTRIES, json=data)


async def get_mealplan_entry(client: MealieClient, entry_id: int) -> JsonValue:
    return await client.request("GET", f"{ENTRIES}/{entry_id}")


async def update_mealplan_entry(
    client: MealieClient, entry_id: int, changes: JsonObject
) -> JsonObject:
    path = f"{ENTRIES}/{entry_id}"
    current = object_response(await client.request("GET", path))
    merged = {**current, **changes}
    start, end = merged.get("date"), merged.get("endDate")
    if not isinstance(start, str) or (end is not None and not isinstance(end, str)):
        raise ValueError("Invalid Mealie mealplan dates.")
    validate_week(start, end)
    result = object_response(await client.request("PUT", path, json=merged))
    if any(key not in result or result[key] != value for key, value in changes.items()):
        raise ValueError(
            "Mealie response did not retain the requested changes; do not replay the write."
        )
    return result


async def delete_mealplan_entry(client: MealieClient, entry_id: int) -> JsonValue:
    return await client.request("DELETE", f"{ENTRIES}/{entry_id}")


async def create_random_mealplan_entry(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", f"{ENTRIES}/random", json=data)


async def get_mealplan_rules(client: MealieClient, query: JsonObject) -> JsonValue:
    return await client.request("GET", RULES, params=query_pairs(query))


async def create_mealplan_rule(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", RULES, json=data)


async def get_mealplan_rule(client: MealieClient, rule_id: str) -> JsonValue:
    return await client.request("GET", f"{RULES}/{encode_path_segment(rule_id)}")


async def update_mealplan_rule(
    client: MealieClient, rule_id: str, changes: JsonObject
) -> JsonObject:
    return await update_preserving(client, f"{RULES}/{encode_path_segment(rule_id)}", changes)


async def delete_mealplan_rule(client: MealieClient, rule_id: str) -> JsonValue:
    return await client.request("DELETE", f"{RULES}/{encode_path_segment(rule_id)}")


async def get_mealplan_ical_token(client: MealieClient) -> JsonValue:
    return await client.request("GET", ICAL)


async def rotate_mealplan_ical_token(client: MealieClient) -> JsonValue:
    return await client.request("POST", ICAL)


async def delete_mealplan_ical_token(client: MealieClient) -> JsonValue:
    return await client.request("DELETE", ICAL)


async def get_mealplan_ical_feed(client: MealieClient, token: str, query: JsonObject) -> JsonObject:
    response = await client.get_binary(
        f"{ICAL}/{encode_path_segment(token)}", params=query_pairs(query), max_bytes=5 * 1024 * 1024
    )
    return {
        "filename": "mealplan.ics",
        "mediaType": response.content_type,
        "size": len(response.content),
        "dataBase64": base64.b64encode(response.content).decode(),
    }
