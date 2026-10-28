from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from mcp.types import CallToolResult
from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes as api
from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.ratings_dates import (
    MarkRecipeLastMadeInput,
    SetRecipeRatingInput,
)
from mealie_mcp_server.models.inputs.recipe_image import (
    SetRecipeImageFromFileInput,
    SetRecipeImageFromUrlInput,
    SetRecipeImageInput,
)
from mealie_mcp_server.models.inputs.recipe_ingredients import (
    UpdateRecipeIngredientsBatchInput,
    UpdateRecipeIngredientsInput,
)
from mealie_mcp_server.models.inputs.recipe_instructions import (
    UpdateRecipeInstructionsBatchInput,
    UpdateRecipeInstructionsInput,
)
from mealie_mcp_server.models.inputs.recipe_taxonomy import (
    PatchRecipeInput,
    UpdateRecipeTaxonomyBatchInput,
    UpdateRecipeTaxonomyInput,
    UpdateRecipeToolsBatchInput,
    UpdateRecipeToolsInput,
)
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
from mealie_mcp_server.services import (
    recipe_equipment,
    recipe_ingredients,
    recipe_instructions,
    recipe_rating,
    recipe_taxonomy,
)
from mealie_mcp_server.services.last_made import resolve_last_made_timestamp
from mealie_mcp_server.services.taxonomy_resolution import resolve_taxonomy_filter
from mealie_mcp_server.support import recipe_image
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


async def patch_recipe(request: PatchRecipeInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_taxonomy.patch_recipe_with_taxonomy(state.client, request.slug, changes)
    )


async def update_recipe_taxonomy(
    request: UpdateRecipeTaxonomyInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_taxonomy.update_recipe_taxonomy(state.client, request.slug, changes)
    )


async def update_recipe_taxonomy_batch(
    request: UpdateRecipeTaxonomyBatchInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_taxonomy.update_recipe_taxonomy_batch(
            state.client, [provided_fields(item) for item in request.updates]
        )
    )


async def update_recipe_tools(request: UpdateRecipeToolsInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_equipment.update_recipe_equipment(state.client, request.slug, changes)
    )


async def update_recipe_tools_batch(
    request: UpdateRecipeToolsBatchInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_equipment.update_recipe_equipment_batch(
            state.client, [provided_fields(item) for item in request.updates]
        )
    )


def register_recipe_organizers(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(server, catalog["patch_recipe"], PatchRecipeInput, patch_recipe)
    register_contract_tool(
        server, catalog["update_recipe_taxonomy"], UpdateRecipeTaxonomyInput, update_recipe_taxonomy
    )
    register_contract_tool(
        server,
        catalog["update_recipe_taxonomy_batch"],
        UpdateRecipeTaxonomyBatchInput,
        update_recipe_taxonomy_batch,
    )
    register_contract_tool(
        server, catalog["update_recipe_tools"], UpdateRecipeToolsInput, update_recipe_tools
    )
    register_contract_tool(
        server,
        catalog["update_recipe_tools_batch"],
        UpdateRecipeToolsBatchInput,
        update_recipe_tools_batch,
    )


async def update_recipe_ingredients(
    request: UpdateRecipeIngredientsInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_ingredients.update_recipe_ingredients(state.client, request.slug, changes)
    )


async def update_recipe_ingredients_batch(
    request: UpdateRecipeIngredientsBatchInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_ingredients.update_recipe_ingredients_batch(
            state.client, [provided_fields(item) for item in request.updates]
        )
    )


def register_recipe_ingredients(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server,
        catalog["update_recipe_ingredients"],
        UpdateRecipeIngredientsInput,
        update_recipe_ingredients,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_ingredients_batch"],
        UpdateRecipeIngredientsBatchInput,
        update_recipe_ingredients_batch,
    )


async def update_recipe_instructions(
    request: UpdateRecipeInstructionsInput, state: AppState
) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_instructions.update_recipe_instructions(state.client, request.slug, changes)
    )


async def update_recipe_instructions_batch(
    request: UpdateRecipeInstructionsBatchInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_instructions.update_recipe_instructions_batch(
            state.client, [provided_fields(item) for item in request.updates]
        )
    )


def register_recipe_instructions(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server,
        catalog["update_recipe_instructions"],
        UpdateRecipeInstructionsInput,
        update_recipe_instructions,
    )
    register_contract_tool(
        server,
        catalog["update_recipe_instructions_batch"],
        UpdateRecipeInstructionsBatchInput,
        update_recipe_instructions_batch,
    )


async def set_recipe_image(request: SetRecipeImageInput, state: AppState) -> CallToolResult:
    return success_result(
        await recipe_image.set_recipe_image(
            state.client, request.slug, request.image_base64, request.extension
        )
    )


async def set_recipe_image_from_file(
    request: SetRecipeImageFromFileInput, state: AppState
) -> CallToolResult:
    return success_result(
        await recipe_image.set_recipe_image_from_file(
            state.client, request.slug, provided_fields(request.file)
        )
    )


async def set_recipe_image_from_url(
    request: SetRecipeImageFromUrlInput, state: AppState
) -> CallToolResult:
    return success_result(
        await api.set_recipe_image_from_url(state.client, request.slug, request.image_url)
    )


def register_recipe_images(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["set_recipe_image"], SetRecipeImageInput, set_recipe_image
    )
    register_contract_tool(
        server,
        catalog["set_recipe_image_from_file"],
        SetRecipeImageFromFileInput,
        set_recipe_image_from_file,
    )
    register_contract_tool(
        server,
        catalog["set_recipe_image_from_url"],
        SetRecipeImageFromUrlInput,
        set_recipe_image_from_url,
    )


async def set_recipe_rating(request: SetRecipeRatingInput, state: AppState) -> CallToolResult:
    changes = provided_fields(request)
    changes.pop("slug")
    return success_result(
        await recipe_rating.set_recipe_rating(state.client, request.slug, changes)
    )


async def mark_recipe_last_made(
    request: MarkRecipeLastMadeInput, state: AppState
) -> CallToolResult:
    timestamp = resolve_last_made_timestamp(
        request.timestamp, now=datetime.now(UTC), zone=ZoneInfo(state.settings.tz)
    )
    return success_result(await api.update_recipe_last_made(state.client, request.slug, timestamp))


def register_ratings_dates(server: FastMCP) -> None:
    catalog = definitions()
    register_contract_tool(
        server, catalog["set_recipe_rating"], SetRecipeRatingInput, set_recipe_rating
    )
    register_contract_tool(
        server, catalog["mark_recipe_last_made"], MarkRecipeLastMadeInput, mark_recipe_last_made
    )
