from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import mealplans as api
from mealie_mcp_server.models.common import JsonObject, provided_fields
from mealie_mcp_server.models.inputs.mealplans import (
    AppendAction,
    CreateMealplanBulkInput,
    CreateMealplanInput,
    GetAllMealplansInput,
    GetMealplanWithRecipesInput,
    GetTodaysMealplanInput,
    MealplanEntry,
    PatchMealplanInput,
)
from mealie_mcp_server.services import mealplans
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


def _entry(request: MealplanEntry) -> JsonObject:
    data = provided_fields(request)
    data.pop("action", None)
    data["entryType"] = request.entry_type
    return data


async def get_all_mealplans(request: GetAllMealplansInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_mealplans(
            state.client,
            {
                "startDate": request.start_date,
                "endDate": request.end_date,
                "page": request.page,
                "perPage": request.per_page,
            },
        )
    )


async def get_mealplan_with_recipes(
    request: GetMealplanWithRecipesInput, state: AppState
) -> CallToolResult:
    return success_result(
        await mealplans.get_mealplan_with_recipes(
            state.client, request.start_date, request.end_date
        )
    )


async def create_mealplan(request: CreateMealplanInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_mealplan(state.client, _entry(request)))


async def create_mealplan_bulk(request: CreateMealplanBulkInput, state: AppState) -> CallToolResult:
    data = await mealplans.create_mealplan_bulk(
        state.client, [_entry(entry) for entry in request.entries]
    )
    result = success_result(data)
    if data["created"] == 0 and bool(data["failed"]):
        result.is_error = True
    return result


async def get_todays_mealplan(request: GetTodaysMealplanInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_todays_mealplan(state.client))


async def patch_mealplan(request: PatchMealplanInput, state: AppState) -> CallToolResult:
    actions = []
    for action in request.actions:
        data = provided_fields(action)
        if isinstance(action, AppendAction):
            data["entryType"] = action.entry_type
        actions.append(data)
    return success_result(await mealplans.patch_mealplan(state.client, actions))


def register_mealplans(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_all_mealplans"], GetAllMealplansInput, get_all_mealplans
    )
    register_contract_tool(
        server,
        catalog["get_mealplan_with_recipes"],
        GetMealplanWithRecipesInput,
        get_mealplan_with_recipes,
    )
    register_contract_tool(server, catalog["create_mealplan"], CreateMealplanInput, create_mealplan)
    register_contract_tool(
        server, catalog["create_mealplan_bulk"], CreateMealplanBulkInput, create_mealplan_bulk
    )
    register_contract_tool(
        server, catalog["get_todays_mealplan"], GetTodaysMealplanInput, get_todays_mealplan
    )
    register_contract_tool(server, catalog["patch_mealplan"], PatchMealplanInput, patch_mealplan)
