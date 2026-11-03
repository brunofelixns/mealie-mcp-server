"""Native recipe search/parser and narrowly verified 3.30 data mutations."""

from copy import deepcopy
from typing import cast
from uuid import UUID

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import (
    MealieClient,
    ParamValue,
    build_query_string,
    encode_path_segment,
)
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.recipe_notes import _snapshot
from mealie_mcp_server.support.mutations import finish_verified_mutation


async def _query(client: MealieClient, path: str, params: JsonObject) -> JsonValue:
    query = build_query_string(cast(dict[str, ParamValue], params))
    return await client.request("GET", path + ("?" + query if query else ""))


async def search_recipes(client: MealieClient, params: JsonObject) -> JsonValue:
    return await _query(client, "/api/recipes", params)


async def get_recipe_suggestions(client: MealieClient, params: JsonObject) -> JsonValue:
    return await _query(client, "/api/recipes/suggestions", params)


async def parse_recipe_ingredient(client: MealieClient, params: JsonObject) -> JsonValue:
    return await client.request("POST", "/api/parser/ingredient", json=params)


async def parse_recipe_ingredients(client: MealieClient, params: JsonObject) -> JsonValue:
    return await client.request("POST", "/api/parser/ingredients", json=params)


def _records(value: JsonValue | None, what: str) -> list[JsonObject]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"Invalid {what} collection; nothing was written.")
    return cast(list[JsonObject], value)


def _without_step_ids(rows: list[JsonObject]) -> list[JsonObject]:
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def _canonical_substitutions(value: JsonValue | None) -> list[JsonObject]:
    result: list[JsonObject] = []
    for row in _records(value, "substitutions"):
        item: JsonObject = {"substituteFoodId": None, "note": None, **row}
        item.pop("substituteFood", None)
        identifier, note = item["substituteFoodId"], item["note"]
        if isinstance(identifier, str):
            item["substituteFoodId"] = identifier.lower()
        if isinstance(note, str):
            # Native SubstitutionBase strips note boundaries and maps blanks to null.
            item["note"] = note.strip() or None
        result.append(item)
    return result


def _canonical_ingredients(rows: list[JsonObject]) -> list[JsonObject]:
    # substituteFood is hydrated by Mealie from the explicit canonical target ID.
    return [
        {**row, "substitutions": [*_canonical_substitutions(row.get("substitutions", []))]}
        for row in rows
    ]


def _food_identifier(value: JsonValue | None) -> str:
    if isinstance(value, str):
        try:
            identifier = UUID(value)
        except ValueError:
            pass
        else:
            if identifier.version == 4 and str(identifier) == value.lower():
                return str(identifier)
    raise ValueError("A canonical food UUID is required; nothing was written.")


async def _validate_substitutions(
    client: MealieClient, rows: list[JsonObject], own_id: JsonValue | None
) -> None:
    seen: set[str] = set()
    for row in rows:
        raw_identifier = row.get("substituteFoodId")
        if raw_identifier is None:
            note = row.get("note")
            if not isinstance(note, str) or not note.strip():
                raise ValueError(
                    "Supply a canonical substituteFoodId or a nonblank note; nothing was written."
                )
            continue
        identifier = _food_identifier(raw_identifier)
        if isinstance(own_id, str) and identifier == own_id.lower():
            raise ValueError("A food cannot substitute itself; nothing was written.")
        if identifier in seen:
            raise ValueError("Duplicate substituteFoodId; nothing was written.")
        seen.add(identifier)
        target = await client.request(
            "GET", "/api/foods/" + encode_path_segment(identifier, "foodId")
        )
        if not isinstance(target, dict) or target.get("id") != identifier:
            raise ValueError("substituteFoodId resolved to a different food; nothing was written.")


async def _write_recipe(
    client: MealieClient, slug: str, original: JsonObject, key: str, desired: list[JsonObject]
) -> JsonObject:
    async def write_and_verify() -> JsonObject:
        updated = await recipes.patch_recipe(client, slug, {key: [*desired]})
        try:
            actual = _records(updated.get(key), key)
            if key == "recipeInstructions":
                matches = _without_step_ids(actual) == desired
            else:
                matches = _canonical_ingredients(actual) == _canonical_ingredients(desired)
            if not matches:
                raise ValueError("Stored collection differs from the requested collection.")
        except ValueError as error:
            raise ValueError(
                "Recipe verification failed after Mealie update; the write was not replayed. "
                "Re-read the recipe before further changes."
            ) from error
        return updated

    current = _records(original.get(key), key)
    if (key == "recipeInstructions" and _without_step_ids(current) == desired) or (
        key == "recipeIngredient"
        and _canonical_ingredients(current) == _canonical_ingredients(desired)
    ):
        return original
    return await finish_verified_mutation(write_and_verify())


