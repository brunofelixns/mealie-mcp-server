"""Mealie meal-plan endpoints, including snake_case date query parameters."""

from collections.abc import Mapping

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import (
    MealieClient,
    ParamValue,
    encode_path_segment,
    format_params,
)
from mealie_mcp_server.models.common import JsonObject

BASE_PATH = "/api/households/mealplans"


def _record(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError("Invalid Mealie mealplan response.")
    return value


async def get_mealplans(
    client: MealieClient, params: Mapping[str, ParamValue] | None = None
) -> JsonObject:
    params = params or {}
    query = list(
        format_params(
            {
                "start_date": params.get("startDate"),
                "end_date": params.get("endDate"),
                "page": params.get("page"),
                "perPage": params.get("perPage"),
            }
        ).items()
    )
    return _record(await client.request("GET", BASE_PATH, params=query))


async def create_mealplan(client: MealieClient, data: JsonObject) -> JsonValue:
    return await client.request("POST", BASE_PATH, json=data)


async def get_todays_mealplan(client: MealieClient) -> JsonValue:
    return await client.request("GET", BASE_PATH + "/today")


async def get_mealplan(client: MealieClient, identifier: str) -> JsonObject:
    return _record(
        await client.request("GET", BASE_PATH + "/" + encode_path_segment(identifier, "id"))
    )


async def update_mealplan(client: MealieClient, identifier: str, data: JsonObject) -> JsonValue:
    return await client.request(
        "PUT", BASE_PATH + "/" + encode_path_segment(identifier, "id"), json=data
    )


async def delete_mealplan(client: MealieClient, identifier: str) -> JsonValue:
    return await client.request("DELETE", BASE_PATH + "/" + encode_path_segment(identifier, "id"))
