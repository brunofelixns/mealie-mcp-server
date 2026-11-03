"""Explicit advanced mealplan handlers."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.mealplan_advanced import (
    CreateMealplanEntryInput,
    CreateMealplanRuleInput,
    CreateRandomMealplanEntryInput,
    GetMealplanIcalFeedInput,
    ListMealplanEntriesInput,
    MealplanEntryIdInput,
    MealplanRuleIdInput,
    UpdateMealplanEntryInput,
    UpdateMealplanRuleInput,
)
from mealie_mcp_server.models.inputs.recipe_collections import EmptyInput, ListCollectionsInput
from mealie_mcp_server.services import mealplan_advanced as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def list_mealplan_entries(
    request: ListMealplanEntriesInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.list_mealplan_entries(state.client, provided_fields(request))
    )


async def create_mealplan_entry(
    request: CreateMealplanEntryInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.create_mealplan_entry(state.client, provided_fields(request))
    )


async def get_mealplan_entry(request: MealplanEntryIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_mealplan_entry(state.client, request.entry_id))


async def update_mealplan_entry(
    request: UpdateMealplanEntryInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.update_mealplan_entry(
            state.client, request.entry_id, provided_fields(request.changes)
        )
    )


async def delete_mealplan_entry(request: MealplanEntryIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.delete_mealplan_entry(state.client, request.entry_id))


async def create_random_mealplan_entry(
    request: CreateRandomMealplanEntryInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.create_random_mealplan_entry(state.client, provided_fields(request))
    )


async def get_mealplan_rules(request: ListCollectionsInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_mealplan_rules(state.client, provided_fields(request)))


async def create_mealplan_rule(request: CreateMealplanRuleInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.create_mealplan_rule(state.client, provided_fields(request))
    )


async def get_mealplan_rule(request: MealplanRuleIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_mealplan_rule(state.client, request.rule_id))


async def update_mealplan_rule(request: UpdateMealplanRuleInput, state: AppState) -> CallToolResult:
    return success_result(
        await service.update_mealplan_rule(
            state.client, request.rule_id, provided_fields(request.changes)
        )
    )


async def delete_mealplan_rule(request: MealplanRuleIdInput, state: AppState) -> CallToolResult:
    return success_result(await service.delete_mealplan_rule(state.client, request.rule_id))


async def get_mealplan_ical_token(request: EmptyInput, state: AppState) -> CallToolResult:
    return success_result(await service.get_mealplan_ical_token(state.client))


async def rotate_mealplan_ical_token(request: EmptyInput, state: AppState) -> CallToolResult:
    return success_result(await service.rotate_mealplan_ical_token(state.client))


async def delete_mealplan_ical_token(request: EmptyInput, state: AppState) -> CallToolResult:
    return success_result(await service.delete_mealplan_ical_token(state.client))


async def get_mealplan_ical_feed(
    request: GetMealplanIcalFeedInput, state: AppState
) -> CallToolResult:
    query = provided_fields(request)
    query.pop("token")
    return success_result(await service.get_mealplan_ical_feed(state.client, request.token, query))


def register_mealplan_advanced(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["list_mealplan_entries"], ListMealplanEntriesInput, list_mealplan_entries
    )
    register_contract_tool(
        server, catalog["create_mealplan_entry"], CreateMealplanEntryInput, create_mealplan_entry
    )
    register_contract_tool(
        server, catalog["get_mealplan_entry"], MealplanEntryIdInput, get_mealplan_entry
    )
    register_contract_tool(
        server, catalog["update_mealplan_entry"], UpdateMealplanEntryInput, update_mealplan_entry
    )
    register_contract_tool(
        server, catalog["delete_mealplan_entry"], MealplanEntryIdInput, delete_mealplan_entry
    )
    register_contract_tool(
        server,
        catalog["create_random_mealplan_entry"],
        CreateRandomMealplanEntryInput,
        create_random_mealplan_entry,
    )
    register_contract_tool(
        server, catalog["get_mealplan_rules"], ListCollectionsInput, get_mealplan_rules
    )
    register_contract_tool(
        server, catalog["create_mealplan_rule"], CreateMealplanRuleInput, create_mealplan_rule
    )
    register_contract_tool(
        server, catalog["get_mealplan_rule"], MealplanRuleIdInput, get_mealplan_rule
    )
    register_contract_tool(
        server, catalog["update_mealplan_rule"], UpdateMealplanRuleInput, update_mealplan_rule
    )
    register_contract_tool(
        server, catalog["delete_mealplan_rule"], MealplanRuleIdInput, delete_mealplan_rule
    )
    register_contract_tool(
        server, catalog["get_mealplan_ical_token"], EmptyInput, get_mealplan_ical_token
    )
    register_contract_tool(
        server, catalog["rotate_mealplan_ical_token"], EmptyInput, rotate_mealplan_ical_token
    )
    register_contract_tool(
        server, catalog["delete_mealplan_ical_token"], EmptyInput, delete_mealplan_ical_token
    )
    register_contract_tool(
        server, catalog["get_mealplan_ical_feed"], GetMealplanIcalFeedInput, get_mealplan_ical_feed
    )
