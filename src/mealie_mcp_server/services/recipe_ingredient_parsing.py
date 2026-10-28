from typing import cast

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.recipe_queues import GetRecipesForIngredientParsingInput
from mealie_mcp_server.services.recipe_audit import (
    AuditScanResult,
    RecipeEnrichmentAudit,
    classify_ingredient,
    scan_audited_recipes,
)
from mealie_mcp_server.services.recipe_classification import compact_context
from mealie_mcp_server.support.recipe_scan import (
    decode_cursor,
    id_string,
    is_number,
    string,
    to_array,
)


def compact_ref(value: JsonValue | None) -> JsonObject | None:
    if not isinstance(value, (dict, list)):
        return None
    row = value if isinstance(value, dict) else {}
    return {"id": id_string(row.get("id")), "name": string(row.get("name"))}


def compact_ingredient(row: JsonObject) -> JsonObject:
    return {
        "referenceId": id_string(row.get("referenceId")),
        "quantity": row.get("quantity") if is_number(row.get("quantity")) else None,
        "unit": compact_ref(row.get("unit")),
        "food": compact_ref(row.get("food")),
        "note": string(row.get("note")),
        "display": string(row.get("display")),
        "originalText": string(row.get("originalText")) or None,
        "title": string(row.get("title")) or None,
        "parsingState": classify_ingredient(row),
    }


def compact_instruction(row: JsonObject) -> JsonObject:
    result: JsonObject = {
        "title": string(row.get("title")),
        "text": string(row.get("text")),
        "ingredientReferences": [*to_array(row.get("ingredientReferences"))],
    }
    if identifier := string(row.get("id")):
        result["id"] = identifier
    return result


def compact_recipe(detail: JsonObject, audit: RecipeEnrichmentAudit) -> JsonObject:
    return {
        **compact_context(detail),
        "ingredients": [
            compact_ingredient(row) for row in to_array(detail.get("recipeIngredient"))
        ],
        "instructions": [
            compact_instruction(row) for row in to_array(detail.get("recipeInstructions"))
        ],
        "ingredientParsingState": cast(JsonValue, audit["ingredients"]),
    }


def audit_page(scan: AuditScanResult[JsonObject]) -> JsonObject:
    return {
        "items": [*scan.items],
        "failures": [*scan.failures],
        "nextCursor": scan.next_cursor,
        "scannedCount": scan.scanned_count,
        "returnedCount": len(scan.items),
        "hasMore": scan.has_more,
    }


async def get_recipes_for_ingredient_parsing(
    client: MealieClient, request: GetRecipesForIngredientParsingInput
) -> JsonObject:
    def matches(audit: RecipeEnrichmentAudit) -> bool:
        counts = audit["ingredients"]
        return request.state == "any" or (
            counts["unparsedCount"] > 0
            if request.state == "unparsed_only"
            else counts["partialCount"] > 0
        )

    return audit_page(
        await scan_audited_recipes(
            client,
            decode_cursor(request.cursor) if request.cursor else None,
            request.limit,
            matches,
            compact_recipe,
        )
    )
