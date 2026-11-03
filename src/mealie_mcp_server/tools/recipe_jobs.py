"""Explicit MCP bindings for native recipe jobs and safe numeric progress."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context
from mcp.types import CallToolResult

from mealie_mcp_server.models.inputs.recipe_io import (
    ImportRecipeFromHtmlOrJsonInput,
    ImportRecipeFromUrlInput,
)
from mealie_mcp_server.models.inputs.recipe_jobs import (
    DeleteRecipesBulkInput,
    DownloadRecipeBulkExportInput,
    ExportRecipesBulkInput,
    GetRecipeBulkExportsInput,
    GetRecipeImportReportInput,
    GetRecipeImportReportsInput,
    ImportRecipesFromUrlsInput,
    ImportRecipeWithAiInput,
    PreviewRecipeFromUrlInput,
    PurgeRecipeBulkExportsInput,
    UpdateRecipeMetadataBatchInput,
)
from mealie_mcp_server.services import recipe_jobs as jobs
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def _report_progress(count: int) -> None:
    await get_context().report_progress(progress=count, message="Mealie import in progress.")


async def preview_recipe_from_url(
    request: PreviewRecipeFromUrlInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.preview_recipe_from_url(state.client, request))


async def import_recipe_with_ai(
    request: ImportRecipeWithAiInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.import_recipe_with_ai(state.client, request))


async def import_recipe_from_url_with_progress(
    request: ImportRecipeFromUrlInput, state: AppState
) -> CallToolResult:
    return success_result(
        await jobs.import_recipe_from_url_with_progress(state.client, request, _report_progress)
    )


async def import_recipe_from_html_or_json_with_progress(
    request: ImportRecipeFromHtmlOrJsonInput, state: AppState
) -> CallToolResult:
    return success_result(
        await jobs.import_recipe_from_html_or_json_with_progress(
            state.client, request, _report_progress
        )
    )


async def import_recipe_with_ai_with_progress(
    request: ImportRecipeWithAiInput, state: AppState
) -> CallToolResult:
    return success_result(
        await jobs.import_recipe_with_ai_with_progress(state.client, request, _report_progress)
    )


async def import_recipes_from_urls(
    request: ImportRecipesFromUrlsInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.import_recipes_from_urls(state.client, request))


async def get_recipe_import_reports(
    request: GetRecipeImportReportsInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.get_recipe_import_reports(state.client))


async def get_recipe_import_report(
    request: GetRecipeImportReportInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.get_recipe_import_report(state.client, request))


async def delete_recipes_bulk(request: DeleteRecipesBulkInput, state: AppState) -> CallToolResult:
    return success_result(await jobs.delete_recipes_bulk(state.client, request))


async def export_recipes_bulk(request: ExportRecipesBulkInput, state: AppState) -> CallToolResult:
    return success_result(await jobs.export_recipes_bulk(state.client, request))


async def get_recipe_bulk_exports(
    request: GetRecipeBulkExportsInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.get_recipe_bulk_exports(state.client))


async def download_recipe_bulk_export(
    request: DownloadRecipeBulkExportInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.download_recipe_bulk_export(state.client, request))


async def purge_recipe_bulk_exports(
    request: PurgeRecipeBulkExportsInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.purge_recipe_bulk_exports(state.client))


async def update_recipe_metadata_batch(
    request: UpdateRecipeMetadataBatchInput, state: AppState
) -> CallToolResult:
    return success_result(await jobs.update_recipe_metadata_batch(state.client, request))


def register_recipe_jobs(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server,
        catalog["preview_recipe_from_url"],
        PreviewRecipeFromUrlInput,
        preview_recipe_from_url,
    )
    register_contract_tool(
        server, catalog["import_recipe_with_ai"], ImportRecipeWithAiInput, import_recipe_with_ai
    )
    register_contract_tool(
        server,
        catalog["import_recipe_from_url_with_progress"],
        ImportRecipeFromUrlInput,
        import_recipe_from_url_with_progress,
    )
    register_contract_tool(
        server,
        catalog["import_recipe_from_html_or_json_with_progress"],
        ImportRecipeFromHtmlOrJsonInput,
        import_recipe_from_html_or_json_with_progress,
    )
    register_contract_tool(
        server,
        catalog["import_recipe_with_ai_with_progress"],
        ImportRecipeWithAiInput,
        import_recipe_with_ai_with_progress,
    )
    register_contract_tool(
        server,
        catalog["import_recipes_from_urls"],
        ImportRecipesFromUrlsInput,
        import_recipes_from_urls,
    )
    register_contract_tool(
        server,
        catalog["get_recipe_import_reports"],
        GetRecipeImportReportsInput,
        get_recipe_import_reports,
    )
    register_contract_tool(
        server,
        catalog["get_recipe_import_report"],
        GetRecipeImportReportInput,
        get_recipe_import_report,
    )
    register_contract_tool(
        server, catalog["delete_recipes_bulk"], DeleteRecipesBulkInput, delete_recipes_bulk
    )
    register_contract_tool(
        server, catalog["export_recipes_bulk"], ExportRecipesBulkInput, export_recipes_bulk
    )
    register_contract_tool(
        server,
        catalog["get_recipe_bulk_exports"],
        GetRecipeBulkExportsInput,
        get_recipe_bulk_exports,
    )
    register_contract_tool(
        server,
        catalog["download_recipe_bulk_export"],
        DownloadRecipeBulkExportInput,
        download_recipe_bulk_export,
    )
    register_contract_tool(
        server,
        catalog["purge_recipe_bulk_exports"],
        PurgeRecipeBulkExportsInput,
        purge_recipe_bulk_exports,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_metadata_batch"],
        UpdateRecipeMetadataBatchInput,
        update_recipe_metadata_batch,
    )
