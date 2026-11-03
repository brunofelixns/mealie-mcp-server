"""Explicit collection handlers backed by the lifespan HTTP client."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_collections import (
    CommentIdInput,
    CookbookIdInput,
    CreateCookbookInput,
    CreateRecipeActionInput,
    EmptyInput,
    GetRecipeHouseholdInput,
    ListCollectionsInput,
    RecipeActionIdInput,
    ShareLinkIdInput,
    TimelineEventIdInput,
    TriggerRecipeActionInput,
    UpdateCookbookInput,
    UpdateRecipeActionInput,
)
from mealie_mcp_server.services import recipe_collections as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_cookbooks(request: ListCollectionsInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_cookbooks(state.client, provided_fields(request)))


async def create_cookbook(request: CreateCookbookInput, state: AppState) -> CallToolResult:
    return success_result(await service.create_cookbook(state.client, provided_fields(request)))


async def get_cookbook(request: CookbookIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_cookbook(state.client, request.cookbook_id))


async def update_cookbook(request: UpdateCookbookInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.update_cookbook(
            state.client, request.cookbook_id, provided_fields(request.changes)
        )
    )


async def delete_cookbook(request: CookbookIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.delete_cookbook(state.client, request.cookbook_id))


async def get_recipe_favorites(request: EmptyInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_favorites(state.client))


async def get_recipe_ratings(request: EmptyInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_ratings(state.client))


async def get_recipe_household(request: GetRecipeHouseholdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_household(state.client, request.slug))


async def list_recipe_comments(request: ListCollectionsInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.list_recipe_comments(state.client, provided_fields(request))
    )


async def get_recipe_comment(request: CommentIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_comment(state.client, request.comment_id))


async def get_recipe_timeline_event(
    request: TimelineEventIdInput, state: AppState
) -> CallToolResult:
    return success_result(await service.get_recipe_timeline_event(state.client, request.event_id))


async def get_recipe_share_link(request: ShareLinkIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_share_link(state.client, request.token_id))


async def get_recipe_actions(request: ListCollectionsInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_actions(state.client, provided_fields(request)))


async def create_recipe_action(request: CreateRecipeActionInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.create_recipe_action(state.client, provided_fields(request))
    )


async def get_recipe_action(request: RecipeActionIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_recipe_action(state.client, request.action_id))


async def update_recipe_action(request: UpdateRecipeActionInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.update_recipe_action(
            state.client, request.action_id, provided_fields(request.changes)
        )
    )


async def delete_recipe_action(request: RecipeActionIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.delete_recipe_action(state.client, request.action_id))


async def trigger_recipe_action(
    request: TriggerRecipeActionInput, state: AppState
) -> CallToolResult:
    payload = provided_fields(request)
    payload.pop("actionId")
    payload.pop("slug")
    return success_result(
        await service.trigger_recipe_action(state.client, request.action_id, request.slug, payload)
    )


def register_recipe_collections(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_cookbooks"], ListCollectionsInput, get_cookbooks)
    register_contract_tool(server, catalog["create_cookbook"], CreateCookbookInput, create_cookbook)
    register_contract_tool(server, catalog["get_cookbook"], CookbookIdInput, get_cookbook)
    register_contract_tool(server, catalog["update_cookbook"], UpdateCookbookInput, update_cookbook)
    register_contract_tool(server, catalog["delete_cookbook"], CookbookIdInput, delete_cookbook)
    register_contract_tool(
        server, catalog["get_recipe_favorites"], EmptyInput, get_recipe_favorites
    )
    register_contract_tool(server, catalog["get_recipe_ratings"], EmptyInput, get_recipe_ratings)
    register_contract_tool(
        server, catalog["list_recipe_comments"], ListCollectionsInput, list_recipe_comments
    )
    register_contract_tool(
        server, catalog["get_recipe_comment"], CommentIdInput, get_recipe_comment
    )
    register_contract_tool(
        server,
        catalog["get_recipe_timeline_event"],
        TimelineEventIdInput,
        get_recipe_timeline_event,
    )
    register_contract_tool(
        server, catalog["get_recipe_share_link"], ShareLinkIdInput, get_recipe_share_link
    )
    register_contract_tool(
        server, catalog["get_recipe_actions"], ListCollectionsInput, get_recipe_actions
    )
    register_contract_tool(
        server, catalog["create_recipe_action"], CreateRecipeActionInput, create_recipe_action
    )
    register_contract_tool(
        server, catalog["get_recipe_action"], RecipeActionIdInput, get_recipe_action
    )
    register_contract_tool(
        server, catalog["update_recipe_action"], UpdateRecipeActionInput, update_recipe_action
    )
    register_contract_tool(
        server, catalog["delete_recipe_action"], RecipeActionIdInput, delete_recipe_action
    )
    register_contract_tool(
        server, catalog["trigger_recipe_action"], TriggerRecipeActionInput, trigger_recipe_action
    )
    register_recipe_household(server)


def register_recipe_household(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_recipe_household"], GetRecipeHouseholdInput, get_recipe_household
    )
