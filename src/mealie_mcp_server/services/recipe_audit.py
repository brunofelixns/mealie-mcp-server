from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass
from time import monotonic
from typing import Literal, TypedDict

from mealie_mcp_server.mealie.api.recipes import get_recipe_value
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.concurrency import map_with_concurrency
from mealie_mcp_server.support.recipe_scan import (
    ScanCursor,
    ScannedRecipe,
    encode_cursor,
    id_string,
    is_number,
    scan_recipes_stable,
    string,
    to_array,
)


class IngredientParsingCounts(TypedDict):
    totalCount: int
    structuredCount: int
    partialCount: int
    unparsedCount: int
    sectionCount: int


class InstructionReferenceFacts(TypedDict):
    instructionCount: int
    referencedInstructionCount: int
    referenceCount: int
    danglingReferenceCount: int
    sectionCount: int


class RecipeEnrichmentAudit(TypedDict):
    ingredients: IngredientParsingCounts
    instructions: InstructionReferenceFacts
    toolCount: int
    categoryCount: int
    tagCount: int
    hasImage: bool


@dataclass
class AuditScanResult[T]:
    items: list[T]
    failures: list[JsonObject]
    next_cursor: str | None
    scanned_count: int
    has_more: bool
    stop_reason: Literal["limit", "deadline", "exhausted"]


def classify_ingredient(raw: JsonObject) -> Literal["section", "unparsed", "partial", "structured"]:
    food = isinstance(raw.get("food"), (dict, list))
    unit = isinstance(raw.get("unit"), (dict, list))
    quantity = raw.get("quantity")
    positive = is_number(quantity) and isinstance(quantity, (int, float)) and quantity > 0
    title = string(raw.get("title"))
    original = string(raw.get("originalText"))
    if (
        title
        and not food
        and not unit
        and not positive
        and not string(raw.get("note"))
        and not string(raw.get("display"))
        and (not original or original == title)
    ):
        return "section"
    if not food:
        return "unparsed"
    return "partial" if not unit and positive else "structured"


def count_ingredient_states(rows: list[JsonObject]) -> IngredientParsingCounts:
    counts: IngredientParsingCounts = {
        "totalCount": len(rows),
        "structuredCount": 0,
        "partialCount": 0,
        "unparsedCount": 0,
        "sectionCount": 0,
    }
    for row in rows:
        if string(row.get("title")):
            counts["sectionCount"] += 1
        state = classify_ingredient(row)
        if state == "structured":
            counts["structuredCount"] += 1
        elif state == "partial":
            counts["partialCount"] += 1
        elif state == "unparsed":
            counts["unparsedCount"] += 1
    return counts


def audit_recipe(recipe: JsonObject) -> RecipeEnrichmentAudit:
    ingredients = to_array(recipe.get("recipeIngredient"))
    steps = to_array(recipe.get("recipeInstructions"))
    known = {id_string(row.get("referenceId")) for row in ingredients} - {""}
    instructions: InstructionReferenceFacts = {
        "instructionCount": len(steps),
        "referencedInstructionCount": 0,
        "referenceCount": 0,
        "danglingReferenceCount": 0,
        "sectionCount": 0,
    }
    for step in steps:
        if string(step.get("title")):
            instructions["sectionCount"] += 1
        refs = to_array(step.get("ingredientReferences"))
        if refs:
            instructions["referencedInstructionCount"] += 1
        instructions["referenceCount"] += len(refs)
        instructions["danglingReferenceCount"] += sum(
            id_string(ref.get("referenceId")) not in known for ref in refs
        )
    return {
        "ingredients": count_ingredient_states(ingredients),
        "instructions": instructions,
        "toolCount": len(to_array(recipe.get("tools"))),
        "categoryCount": len(to_array(recipe.get("recipeCategory"))),
        "tagCount": len(to_array(recipe.get("tags"))),
        "hasImage": bool(string(recipe.get("image"))),
    }


def next_cursor_for(entry: ScannedRecipe | None, has_more: bool) -> str | None:
    return (
        encode_cursor(ScanCursor(entry.created_at, entry.id, entry.page))
        if has_more and entry
        else None
    )


async def fetch_recipe_detail(
    client: MealieClient, entry: ScannedRecipe
) -> tuple[JsonObject | None, JsonObject | None]:
    slug = string(entry.summary.get("slug")) or entry.id
    failure: JsonObject = {}
    if slug:
        failure["slug"] = slug
    if entry.id:
        failure["id"] = entry.id
    try:
        detail = await get_recipe_value(client, slug)
        if isinstance(detail, dict):
            return detail, None
        failure["error"] = "Recipe detail response was empty or invalid"
    except Exception as error:
        failure["error"] = str(error)
    return None, failure


async def scan_audited_recipes[T](
    client: MealieClient,
    cursor: ScanCursor | None,
    limit: int,
    matches: Callable[[RecipeEnrichmentAudit], bool],
    to_item: Callable[[JsonObject, RecipeEnrichmentAudit], T],
    *,
    now: Callable[[], float] | None = None,
    deadline_ms: float = 20000,
) -> AuditScanResult[T]:
    clock = now or (lambda: monotonic() * 1000)
    deadline = clock() + deadline_ms
    items: list[T] = []
    failures: list[JsonObject] = []
    scanned_count = 0
    last: ScannedRecipe | None = None
    reason: Literal["limit", "deadline", "exhausted"] = "exhausted"
    async with aclosing(scan_recipes_stable(client, cursor)) as iterator:
        while True:
            batch: list[ScannedRecipe] = []
            for _ in range(20):
                entry = await anext(iterator, None)
                if entry is None:
                    break
                batch.append(entry)
            if not batch:
                break

            async def fetch(entry: ScannedRecipe) -> tuple[JsonObject | None, JsonObject | None]:
                return await fetch_recipe_detail(client, entry)

            details = await map_with_concurrency(batch, 4, fetch)
            for entry, (detail, failure) in zip(batch, details, strict=True):
                scanned_count += 1
                last = entry
                if failure is not None:
                    failures.append(failure)
                    continue
                assert detail is not None
                audit = audit_recipe(detail)
                if matches(audit):
                    items.append(to_item(detail, audit))
                if len(items) >= limit:
                    reason = "limit"
                    break
            if reason == "limit":
                break
            if clock() > deadline:
                reason = "deadline"
                break
    has_more = reason != "exhausted"
    return AuditScanResult(
        items, failures, next_cursor_for(last, has_more), scanned_count, has_more, reason
    )
