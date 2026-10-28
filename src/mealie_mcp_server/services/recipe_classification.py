"""Cheap taxonomy filtering before bounded detail reads; no recipe writes."""

from collections.abc import Callable
from contextlib import aclosing
from time import monotonic

from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.recipe_queues import (
    GetRecipesForClassificationInput,
    TaxonomyState,
)
from mealie_mcp_server.services.recipe_audit import fetch_recipe_detail, next_cursor_for
from mealie_mcp_server.support.concurrency import map_with_concurrency
from mealie_mcp_server.support.recipe_scan import (
    ScannedRecipe,
    decode_cursor,
    id_string,
    is_number,
    scan_recipes_stable,
    string,
    taxonomy_item,
    to_array,
)


def compact_context(raw: JsonObject) -> JsonObject:
    return {
        "id": id_string(raw.get("id")),
        "slug": string(raw.get("slug")),
        "name": string(raw.get("name")),
        "description": string(raw.get("description")) or None,
        "totalTime": string(raw.get("totalTime")) or None,
        "prepTime": string(raw.get("prepTime")) or None,
        "cookTime": string(raw.get("cookTime")) or None,
        "servings": raw.get("recipeServings") if is_number(raw.get("recipeServings")) else None,
        "yield": string(raw.get("recipeYield")) or None,
        "categories": [taxonomy_item(row) for row in to_array(raw.get("recipeCategory"))],
        "tags": [taxonomy_item(row) for row in to_array(raw.get("tags"))],
    }


def ingredient_line(row: JsonObject) -> str:
    for field in ("display", "note"):
        if text := string(row.get(field)):
            return text
    quantity = row.get("quantity")
    parts = [id_string(quantity) if is_number(quantity) and quantity > 0 else ""]
    for field in ("unit", "food"):
        value = row.get(field)
        parts.append(string(value.get("name")) if isinstance(value, dict) else "")
    reconstructed = " ".join(part for part in parts if part)
    return reconstructed or string(row.get("originalText")) or string(row.get("title"))


def compact_recipe(raw: JsonObject) -> JsonObject:
    instructions: list[str] = []
    last_heading = ""
    for row in to_array(raw.get("recipeInstructions")):
        title, text = string(row.get("title")), string(row.get("text"))
        if title and title != last_heading:
            instructions.append(title)
            last_heading = title
        if text:
            instructions.append(text)
    return {
        **compact_context(raw),
        "sourceUrl": string(raw.get("orgURL")) or None,
        "ingredients": [
            line for row in to_array(raw.get("recipeIngredient")) if (line := ingredient_line(row))
        ],
        "instructions": [*instructions],
    }


def matches_taxonomy(raw: JsonObject, state: TaxonomyState) -> bool:
    categories_empty = not to_array(raw.get("recipeCategory"))
    tags_empty = not to_array(raw.get("tags"))
    return {
        "any": True,
        "missing_either": categories_empty or tags_empty,
        "missing_both": categories_empty and tags_empty,
        "missing_categories": categories_empty,
        "missing_tags": tags_empty,
    }[state]


async def get_recipes_for_classification(
    client: MealieClient,
    request: GetRecipesForClassificationInput,
    *,
    now: Callable[[], float] | None = None,
    deadline_ms: float = 20000,
) -> JsonObject:
    clock = now or (lambda: monotonic() * 1000)
    deadline = clock() + deadline_ms
    cursor = decode_cursor(request.cursor) if request.cursor else None
    matched: list[ScannedRecipe] = []
    last: ScannedRecipe | None = None
    scanned_count = 0
    has_more = False
    async with aclosing(scan_recipes_stable(client, cursor)) as iterator:
        async for entry in iterator:
            scanned_count += 1
            last = entry
            if matches_taxonomy(entry.summary, request.taxonomy_state):
                matched.append(entry)
            if len(matched) >= request.limit or clock() > deadline:
                has_more = True
                break

    async def fetch(entry: ScannedRecipe) -> tuple[JsonObject | None, JsonObject | None]:
        return await fetch_recipe_detail(client, entry)

    details = await map_with_concurrency(matched, 4, fetch)
    items: list[JsonObject] = []
    failures: list[JsonObject] = []
    for detail, failure in details:
        if failure is not None:
            failures.append(failure)
        elif detail is not None:
            items.append(compact_recipe(detail))
    return {
        "items": [*items],
        "failures": [*failures],
        "nextCursor": next_cursor_for(last, has_more),
        "scannedCount": scanned_count,
        "returnedCount": len(items),
        "hasMore": has_more,
    }
