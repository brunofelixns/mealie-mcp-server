"""Meal-plan workflows keep ordered phases and independent entry results."""

from typing import cast

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import mealplans as api
from mealie_mcp_server.mealie.api.recipes import get_recipes_batch
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.concurrency import map_with_concurrency


async def create_mealplan_bulk(client: MealieClient, entries: list[JsonObject]) -> JsonObject:
    async def create(indexed: tuple[int, JsonObject]) -> JsonValue:
        index, entry = indexed
        try:
            payload = dict(entry)
            payload.setdefault("entryType", "breakfast")
            created = await api.create_mealplan(client, payload)
            if not isinstance(created, dict):
                raise ValueError("Invalid Mealie mealplan response.")
            projected = {
                key: created[key]
                for key in ("id", "date", "entryType", "recipeId", "title")
                if key in created
            }
            return {"index": index, "success": True, "entry": projected}
        except Exception as error:
            return {"index": index, "success": False, "error": str(error)}

    results = await map_with_concurrency(list(enumerate(entries)), 4, create)
    created = sum(isinstance(result, dict) and result.get("success") is True for result in results)
    return {"created": created, "failed": len(results) - created, "results": results}


async def _apply_action(client: MealieClient, action: JsonObject) -> JsonObject:
    kind = action["action"]
    identifier = cast(str, action.get("id"))
    try:
        if kind == "delete":
            await api.delete_mealplan(client, identifier)
            return {"action": "delete", "id": identifier, "ok": True}
        if kind == "replace":
            current = await api.get_mealplan(client, identifier)
            merged = dict(current)
            merged.update(
                {
                    key: action[key]
                    for key in ("date", "recipeId", "title", "entryType")
                    if key in action
                }
            )
            updated = await api.update_mealplan(client, identifier, merged)
            return {"action": "replace", "id": identifier, "ok": True, "entry": updated}
        payload = {
            key: action[key] for key in ("date", "recipeId", "title", "entryType") if key in action
        }
        payload.setdefault("entryType", "breakfast")
        created = await api.create_mealplan(client, payload)
        return {"action": "append", "ok": True, "entry": created}
    except Exception as error:
        result: JsonObject = {"action": kind}
        if kind in ("delete", "replace"):
            result["id"] = identifier
        result.update({"ok": False, "error": str(error)})
        return result


async def patch_mealplan(client: MealieClient, actions: list[JsonObject]) -> JsonObject:
    results: list[JsonValue] = []
    counts = {"deleted": 0, "replaced": 0, "appended": 0, "failed": 0}

    async def apply(action: JsonObject) -> JsonValue:
        return await _apply_action(client, action)

    for phase, counter in (("delete", "deleted"), ("replace", "replaced"), ("append", "appended")):
        group = [action for action in actions if action.get("action") == phase]
        phase_results = await map_with_concurrency(group, 4, apply)
        results.extend(phase_results)
        for result in phase_results:
            counts[
                counter if isinstance(result, dict) and result.get("ok") is True else "failed"
            ] += 1
    return {
        "summary": {
            "deleted": counts["deleted"],
            "replaced": counts["replaced"],
            "appended": counts["appended"],
            "failed": counts["failed"],
        },
        "results": results,
    }


async def get_mealplan_with_recipes(
    client: MealieClient, start_date: str, end_date: str
) -> list[JsonValue]:
    items: list[JsonObject] = []
    page = 1
    while True:
        result = await api.get_mealplans(
            client, {"startDate": start_date, "endDate": end_date, "page": page, "perPage": 100}
        )
        raw_items = result.get("items")
        if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
            raise ValueError("Invalid Mealie mealplan listing.")
        items.extend(item for item in raw_items if isinstance(item, dict))
        total = result.get("total")
        if not raw_items or (isinstance(total, (int, float)) and len(items) >= total):
            break
        page += 1
    filtered = [
        item
        for item in items
        if isinstance(item.get("date"), str) and start_date <= cast(str, item["date"]) <= end_date
    ]
    references: dict[str, None] = {}
    for item in filtered:
        for key in ("recipeId", "recipeSlug"):
            reference = item.get(key)
            if isinstance(reference, str) and reference:
                references[reference] = None
    recipe_map = await get_recipes_batch(client, list(references)) if references else {}
    enriched: list[JsonValue] = []
    for item in filtered:
        reference_key = item.get("recipeId") or item.get("recipeSlug")
        if isinstance(reference_key, str) and reference_key in recipe_map:
            enriched.append({**item, "recipe": recipe_map[reference_key]})
        else:
            enriched.append(item)
    return enriched
