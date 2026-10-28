"""Mealie suggestions, strict food filtering and text fallback with explicit provenance."""

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient, ParamValue, build_query_string
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.models.inputs.recipe_queues import FindRecipesForIngredientsInput
from mealie_mcp_server.services.ingredient_resolution import ResolvedIngredient, resolve_ingredients
from mealie_mcp_server.services.taxonomy_resolution import resolve_taxonomy_filter
from mealie_mcp_server.support.recipe_scan import to_array
from mealie_mcp_server.support.strings import trim


@dataclass
class Candidate:
    recipe: JsonObject
    matched: dict[str, None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        name
        for row in value
        if isinstance(row, dict) and isinstance(name := row.get("name"), str) and name
    ]


def candidate_json(candidate: Candidate, source: str) -> JsonObject:
    recipe = candidate.recipe
    result: JsonObject = {
        "name": recipe.get("name") if isinstance(recipe.get("name"), str) else "",
        "slug": recipe.get("slug") if isinstance(recipe.get("slug"), str) else "",
        "categories": [*names(recipe.get("recipeCategory"))],
        "tags": [*names(recipe.get("tags"))],
        "totalTime": recipe.get("totalTime") if isinstance(recipe.get("totalTime"), str) else None,
        "matchedIngredients": list(candidate.matched),
        "missingIngredients": [*candidate.missing],
        "matchSource": source,
    }
    if isinstance(description := recipe.get("description"), str) and description:
        result["description"] = description
    return result


async def settled[T](
    items: list[T], fn: Callable[[T], Awaitable[JsonObject]]
) -> list[JsonObject | None]:
    async def call(item: T) -> JsonObject | None:
        try:
            return await fn(item)
        except Exception:
            return None

    return list(await asyncio.gather(*(call(item) for item in items)))


def taxonomy_matches(
    recipe: JsonObject, key: str, ids: list[str] | None, require_all: bool | None
) -> bool:
    if not ids:
        return True
    present = {row.get("id") for row in to_array(recipe.get(key)) if isinstance(row.get("id"), str)}
    hits = [identifier in present for identifier in ids]
    return all(hits) if require_all else any(hits)


