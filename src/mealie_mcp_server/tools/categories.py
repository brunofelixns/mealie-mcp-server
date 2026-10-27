from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import categories as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.categories import (
    CreateCategoryInput,
    DeleteCategoryInput,
    GetCategoriesInput,
    GetCategoryBySlugInput,
    GetCategoryInput,
    GetEmptyCategoriesInput,
    UpdateCategoryInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_categories(request: GetCategoriesInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_categories(state.client, request.page, request.per_page))


async def get_empty_categories(request: GetEmptyCategoriesInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_empty_categories(state.client))


async def create_category(request: CreateCategoryInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_category(state.client, request.name))


async def get_category(request: GetCategoryInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_category(state.client, request.category_id))


async def get_category_by_slug(request: GetCategoryBySlugInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_category_by_slug(state.client, request.category_slug))


async def update_category(request: UpdateCategoryInput, state: AppState) -> CallToolResult:
    data = provided_fields(request)
    data.pop("categoryId")
    return success_result(await api.update_category(state.client, request.category_id, data))


async def delete_category(request: DeleteCategoryInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_category(state.client, request.category_id))


def register_categories(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_categories"], GetCategoriesInput, get_categories)
    register_contract_tool(
        server, catalog["get_empty_categories"], GetEmptyCategoriesInput, get_empty_categories
    )
    register_contract_tool(server, catalog["create_category"], CreateCategoryInput, create_category)
    register_contract_tool(server, catalog["get_category"], GetCategoryInput, get_category)
    register_contract_tool(
        server, catalog["get_category_by_slug"], GetCategoryBySlugInput, get_category_by_slug
    )
    register_contract_tool(server, catalog["update_category"], UpdateCategoryInput, update_category)
    register_contract_tool(server, catalog["delete_category"], DeleteCategoryInput, delete_category)
