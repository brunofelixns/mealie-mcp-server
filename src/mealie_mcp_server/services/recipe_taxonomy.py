"""Category/tag mutations preserve no-op, delta and creation boundaries."""

import asyncio

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import to_organizer_items
from mealie_mcp_server.services.recipe_organizers import (
    OrganizerKind,
    batch_slugs,
    mode_value,
    recipe_identity,
    resolve_collection,
    string_values,
)
from mealie_mcp_server.support.concurrency import map_with_concurrency


def _validate(changes: JsonObject) -> None:
    for full, add, remove in (
        ("categories", "addCategories", "removeCategories"),
        ("tags", "addTags", "removeTags"),
    ):
        if full in changes and (add in changes or remove in changes):
            raise ValueError(
                f"Provide either {full} (with optional mode) or {add}/{remove}, not both."
            )
    has_full = "categories" in changes or "tags" in changes
    has_delta = any(
        key in changes for key in ("addCategories", "removeCategories", "addTags", "removeTags")
    )
    if has_delta and not has_full and "mode" in changes:
        raise ValueError(
            "mode only applies together with categories/tags; "
            "it has no effect on add/remove delta fields."
        )


async def build_taxonomy_patch(
    client: MealieClient,
    recipe: JsonObject,
    changes: JsonObject,
    *,
    creation_lock: asyncio.Lock | None = None,
) -> JsonObject:
    _validate(changes)
    mode = mode_value(changes)
    create_missing = changes.get("createMissing") is True
    configurations: list[tuple[OrganizerKind, str, str, str, str, str]] = []
    if any(key in changes for key in ("categories", "addCategories", "removeCategories")):
        configurations.append(
            (
                "category",
                "categories",
                "recipeCategory",
                "categories",
                "addCategories",
                "removeCategories",
            )
        )
    if any(key in changes for key in ("tags", "addTags", "removeTags")):
        configurations.append(("tag", "tags", "tags", "tags", "addTags", "removeTags"))

    async def resolve_all() -> JsonObject:
        patch_fields: JsonObject = {}
        outcome: JsonObject = {"patchFields": patch_fields}
        if create_missing and len(configurations) > 1:
            for kind, _, patch_key, full, add, remove in configurations:
                await resolve_collection(
                    client,
                    kind,
                    to_organizer_items(recipe.get(patch_key)),
                    string_values(changes, full),
                    string_values(changes, add) or [],
                    string_values(changes, remove) or [],
                    mode,
                    True,
                    dry_run=True,
                )
        for kind, outcome_key, patch_key, full, add, remove in configurations:
            collection = await resolve_collection(
                client,
                kind,
                to_organizer_items(recipe.get(patch_key)),
                string_values(changes, full),
                string_values(changes, add) or [],
                string_values(changes, remove) or [],
                mode,
                create_missing,
            )
            outcome[outcome_key] = collection.as_json()
            if collection.changed:
                patch_fields[patch_key] = list(collection.payload())
        return outcome

    if create_missing and creation_lock is not None:
        async with creation_lock:
            return await resolve_all()
    return await resolve_all()


async def update_recipe_taxonomy(
    client: MealieClient,
    slug: str,
    changes: JsonObject,
    *,
    creation_lock: asyncio.Lock | None = None,
) -> JsonObject:
    recipe = await recipes.get_recipe(client, slug)
    outcome = await build_taxonomy_patch(client, recipe, changes, creation_lock=creation_lock)
    patch_fields = outcome["patchFields"]
    if isinstance(patch_fields, dict) and patch_fields:
        await recipes.patch_recipe(client, slug, patch_fields)
    return {
        **recipe_identity(recipe, slug),
        **{key: value for key, value in outcome.items() if key != "patchFields"},
    }


async def update_recipe_taxonomy_batch(
    client: MealieClient, updates: list[JsonObject]
) -> list[JsonValue]:
    batch_slugs(updates)
    lock = asyncio.Lock()

    async def apply(update: JsonObject) -> JsonValue:
        slug = update["slug"]
        assert isinstance(slug, str)
        try:
            result = await update_recipe_taxonomy(
                client,
                slug,
                {key: value for key, value in update.items() if key != "slug"},
                creation_lock=lock,
            )
            return {"success": True, **result}
        except Exception as error:
            return {"slug": slug, "success": False, "error": str(error)}

    return await map_with_concurrency(updates, 5, apply)


async def patch_recipe_with_taxonomy(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonObject:
    special = {"categories", "tags", "taxonomyMode", "createMissing", "instructions"}
    data = {key: value for key, value in changes.items() if key not in special}
    if "instructions" in changes:
        instructions = string_values(changes, "instructions")
        assert instructions is not None
        data["recipeInstructions"] = [{"text": text} for text in instructions]
    taxonomy_changes: JsonObject | None = None
    if "categories" in changes or "tags" in changes:
        recipe = await recipes.get_recipe(client, slug)
        taxonomy = {
            key: value
            for key, value in changes.items()
            if key in {"categories", "tags", "createMissing"}
        }
        if "taxonomyMode" in changes:
            taxonomy["mode"] = changes["taxonomyMode"]
        outcome = await build_taxonomy_patch(client, recipe, taxonomy)
        fields = outcome["patchFields"]
        assert isinstance(fields, dict)
        data.update(fields)
        taxonomy_changes = {key: value for key, value in outcome.items() if key != "patchFields"}
        if not data:
            return {**recipe, "taxonomyChanges": taxonomy_changes}
    result = await recipes.patch_recipe(client, slug, data)
    return (
        {**result, "taxonomyChanges": taxonomy_changes} if taxonomy_changes is not None else result
    )