async def update_recipe_ingredient_substitutions(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonObject:
    original = await _snapshot(client, slug, changes)
    desired = deepcopy(_records(original.get("recipeIngredient"), "recipeIngredient"))
    updates = _records(changes.get("updates"), "updates")
    if not updates:
        raise ValueError("Provide at least one substitution update; nothing was written.")
    seen: set[str] = set()
    for update in updates:
        reference = update.get("referenceId")
        if not isinstance(reference, str) or not reference:
            raise ValueError("referenceId is required; nothing was written.")
        reference = reference.lower()
        indexes = [
            index
            for index, row in enumerate(desired)
            if isinstance(row.get("referenceId"), str)
            and str(row["referenceId"]).lower() == reference
        ]
        if len(indexes) != 1 or reference in seen:
            raise ValueError(
                "Unknown, duplicate or ambiguous ingredient referenceId; nothing was written."
            )
        seen.add(reference)
        row = desired[indexes[0]]
        substitutions = _records(update.get("substitutions"), "substitutions")
        food = row.get("food")
        if any(item.get("substituteFoodId") is not None for item in substitutions):
            if not isinstance(food, dict):
                raise ValueError(
                    "Ingredient substitutions require a canonical food association; "
                    "nothing was written."
                )
            _food_identifier(food.get("id"))
        await _validate_substitutions(
            client, substitutions, food.get("id") if isinstance(food, dict) else None
        )
        row["substitutions"] = [*deepcopy(substitutions)]
    return await _write_recipe(client, slug, original, "recipeIngredient", desired)


async def update_food_substitutions(
    client: MealieClient, food_id: str, changes: JsonObject
) -> JsonObject:
    food_id = _food_identifier(food_id)
    path = "/api/foods/" + encode_path_segment(food_id, "foodId")
    original = await client.request("GET", path)
    if not isinstance(original, dict) or original.get("id") != food_id:
        raise ValueError("Invalid Mealie food response; nothing was written.")
    substitutions = _records(changes.get("substitutions"), "substitutions")
    await _validate_substitutions(client, substitutions, food_id)
    if _canonical_substitutions(original.get("substitutions", [])) == _canonical_substitutions(
        cast(JsonValue, substitutions)
    ):
        return original

    async def write_and_verify() -> JsonObject:
        updated = await client.request(
            "PUT", path, json={**original, "substitutions": [*substitutions]}
        )
        if not isinstance(updated, dict) or _canonical_substitutions(
            updated.get("substitutions")
        ) != _canonical_substitutions(cast(JsonValue, substitutions)):
            raise ValueError(
                "Food substitution verification failed after Mealie update; "
                "the write was not replayed. Re-read the food before further changes."
            )
        return updated

    return await finish_verified_mutation(write_and_verify())


async def update_recipe_instruction_durations(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonObject:
    original = await _snapshot(client, slug, changes)
    desired = deepcopy(
        _without_step_ids(_records(original.get("recipeInstructions"), "recipeInstructions"))
    )
    updates = _records(changes.get("updates"), "updates")
    if not updates:
        raise ValueError("Provide at least one duration update; nothing was written.")
    seen: set[int] = set()
    for update in updates:
        index = update.get("index")
        duration = update.get("durationSeconds")
        if type(index) is not int or index < 0 or index >= len(desired) or index in seen:
            raise ValueError("Invalid or duplicate instruction index; nothing was written.")
        if "durationSeconds" not in update or (
            duration is not None and (type(duration) is not int or not 1 <= duration <= 2147483647)
        ):
            raise ValueError("durationSeconds must be null or an integer between 1 and 2147483647.")
        seen.add(index)
        desired[index]["durationSeconds"] = duration
    return await _write_recipe(client, slug, original, "recipeInstructions", desired)
