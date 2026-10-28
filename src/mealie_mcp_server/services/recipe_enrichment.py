from typing import cast

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject, provided_fields
from mealie_mcp_server.models.inputs.recipe_queues import GetRecipesForDataEnrichmentInput
from mealie_mcp_server.services.recipe_audit import RecipeEnrichmentAudit, scan_audited_recipes
from mealie_mcp_server.services.recipe_classification import compact_context
from mealie_mcp_server.services.recipe_ingredient_parsing import audit_page, compact_ingredient
from mealie_mcp_server.support.recipe_scan import decode_cursor, id_string, string, to_array

DIMENSIONS = (
    "ingredientParsing",
    "ingredientSections",
    "instructionIngredientLinks",
    "tools",
    "categories",
    "tags",
    "image",
)
DEFAULT_FILTERS: JsonObject = {
    "ingredientParsing": "unparsed_or_partial",
    "ingredientSections": False,
    "instructionIngredientLinks": "missing_or_dangling",
    "tools": False,
    "categories": False,
    "tags": False,
    "image": False,
}


def matched_dimensions(filters: JsonObject, audit: RecipeEnrichmentAudit) -> list[str]:
    ingredients, instructions = audit["ingredients"], audit["instructions"]
    unparsed, partial = ingredients["unparsedCount"] > 0, ingredients["partialCount"] > 0
    missing = instructions["instructionCount"] > 0 and instructions["referenceCount"] == 0
    dangling = instructions["danglingReferenceCount"] > 0
    parsing = filters.get("ingredientParsing")
    links = filters.get("instructionIngredientLinks")
    matches = {
        "ingredientParsing": unparsed
        if parsing == "unparsed"
        else partial
        if parsing == "partial"
        else unparsed or partial,
        "ingredientSections": ingredients["sectionCount"] > 0
        if filters.get("ingredientSections")
        else ingredients["totalCount"] > 0 and ingredients["sectionCount"] == 0,
        "instructionIngredientLinks": missing
        if links == "missing"
        else dangling
        if links == "dangling"
        else missing or dangling,
        "tools": (audit["toolCount"] > 0) == filters.get("tools"),
        "categories": (audit["categoryCount"] > 0) == filters.get("categories"),
        "tags": (audit["tagCount"] > 0) == filters.get("tags"),
        "image": audit["hasImage"] == filters.get("image"),
    }
    return [dimension for dimension in DIMENSIONS if dimension in filters and matches[dimension]]


def compact_recipe(
    detail: JsonObject, audit: RecipeEnrichmentAudit, dimensions: list[str]
) -> JsonObject:
    return {
        **compact_context(detail),
        "createdAt": string(detail.get("createdAt")) or None,
        "updatedAt": string(detail.get("updatedAt")) or None,
        "sourceUrl": string(detail.get("orgURL")) or None,
        "ingredients": [
            compact_ingredient(row) for row in to_array(detail.get("recipeIngredient"))
        ],
        "instructions": [
            {
                "title": string(row.get("title")),
                "text": string(row.get("text")),
                "ingredientReferenceIds": [
                    identifier
                    for ref in to_array(row.get("ingredientReferences"))
                    if (identifier := id_string(ref.get("referenceId")))
                ],
            }
            for row in to_array(detail.get("recipeInstructions"))
        ],
        "tools": [
            {"id": id_string(row.get("id")), "name": string(row.get("name"))}
            for row in to_array(detail.get("tools"))
        ],
        "audit": cast(JsonValue, audit),
        "matchedDimensions": [*dimensions],
    }


async def get_recipes_for_data_enrichment(
    client: MealieClient, request: GetRecipesForDataEnrichmentInput
) -> JsonObject:
    filters = (
        provided_fields(request.filters) if request.filters is not None else dict(DEFAULT_FILTERS)
    )
    if not filters:
        raise ValueError(
            "filters must specify at least one dimension. An empty filters object is not "
            '"return every recipe"; omit filters to use the default enrichment filters.'
        )

    def matches(audit: RecipeEnrichmentAudit) -> bool:
        count = len(matched_dimensions(filters, audit))
        return count == len(filters) if request.match == "all" else count > 0

    def to_item(detail: JsonObject, audit: RecipeEnrichmentAudit) -> JsonObject:
        return compact_recipe(detail, audit, matched_dimensions(filters, audit))

    return audit_page(
        await scan_audited_recipes(
            client,
            decode_cursor(request.cursor) if request.cursor else None,
            request.limit,
            matches,
            to_item,
        )
    )
