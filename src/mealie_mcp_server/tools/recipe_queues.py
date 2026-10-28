from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult

from mealie_mcp_server.models.inputs.recipe_queues import (
    FindRecipesForIngredientsInput,
    GetRecipesForClassificationInput,
    GetRecipesForDataEnrichmentInput,
    GetRecipesForIngredientParsingInput,
)
from mealie_mcp_server.services import (
    recipe_classification,
    recipe_discovery,
    recipe_enrichment,
    recipe_ingredient_parsing,
)
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


async def find_recipes_for_ingredients(
    request: FindRecipesForIngredientsInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_discovery.find_recipes_for_ingredients(state.client, request)
    )


async def get_recipes_for_classification(
    request: GetRecipesForClassificationInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_classification.get_recipes_for_classification(state.client, request)
    )


async def get_recipes_for_ingredient_parsing(
    request: GetRecipesForIngredientParsingInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_ingredient_parsing.get_recipes_for_ingredient_parsing(state.client, request)
    )


async def get_recipes_for_data_enrichment(
    request: GetRecipesForDataEnrichmentInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_enrichment.get_recipes_for_data_enrichment(state.client, request)
    )


def register_recipe_queues(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server,
        catalog["find_recipes_for_ingredients"],
        FindRecipesForIngredientsInput,
        find_recipes_for_ingredients,
    )
    register_contract_tool(
        server,
        catalog["get_recipes_for_classification"],
        GetRecipesForClassificationInput,
        get_recipes_for_classification,
    )
    register_contract_tool(
        server,
        catalog["get_recipes_for_ingredient_parsing"],
        GetRecipesForIngredientParsingInput,
        get_recipes_for_ingredient_parsing,
    )
    register_contract_tool(
        server,
        catalog["get_recipes_for_data_enrichment"],
        GetRecipesForDataEnrichmentInput,
        get_recipes_for_data_enrichment,
    )
