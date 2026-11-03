"""Explicit binding for the additional recipe metadata contract."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_metadata import UpdateRecipeMetadataInput
from mealie_mcp_server.services.recipe_metadata import update_recipe_metadata as update_metadata
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def update_recipe_metadata(
    request: UpdateRecipeMetadataInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(await update_metadata(state.client, request.slug, changes))


def register_recipe_metadata(server: FastMCP) -> None:
    register_contract_tool(
        server,
        definitions()["update_recipe_metadata"],
        UpdateRecipeMetadataInput,
        update_recipe_metadata,
    )
