"""Explicit read-only bindings for recipe media and shared recipe downloads."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.inputs.recipe_media import (
    DownloadRecipeAssetInput,
    DownloadRecipeImageInput,
    DownloadRecipeTimelineImageInput,
    DownloadSharedRecipeInput,
    GetRecipeAssetsInput,
    GetSharedRecipeInput,
)
from mealie_mcp_server.services import recipe_media as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_recipe_assets(request: GetRecipeAssetsInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_assets(state.client, request.slug))


async def download_recipe_asset(
    request: DownloadRecipeAssetInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.download_recipe_asset(state.client, request.slug, request.file_name)
    )


async def download_recipe_image(
    request: DownloadRecipeImageInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.download_recipe_image(state.client, request.slug, request.file_name)
    )


async def download_recipe_timeline_image(
    request: DownloadRecipeTimelineImageInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.download_recipe_timeline_image(
            state.client, request.slug, request.event_id, request.file_name
        )
    )


async def get_shared_recipe(request: GetSharedRecipeInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_shared_recipe(state.client, request.token_id))


async def download_shared_recipe(
    request: DownloadSharedRecipeInput, state: AppState
) -> CallToolResult:
    return success_result(await service.download_shared_recipe(state.client, request.token_id))


def register_recipe_media(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_recipe_assets"], GetRecipeAssetsInput, get_recipe_assets
    )
    register_contract_tool(
        server, catalog["download_recipe_asset"], DownloadRecipeAssetInput, download_recipe_asset
    )
    register_contract_tool(
        server, catalog["download_recipe_image"], DownloadRecipeImageInput, download_recipe_image
    )
    register_contract_tool(
        server,
        catalog["download_recipe_timeline_image"],
        DownloadRecipeTimelineImageInput,
        download_recipe_timeline_image,
    )
    register_contract_tool(
        server, catalog["get_shared_recipe"], GetSharedRecipeInput, get_shared_recipe
    )
    register_contract_tool(
        server, catalog["download_shared_recipe"], DownloadSharedRecipeInput, download_shared_recipe
    )