async def find_recipes_for_ingredients(
    client: MealieClient, request: FindRecipesForIngredientsInput
) -> JsonObject:
    queries = [value for query in request.ingredients if (value := trim(query))]
    if not queries:
        raise ValueError("ingredients must contain at least one non-empty ingredient name.")
    limit = min(max(math.trunc(request.limit), 1), 50)
    categories = await resolve_taxonomy_filter(client, "category", request.categories)
    tags = await resolve_taxonomy_filter(client, "tag", request.tags)
    resolved, unresolved = await resolve_ingredients(client, queries)
    notes: list[str] = []
    taxonomy_requested = bool(request.categories or request.tags)

    async def note_excluded(count: Callable[[], Awaitable[int]]) -> None:
        if not taxonomy_requested:
            return
        try:
            total = await count()
        except Exception:
            return
        if total > 0:
            notes.append(
                f"{total} recipe(s) matched the ingredient search but were excluded by the "
                "requested categories/tags filter."
            )

    def taxonomy_params(include: bool = True) -> dict[str, ParamValue]:
        return {
            "categories": categories if include else None,
            "tags": tags if include else None,
            "requireAllCategories": request.require_all_categories,
            "requireAllTags": request.require_all_tags,
        }

    async def terms_search(
        terms: list[str], per_call: int, include: bool
    ) -> tuple[list[Candidate], list[str]]:
        async def search(term: str) -> JsonObject:
            return await recipes.get_recipes(
                client, {"search": term, **taxonomy_params(include), "perPage": per_call}
            )

        outcomes = await settled(terms, search)
        by_slug: dict[str, Candidate] = {}
        failed: list[str] = []
        successful: list[str] = []
        for term, result in zip(terms, outcomes, strict=True):
            if result is None:
                failed.append(term)
                continue
            successful.append(term)
            for recipe in to_array(result.get("items")):
                slug = recipe.get("slug")
                if not isinstance(slug, str) or not slug:
                    continue
                candidate = by_slug.setdefault(slug, Candidate(recipe))
                candidate.matched[term] = None
        entries = list(by_slug.values())
        if request.require_all_ingredients and len(successful) > 1:
            entries = [
                entry for entry in entries if all(term in entry.matched for term in successful)
            ]
        return entries, failed

    async def text_fallback(terms: list[str]) -> list[JsonObject]:
        if not terms:
            return []
        per_call = min(limit * 4, 100) if len(terms) > 1 else limit
        entries, failed = await terms_search(terms, per_call, True)
        if failed:
            notes.append(f"Text search failed for: {', '.join(failed)}.")
        if len(failed) == len(terms):
            raise ValueError(
                f"Mealie recipe search failed for all ingredient terms: {', '.join(failed)}."
            )
        if not entries:

            async def count() -> int:
                unfiltered, _ = await terms_search(terms, per_call, False)
                return len(unfiltered)

            await note_excluded(count)
        entries.sort(key=lambda entry: -len(entry.matched))
        return [candidate_json(entry, "text-search") for entry in entries[:limit]]

    async def suggestions() -> tuple[list[JsonObject], list[str]]:
        per_call = min(limit * 4, 100) if taxonomy_requested else limit

        async def fetch(item: ResolvedIngredient) -> JsonObject:
            query = build_query_string(
                {
                    "foods": [item.food_id],
                    "limit": per_call,
                    "maxMissingFoods": 1000,
                    "includeFoodsOnHand": False,
                    "includeToolsOnHand": False,
                }
            )
            result = await client.request("GET", "/api/recipes/suggestions?" + query)
            if not isinstance(result, dict):
                raise ValueError("Invalid Mealie suggestions response.")
            return result

        outcomes = await settled(resolved, fetch)
        by_slug: dict[str, Candidate] = {}
        failed: list[str] = []
        primary_notes: list[str] = []
        for food, result in zip(resolved, outcomes, strict=True):
            if result is None:
                failed.append(food.query)
                continue
            for item in to_array(result.get("items")):
                recipe = item.get("recipe")
                if not isinstance(recipe, dict):
                    continue
                slug = recipe.get("slug")
                if not isinstance(slug, str) or not slug:
                    continue
                missing = names(item.get("missingFoods"))
                if slug in by_slug:
                    candidate = by_slug[slug]
                    if len(missing) < len(candidate.missing):
                        candidate.missing = missing
                else:
                    candidate = Candidate(recipe, missing=missing)
                    by_slug[slug] = candidate
                candidate.matched[food.query] = None
        if failed and len(failed) == len(resolved):
            raise ValueError(
                "Mealie recipe suggestions lookup failed for all resolved ingredients: "
                f"{', '.join(failed)}."
            )
        if failed:
            primary_notes.append(
                f"Recipe suggestions lookup failed for: {', '.join(failed)} "
                "(other ingredients still searched)."
            )
        candidates = [
            entry
            for entry in by_slug.values()
            if taxonomy_matches(
                entry.recipe, "recipeCategory", categories, request.require_all_categories
            )
            and taxonomy_matches(entry.recipe, "tags", tags, request.require_all_tags)
        ]
        excluded = len(by_slug) - len(candidates)
        if excluded:
            primary_notes.append(
                f"{excluded} recipe(s) matched the ingredient search but were excluded by the "
                "requested categories/tags filter."
            )
        candidates.sort(key=lambda entry: -len(entry.matched))
        return [candidate_json(entry, "suggestions") for entry in candidates[:limit]], primary_notes

    def result(items: list[JsonObject], source: str) -> JsonObject:
        return {
            "resolvedIngredients": [food.as_json() for food in resolved],
            "unresolvedIngredients": [*unresolved],
            "matchSource": source if items else "none",
            "recipes": [*items],
            "notes": [*notes],
        }

    if not resolved:
        terms = [
            str(item["query"])
            for item in unresolved
            if item["reason"] in ("not-found", "ambiguous")
        ]
        return result(await text_fallback(terms), "text-search")
    if unresolved:
        notes.append(
            f"{len(unresolved)} ingredient(s) could not be resolved to a Mealie food "
            "and were excluded from matching: "
            f"{', '.join(str(item['query']) for item in unresolved)}."
        )
    food_filter = len(resolved) > 1 and request.require_all_ingredients is True
    if food_filter and unresolved:
        notes.append(
            "requireAllIngredients only applies to the ingredients that were successfully "
            "resolved to a Mealie food."
        )
    if food_filter:
        foods = [item.food_id for item in resolved]
        page = await recipes.get_recipes(
            client, {"foods": foods, "requireAllFoods": True, **taxonomy_params(), "perPage": limit}
        )
        entries = to_array(page.get("items"))
        primary_notes: list[str] = []
        if not entries:

            async def count() -> int:
                page = await recipes.get_recipes(
                    client, {"foods": foods, "requireAllFoods": True, "perPage": 1}
                )
                total = page.get("total")
                return int(total) if isinstance(total, (int, float)) else 0

            prior = len(notes)
            await note_excluded(count)
            primary_notes = notes[prior:]
            del notes[prior:]
        items = [
            candidate_json(
                Candidate(recipe, dict.fromkeys(item.query for item in resolved)), "food-filter"
            )
            for recipe in entries
        ]
    else:
        items, primary_notes = await suggestions()
    if items:
        notes.extend(primary_notes)
        return result(items, "food-filter" if food_filter else "suggestions")
    fallback = await text_fallback(queries)
    if fallback:
        notes.append(
            "No results from Mealie's Recipe Finder for the resolved ingredient(s); "
            "fell back to normal recipe text search."
        )
    return result(fallback, "text-search")
