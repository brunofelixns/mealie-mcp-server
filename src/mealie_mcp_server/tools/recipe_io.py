"""Explicit lifespan-backed native recipe IO handlers."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.inputs.recipe_io import (
    CreateRecipeAssetFromUrlInput,
    ExportRecipeInput,
    GetRecipeExportFormatsInput,
    ImportRecipeFromHtmlOrJsonInput,
    ImportRecipeFromUrlInput,
    ImportRecipeFromZipInput,
    UploadRecipeAssetInput,
)
from mealie_mcp_server.services import recipe_io as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def upload_recipe_asset(request: UploadRecipeAssetInput, state: AppState) -> CallToolResult:
    return success_result(await service.upload_recipe_asset(state.client, request))


async def create_recipe_asset_from_url(
    request: CreateRecipeAssetFromUrlInput, state: AppState
) -> CallToolResult:
    return success_result(await service.create_recipe_asset_from_url(state.client, request))


async def import_recipe_from_url(
    request: ImportRecipeFromUrlInput, state: AppState
) -> CallToolResult:
    return success_result(await service.import_recipe_from_url(state.client, request))


async def import_recipe_from_html_or_json(
    request: ImportRecipeFromHtmlOrJsonInput, state: AppState
) -> CallToolResult:
    return success_result(await service.import_recipe_from_html_or_json(state.client, request))


async def import_recipe_from_zip(
    request: ImportRecipeFromZipInput, state: AppState
) -> CallToolResult:
    return success_result(await service.import_recipe_from_zip(state.client, request))


async def get_recipe_export_formats(
    request: GetRecipeExportFormatsInput, state: AppState
) -> CallToolResult:
    return success_result(await service.get_recipe_export_formats(state.client))


async def export_recipe(request: ExportRecipeInput, state: AppState) -> CallToolResult:
    return success_result(await service.export_recipe(state.client, request))


def register_recipe_io(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["upload_recipe_asset"], UploadRecipeAssetInput, upload_recipe_asset
    )
    register_contract_tool(
        server,
        catalog["create_recipe_asset_from_url"],
        CreateRecipeAssetFromUrlInput,
        create_recipe_asset_from_url,
    )
    register_contract_tool(
        server, catalog["import_recipe_from_url"], ImportRecipeFromUrlInput, import_recipe_from_url
    )
    register_contract_tool(
        server,
        catalog["import_recipe_from_html_or_json"],
        ImportRecipeFromHtmlOrJsonInput,
        import_recipe_from_html_or_json,
    )
    register_contract_tool(
        server, catalog["import_recipe_from_zip"], ImportRecipeFromZipInput, import_recipe_from_zip
    )
    register_contract_tool(
        server,
        catalog["get_recipe_export_formats"],
        GetRecipeExportFormatsInput,
        get_recipe_export_formats,
    )
    register_contract_tool(server, catalog["export_recipe"], ExportRecipeInput, export_recipe)
