from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import equipment as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.equipment import (
    CreateToolInput,
    DeleteToolInput,
    GetToolInput,
    GetToolMatchesInput,
    GetToolsInput,
    UpdateToolInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_tools(request: GetToolsInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_tools(state.client, request.search, request.page, request.per_page)
    )


async def get_tool(request: GetToolInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_tool(state.client, request.tool_id))


async def get_tool_matches(request: GetToolMatchesInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_tool_matches(state.client, request.queries, request.max_matches_per_query)
    )


async def create_tool(request: CreateToolInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_tool(state.client, request.name))


async def update_tool(request: UpdateToolInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("toolId")
    return success_result(await api.update_tool(state.client, request.tool_id, changes))


async def delete_tool(request: DeleteToolInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_tool(state.client, request.tool_id))


def register_equipment(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_tools"], GetToolsInput, get_tools)
    register_contract_tool(server, catalog["get_tool"], GetToolInput, get_tool)
    register_contract_tool(
        server, catalog["get_tool_matches"], GetToolMatchesInput, get_tool_matches
    )
    register_contract_tool(server, catalog["create_tool"], CreateToolInput, create_tool)
    register_contract_tool(server, catalog["update_tool"], UpdateToolInput, update_tool)
    register_contract_tool(server, catalog["delete_tool"], DeleteToolInput, delete_tool)
