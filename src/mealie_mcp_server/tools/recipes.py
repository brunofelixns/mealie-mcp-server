from typing import TYPE_CHECKING

from fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes as api
from mealie_mcp_server.models.inputs.recipes import (
    CreateRecipeInput,
    DeleteRecipeInput,
    DuplicateRecipeInput,
    GetRecipeConciseInput,
    GetRecipeDetailedInput,
    GetRecipesBatchInput,
    GetRecipesDetailedBatchInput,
    GetRecipesInput,
)
from mealie_mcp_server.services.taxonomy_resolution import resolve_taxonomy_filter
from mealie_mcp_server.tools.contracts import register_contract_tool
from mealie_mcp_server.tools.helpers import success_result
from mealie_mcp_server.tools.registry import definitions

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState

CONCISE_FIELDS = (
    "name",
    "slug",
    "recipeServings",
    "recipeYieldQuantity",
    "recipeYield",
    "totalTime",
    "rating",
    "recipeIngredient",
    "lastMade",
)


async def get_recipes(request: GetRecipesInput, state: AppState) -> CallToolResult:
    categories = await resolve_taxonomy_filter(state.client, "category", request.categories)
    tags = await resolve_taxonomy_filter(state.client, "tag", request.tags)
    result = await api.get_recipes(
        state.client,
        {
            "search": request.search,
            "page": request.page,
            "perPage": request.per_page,
            "categories": categories,
            "tags": tags,
            "requireAllTags": request.require_all_tags,
            "requireAllCategories": request.require_all_categories,
        },
    )
    return success_result(result)


async def get_recipe_detailed(request: GetRecipeDetailedInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_recipe(state.client, request.slug))


async def get_recipe_concise(request: GetRecipeConciseInput, state: AppState) -> CallToolResult:
    raw = await api.get_recipe(state.client, request.slug)
    return success_result({key: raw[key] for key in CONCISE_FIELDS if key in raw})


async def get_recipes_batch(request: GetRecipesBatchInput, state: AppState) -> CallToolResult:
    return success_result(await api.get_recipes_batch(state.client, request.slugs))


async def get_recipes_detailed_batch(
    request: GetRecipesDetailedBatchInput, state: AppState
) -> CallToolResult:
    return success_result(await api.get_recipes_batch(state.client, request.slugs))


async def create_recipe(request: CreateRecipeInput, state: AppState) -> CallToolResult:
    slug = await api.create_recipe(state.client, request.name)
    result: JsonValue = slug
    if request.ingredients is not None or request.instructions is not None:
        current = await api.get_recipe(state.client, slug)
        updated = dict(current)
        if request.ingredients is not None:
            updated["recipeIngredient"] = [{"note": note} for note in request.ingredients]
        if request.instructions is not None:
            updated["recipeInstructions"] = [{"text": text} for text in request.instructions]
        result = await api.update_recipe(state.client, slug, updated)
    return success_result(result)


async def duplicate_recipe(request: DuplicateRecipeInput, state: AppState) -> CallToolResult:
    return success_result(await api.duplicate_recipe(state.client, request.slug, request.name))


async def delete_recipe(request: DeleteRecipeInput, state: AppState) -> CallToolResult:
    return success_result(await api.delete_recipe(state.client, request.slug))


def register_recipe_core(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["get_recipes"], GetRecipesInput, get_recipes)
    register_contract_tool(
        server, catalog["get_recipe_detailed"], GetRecipeDetailedInput, get_recipe_detailed
    )
    register_contract_tool(
        server, catalog["get_recipe_concise"], GetRecipeConciseInput, get_recipe_concise
    )
    register_contract_tool(
        server, catalog["get_recipes_batch"], GetRecipesBatchInput, get_recipes_batch
    )
    register_contract_tool(
        server,
        catalog["get_recipes_detailed_batch"],
        GetRecipesDetailedBatchInput,
        get_recipes_detailed_batch,
    )
    register_contract_tool(server, catalog["create_recipe"], CreateRecipeInput, create_recipe)
    register_contract_tool(
        server, catalog["duplicate_recipe"], DuplicateRecipeInput, duplicate_recipe
    )
    register_contract_tool(server, catalog["delete_recipe"], DeleteRecipeInput, delete_recipe)
