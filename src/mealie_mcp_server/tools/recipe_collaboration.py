"""Explicit MCP bindings for recipe collaboration and cooking history."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_collaboration import (
    CreateRecipeCommentInput,
    CreateRecipeShareLinkInput,
    CreateRecipeTimelineEventInput,
    DeleteRecipeCommentInput,
    DeleteRecipeShareLinkInput,
    DeleteRecipeTimelineEventInput,
    GetRecipeCommentsInput,
    GetRecipeShareLinksInput,
    GetRecipeTimelineInput,
    SetRecipeTimelineEventImageInput,
    UpdateRecipeCommentInput,
    UpdateRecipeTimelineEventInput,
)
from mealie_mcp_server.services import recipe_collaboration as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_recipe_comments(request: GetRecipeCommentsInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_comments(state.client, request.slug))


async def create_recipe_comment(
    request: CreateRecipeCommentInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.create_recipe_comment(state.client, request.slug, request.text)
    )


async def update_recipe_comment(
    request: UpdateRecipeCommentInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.update_recipe_comment(state.client, request.comment_id, request.text)
    )


async def delete_recipe_comment(
    request: DeleteRecipeCommentInput, state: AppState
) -> CallToolResult:
    return success_result(await service.delete_recipe_comment(state.client, request.comment_id))


async def get_recipe_share_links(
    request: GetRecipeShareLinksInput, state: AppState
) -> CallToolResult:
    return success_result(await service.get_recipe_share_links(state.client, request.slug))


async def create_recipe_share_link(
    request: CreateRecipeShareLinkInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await service.create_recipe_share_link(state.client, request.slug, changes)
    )


async def delete_recipe_share_link(
    request: DeleteRecipeShareLinkInput, state: AppState
) -> CallToolResult:
    return success_result(await service.delete_recipe_share_link(state.client, request.token_id))


async def get_recipe_timeline(request: GetRecipeTimelineInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.get_recipe_timeline(
            state.client, request.slug, {"page": request.page, "perPage": request.per_page}
        )
    )


async def create_recipe_timeline_event(
    request: CreateRecipeTimelineEventInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await service.create_recipe_timeline_event(state.client, request.slug, changes)
    )


async def update_recipe_timeline_event(
    request: UpdateRecipeTimelineEventInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("eventId")
    return success_result(
        await service.update_recipe_timeline_event(state.client, request.event_id, changes)
    )


async def delete_recipe_timeline_event(
    request: DeleteRecipeTimelineEventInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.delete_recipe_timeline_event(state.client, request.event_id)
    )


async def set_recipe_timeline_event_image(
    request: SetRecipeTimelineEventImageInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.set_recipe_timeline_event_image(
            state.client, request.event_id, request.image_base64, request.extension
        )
    )


def register_recipe_collaboration(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_recipe_comments"], GetRecipeCommentsInput, get_recipe_comments
    )
    register_contract_tool(
        server, catalog["create_recipe_comment"], CreateRecipeCommentInput, create_recipe_comment
    )
    register_contract_tool(
        server, catalog["update_recipe_comment"], UpdateRecipeCommentInput, update_recipe_comment
    )
    register_contract_tool(
        server, catalog["delete_recipe_comment"], DeleteRecipeCommentInput, delete_recipe_comment
    )
    register_contract_tool(
        server, catalog["get_recipe_share_links"], GetRecipeShareLinksInput, get_recipe_share_links
    )
    register_contract_tool(
        server,
        catalog["create_recipe_share_link"],
        CreateRecipeShareLinkInput,
        create_recipe_share_link,
    )
    register_contract_tool(
        server,
        catalog["delete_recipe_share_link"],
        DeleteRecipeShareLinkInput,
        delete_recipe_share_link,
    )
    register_contract_tool(
        server, catalog["get_recipe_timeline"], GetRecipeTimelineInput, get_recipe_timeline
    )
    register_contract_tool(
        server,
        catalog["create_recipe_timeline_event"],
        CreateRecipeTimelineEventInput,
        create_recipe_timeline_event,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_timeline_event"],
        UpdateRecipeTimelineEventInput,
        update_recipe_timeline_event,
    )
    register_contract_tool(
        server,
        catalog["delete_recipe_timeline_event"],
        DeleteRecipeTimelineEventInput,
        delete_recipe_timeline_event,
    )
    register_contract_tool(
        server,
        catalog["set_recipe_timeline_event_image"],
        SetRecipeTimelineEventImageInput,
        set_recipe_timeline_event_image,
    )
