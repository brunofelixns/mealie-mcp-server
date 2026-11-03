"""Explicit handlers for additional native Mealie 3.30 recipe capabilities."""

from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.recipe_advanced import (
    GetRecipeSuggestionsInput,
    ParseRecipeIngredientInput,
    ParseRecipeIngredientsInput,
    SearchRecipesInput,
    UpdateFoodSubstitutionsInput,
    UpdateRecipeIngredientSubstitutionsInput,
    UpdateRecipeInstructionDurationsInput,
)
from mealie_mcp_server.services import recipe_advanced as service
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def search_recipes(request: SearchRecipesInput, state: AppState) -> CallToolResult:
    return success_result(await service.search_recipes(state.client, provided_fields(request)))


async def get_recipe_suggestions(
    request: GetRecipeSuggestionsInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.get_recipe_suggestions(state.client, provided_fields(request))
    )


async def parse_recipe_ingredient(
    request: ParseRecipeIngredientInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.parse_recipe_ingredient(state.client, provided_fields(request))
    )


async def parse_recipe_ingredients(
    request: ParseRecipeIngredientsInput, state: AppState
) -> CallToolResult:
    return success_result(
        await service.parse_recipe_ingredients(state.client, provided_fields(request))
    )


async def update_recipe_ingredient_substitutions(
    request: UpdateRecipeIngredientSubstitutionsInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await service.update_recipe_ingredient_substitutions(state.client, request.slug, changes)
    )


async def update_food_substitutions(
    request: UpdateFoodSubstitutionsInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("foodId")
    return success_result(
        await service.update_food_substitutions(state.client, request.food_id, changes)
    )


async def update_recipe_instruction_durations(
    request: UpdateRecipeInstructionDurationsInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await service.update_recipe_instruction_durations(state.client, request.slug, changes)
    )


def register_recipe_advanced(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["search_recipes"], SearchRecipesInput, search_recipes)
    register_contract_tool(
        server, catalog["get_recipe_suggestions"], GetRecipeSuggestionsInput, get_recipe_suggestions
    )
    register_contract_tool(
        server,
        catalog["parse_recipe_ingredient"],
        ParseRecipeIngredientInput,
        parse_recipe_ingredient,
    )
    register_contract_tool(
        server,
        catalog["parse_recipe_ingredients"],
        ParseRecipeIngredientsInput,
        parse_recipe_ingredients,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_ingredient_substitutions"],
        UpdateRecipeIngredientSubstitutionsInput,
        update_recipe_ingredient_substitutions,
    )
    register_contract_tool(
        server,
        catalog["update_food_substitutions"],
        UpdateFoodSubstitutionsInput,
        update_food_substitutions,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_instruction_durations"],
        UpdateRecipeInstructionDurationsInput,
        update_recipe_instruction_durations,
    )
