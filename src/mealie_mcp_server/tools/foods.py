from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import foods as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.foods import (
    CreateFoodInput,
    DeleteFoodInput,
    GetFoodInput,
    GetFoodMatchesInput,
    GetFoodsInput,
    MergeFoodsInput,
    UpdateFoodInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_foods(request: GetFoodsInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_foods(state.client, request.search, request.page, request.per_page)
    )


async def get_food(request: GetFoodInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_food(state.client, request.food_id))


async def get_food_matches(request: GetFoodMatchesInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_food_matches(state.client, request.queries, request.max_matches_per_query)
    )


async def create_food(request: CreateFoodInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_food(state.client, provided_fields(request)))


async def update_food(request: UpdateFoodInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("foodId")
    return success_result(await api.update_food(state.client, request.food_id, changes))


async def delete_food(request: DeleteFoodInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_food(state.client, request.food_id))


async def merge_foods(request: MergeFoodsInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.merge_foods(state.client, request.from_food_id, request.to_food_id)
    )


def register_foods(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_foods"], GetFoodsInput, get_foods)
    register_contract_tool(server, catalog["get_food"], GetFoodInput, get_food)
    register_contract_tool(
        server, catalog["get_food_matches"], GetFoodMatchesInput, get_food_matches
    )
    register_contract_tool(server, catalog["create_food"], CreateFoodInput, create_food)
    register_contract_tool(server, catalog["update_food"], UpdateFoodInput, update_food)
    register_contract_tool(server, catalog["delete_food"], DeleteFoodInput, delete_food)
    register_contract_tool(server, catalog["merge_foods"], MergeFoodsInput, merge_foods)
