"""Explicit MCP recipe note handlers using the lifespan client."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_notes import (
    AddRecipeNoteInput,
    DeleteRecipeNoteInput,
    GetRecipeNotesInput,
    UpdateRecipeNoteInput,
)
from mealie_mcp_server.services import recipe_notes as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_recipe_notes(request: GetRecipeNotesInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_notes(state.client, request.slug))


async def add_recipe_note(request: AddRecipeNoteInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(await service.add_recipe_note(state.client, request.slug, changes))


async def update_recipe_note(request: UpdateRecipeNoteInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(await service.update_recipe_note(state.client, request.slug, changes))


async def delete_recipe_note(request: DeleteRecipeNoteInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(await service.delete_recipe_note(state.client, request.slug, changes))


def register_recipe_notes(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_recipe_notes"], GetRecipeNotesInput, get_recipe_notes
    )
    register_contract_tool(server, catalog["add_recipe_note"], AddRecipeNoteInput, add_recipe_note)
    register_contract_tool(
        server, catalog["update_recipe_note"], UpdateRecipeNoteInput, update_recipe_note
    )
    register_contract_tool(
        server, catalog["delete_recipe_note"], DeleteRecipeNoteInput, delete_recipe_note
    )
