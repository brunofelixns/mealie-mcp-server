from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import tags as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.tags import (
    CreateTagInput,
    DeleteTagInput,
    GetEmptyTagsInput,
    GetTagBySlugInput,
    GetTagInput,
    GetTagsInput,
    UpdateTagInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_tags(request: GetTagsInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_tags(state.client, request.page, request.per_page))


async def get_empty_tags(request: GetEmptyTagsInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_empty_tags(state.client))


async def create_tag(request: CreateTagInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_tag(state.client, request.name))


async def get_tag(request: GetTagInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_tag(state.client, request.tag_id))


async def get_tag_by_slug(request: GetTagBySlugInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_tag_by_slug(state.client, request.tag_slug))


async def update_tag(request: UpdateTagInput, state: AppState) -> CallToolResult:
    data = provided_fields(request)
    data.pop("tagId")
    return success_result(await api.update_tag(state.client, request.tag_id, data))


async def delete_tag(request: DeleteTagInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_tag(state.client, request.tag_id))


def register_tags(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_tags"], GetTagsInput, get_tags)
    register_contract_tool(server, catalog["get_empty_tags"], GetEmptyTagsInput, get_empty_tags)
    register_contract_tool(server, catalog["create_tag"], CreateTagInput, create_tag)
    register_contract_tool(server, catalog["get_tag"], GetTagInput, get_tag)
    register_contract_tool(server, catalog["get_tag_by_slug"], GetTagBySlugInput, get_tag_by_slug)
    register_contract_tool(server, catalog["update_tag"], UpdateTagInput, update_tag)
    register_contract_tool(server, catalog["delete_tag"], DeleteTagInput, delete_tag)
