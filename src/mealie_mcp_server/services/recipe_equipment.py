"""Recipe equipment assignment, with per-entry creation and failure scope."""

import asyncio

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import to_organizer_items
from mealie_mcp_server.services.recipe_organizers import (
    CollectionOutcome,
    batch_slugs,
    mode_value,
    recipe_identity,
    resolve_collection,
    string_values,
)
from mealie_mcp_server.support.concurrency import map_with_concurrency


async def update_recipe_equipment(
    client: MealieClient,
    slug: str,
    changes: JsonObject,
    *,
    creation_lock: asyncio.Lock | None = None,
) -> JsonObject:
    legacy = "tools" in changes or "mode" in changes
    delta = "add" in changes or "remove" in changes
    if legacy and delta:
        raise ValueError("Provide either tools (with optional mode) or add/remove, not both.")
    if not delta and "tools" not in changes:
        raise ValueError(
            "mode only applies together with tools; provide tools, or use add/remove."
            if "mode" in changes
            else "Provide tools (with optional mode) or at least one of add/remove."
        )
    recipe = await recipes.get_recipe(client, slug)
    create_missing = changes.get("createMissing") is True

    async def resolve_all() -> CollectionOutcome:
        return await resolve_collection(
            client,
            "tool",
            to_organizer_items(recipe.get("tools")),
            string_values(changes, "tools") if legacy else None,
            string_values(changes, "add") or [],
            string_values(changes, "remove") or [],
            mode_value(changes),
            create_missing,
        )

    if create_missing and creation_lock is not None:
        async with creation_lock:
            collection = await resolve_all()
    else:
        collection = await resolve_all()
    if collection.changed:
        await recipes.patch_recipe(client, slug, {"tools": list(collection.payload())})
    return {**recipe_identity(recipe, slug), "tools": collection.as_json()}


async def update_recipe_equipment_batch(
    client: MealieClient, updates: list[JsonObject]
) -> JsonObject:
    batch_slugs(updates, limit=25)
    lock = asyncio.Lock()

    async def apply(update: JsonObject) -> JsonValue:
        slug = update["slug"]
        assert isinstance(slug, str)
        try:
            result = await update_recipe_equipment(
                client,
                slug,
                {key: value for key, value in update.items() if key != "slug"},
                creation_lock=lock,
            )
            return {"success": True, **result}
        except Exception as error:
            return {"slug": slug, "success": False, "error": str(error)}

    results = await map_with_concurrency(updates, 5, apply)
    succeeded = sum(
        isinstance(result, dict) and result.get("success") is True for result in results
    )
    return {
        "requestedCount": len(updates),
        "succeededCount": succeeded,
        "failedCount": len(updates) - succeeded,
        "results": results,
    }
