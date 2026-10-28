from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.mealie.api import shopping_lists as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.shopping_lists import (
    AddRecipeToShoppingListInput,
    CreateShoppingListInput,
    CreateShoppingListItemInput,
    CreateShoppingListItemsBulkInput,
    DeleteShoppingListInput,
    DeleteShoppingListItemInput,
    DeleteShoppingListItemsBulkInput,
    GetShoppingListInput,
    GetShoppingListItemsInput,
    GetShoppingListsInput,
    RemoveRecipeFromShoppingListInput,
    UpdateShoppingListInput,
    UpdateShoppingListItemInput,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def get_shopping_lists(request: GetShoppingListsInput, state: AppState) -> CallToolResult:
    return success_result(
        await api.get_shopping_lists(state.client, request.page, request.per_page)
    )


async def create_shopping_list(request: CreateShoppingListInput, state: AppState) -> CallToolResult:
    return success_result(await api.create_shopping_list(state.client, request.name))


async def get_shopping_list(request: GetShoppingListInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_shopping_list(state.client, request.list_id))


async def update_shopping_list(request: UpdateShoppingListInput, state: AppState) -> CallToolResult:
    data = provided_fields(request)
    data.pop("listId")
    return success_result(await api.update_shopping_list(state.client, request.list_id, data))


async def delete_shopping_list(request: DeleteShoppingListInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_shopping_list(state.client, request.list_id))


async def add_recipe_to_shopping_list(
    request: AddRecipeToShoppingListInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.add_recipe_to_shopping_list(
            state.client, request.list_id, request.recipe_id, request.recipe_increment_quantity
        )
    )


async def remove_recipe_from_shopping_list(
    request: RemoveRecipeFromShoppingListInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.remove_recipe_from_shopping_list(state.client, request.list_id, request.recipe_id)
    )


async def get_shopping_list_items(
    request: GetShoppingListItemsInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.get_shopping_list_items(
            state.client, request.page, request.per_page, request.search
        )
    )


async def create_shopping_list_item(
    request: CreateShoppingListItemInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.create_shopping_list_item(state.client, provided_fields(request))
    )


async def create_shopping_list_items_bulk(
    request: CreateShoppingListItemsBulkInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.create_shopping_list_items_bulk(
            state.client, [provided_fields(item) for item in request.items]
        )
    )


async def update_shopping_list_item(
    request: UpdateShoppingListItemInput, state: AppState
) -> CallToolResult:
    data = provided_fields(request)
    data.pop("itemId")
    return success_result(await api.update_shopping_list_item(state.client, request.item_id, data))


async def delete_shopping_list_item(
    request: DeleteShoppingListItemInput, state: AppState
) -> CallToolResult:
    return success_result(await api.delete_shopping_list_item(state.client, request.item_id))


async def delete_shopping_list_items_bulk(
    request: DeleteShoppingListItemsBulkInput, state: AppState
) -> CallToolResult:
    return success_result(await api.delete_shopping_list_items_bulk(state.client, request.item_ids))


def register_shopping_lists(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["get_shopping_lists"], GetShoppingListsInput, get_shopping_lists
    )
    register_contract_tool(
        server, catalog["create_shopping_list"], CreateShoppingListInput, create_shopping_list
    )
    register_contract_tool(
        server, catalog["get_shopping_list"], GetShoppingListInput, get_shopping_list
    )
    register_contract_tool(
        server, catalog["update_shopping_list"], UpdateShoppingListInput, update_shopping_list
    )
    register_contract_tool(
        server, catalog["delete_shopping_list"], DeleteShoppingListInput, delete_shopping_list
    )
    register_contract_tool(
        server,
        catalog["add_recipe_to_shopping_list"],
        AddRecipeToShoppingListInput,
        add_recipe_to_shopping_list,
    )
    register_contract_tool(
        server,
        catalog["remove_recipe_from_shopping_list"],
        RemoveRecipeFromShoppingListInput,
        remove_recipe_from_shopping_list,
    )
    register_contract_tool(
        server,
        catalog["get_shopping_list_items"],
        GetShoppingListItemsInput,
        get_shopping_list_items,
    )
    register_contract_tool(
        server,
        catalog["create_shopping_list_item"],
        CreateShoppingListItemInput,
        create_shopping_list_item,
    )
    register_contract_tool(
        server,
        catalog["create_shopping_list_items_bulk"],
        CreateShoppingListItemsBulkInput,
        create_shopping_list_items_bulk,
    )
    register_contract_tool(
        server,
        catalog["update_shopping_list_item"],
        UpdateShoppingListItemInput,
        update_shopping_list_item,
    )
    register_contract_tool(
        server,
        catalog["delete_shopping_list_item"],
        DeleteShoppingListItemInput,
        delete_shopping_list_item,
    )
    register_contract_tool(
        server,
        catalog["delete_shopping_list_items_bulk"],
        DeleteShoppingListItemsBulkInput,
        delete_shopping_list_items_bulk,
    )
