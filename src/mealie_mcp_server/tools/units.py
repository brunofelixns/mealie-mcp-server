from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import units as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.units import (
    CreateUnitInput,
    DeleteUnitInput,
    GetUnitInput,
    GetUnitMatchesInput,
    GetUnitsInput,
    UpdateUnitInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_units(request: GetUnitsInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_units(state.client, request.search, request.page, request.per_page)
    )


async def get_unit(request: GetUnitInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_unit(state.client, request.unit_id))


async def get_unit_matches(request: GetUnitMatchesInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_unit_matches(state.client, request.queries, request.max_matches_per_query)
    )


async def create_unit(request: CreateUnitInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_unit(state.client, provided_fields(request)))


async def update_unit(request: UpdateUnitInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("unitId")
    return success_result(await api.update_unit(state.client, request.unit_id, changes))


async def delete_unit(request: DeleteUnitInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_unit(state.client, request.unit_id))


def register_units(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_units"], GetUnitsInput, get_units)
    register_contract_tool(server, catalog["get_unit"], GetUnitInput, get_unit)
    register_contract_tool(
        server, catalog["get_unit_matches"], GetUnitMatchesInput, get_unit_matches
    )
    register_contract_tool(server, catalog["create_unit"], CreateUnitInput, create_unit)
    register_contract_tool(server, catalog["update_unit"], UpdateUnitInput, update_unit)
    register_contract_tool(server, catalog["delete_unit"], DeleteUnitInput, delete_unit)
