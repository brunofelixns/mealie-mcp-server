"""Stable note edits preserve provider fields and never replay recipe writes."""

from copy import deepcopy
from uuid import uuid4

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.recipe_instructions import UUID_PATTERN
from mealie_mcp_server.support.mutations import finish_verified_mutation


def _reference(value: JsonValue | None) -> str:
    if not isinstance(value, str) or not UUID_PATTERN.fullmatch(value):
        raise ValueError(
            "Invalid or missing referenceId in recipe notes or instruction references."
        )
    return value.lower()


def _notes(recipe: JsonObject) -> list[JsonObject]:
    value = recipe.get("notes", [])
    if not isinstance(value, list):
        raise ValueError("Invalid recipe notes collection; nothing was written.")
    result: list[JsonObject] = []
    seen: set[str] = set()
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Invalid recipe notes row; nothing was written.")
        identifier = _reference(row.get("referenceId"))
        if identifier in seen:
            raise ValueError("Duplicate referenceId in recipe notes; nothing was written.")
        if not isinstance(row.get("title"), str) or not isinstance(row.get("text"), str):
            raise ValueError("Invalid title/text in recipe notes; nothing was written.")
        seen.add(identifier)
        result.append(row)
    return result


async def get_recipe_notes(client: MealieClient, slug: str) -> JsonObject:
    recipe = await recipes.get_recipe(client, slug)
    return {key: recipe[key] for key in ("slug", "updatedAt", "notes") if key in recipe}


async def _snapshot(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject:
    expected = changes.get("expectedUpdatedAt")
    if not isinstance(expected, str) or not expected:
        raise ValueError("expectedUpdatedAt is required; re-read the recipe snapshot first.")
    original = await recipes.get_recipe(client, slug)
    if original.get("updatedAt") != expected:
        raise ValueError(
            "Stale snapshot: expectedUpdatedAt does not match the recipe's current updatedAt. "
            "Nothing was written. Re-read the recipe and use its new snapshot token."
        )
    return original


def _canonical_notes(notes: list[JsonObject]) -> list[JsonObject]:
    return [{**row, "referenceId": _reference(row.get("referenceId"))} for row in notes]


def _instructions(value: JsonValue | None) -> list[JsonObject]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("Invalid instruction references collection; nothing was written.")
    return [
        {key: item for key, item in row.items() if key != "id"}
        for row in value
        if isinstance(row, dict)
    ]


async def _write(
    client: MealieClient, slug: str, original: JsonObject, payload: JsonObject
) -> JsonObject:
    async def write_and_verify() -> JsonObject:
        updated = await recipes.patch_recipe(client, slug, payload)
        try:
            expected_notes = payload["notes"]
            assert isinstance(expected_notes, list)
            wanted = _canonical_notes([row for row in expected_notes if isinstance(row, dict)])
            if wanted != _canonical_notes(_notes(updated)):
                raise ValueError("Stored notes do not match the requested notes.")
            if (
                "recipeInstructions" in payload
                and _instructions(updated.get("recipeInstructions"))
                != payload["recipeInstructions"]
            ):
                raise ValueError("Stored instruction references do not match the requested values.")
        except ValueError as error:
            raise ValueError(
                "Recipe note verification failed after Mealie update. "
                "The write was not replayed; re-read the recipe before further changes."
            ) from error
        return updated

    if payload.get("notes") == original.get("notes", []) and (
        "recipeInstructions" not in payload
        or payload["recipeInstructions"] == _instructions(original.get("recipeInstructions", []))
    ):
        return original
    return await finish_verified_mutation(write_and_verify())


async def add_recipe_note(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject:
    original = await _snapshot(client, slug, changes)
    current = _notes(original)
    identifier = _reference(changes.get("referenceId", str(uuid4())))
    if any(_reference(row.get("referenceId")) == identifier for row in current):
        raise ValueError("referenceId already exists on this recipe; nothing was written.")
    title, text = changes.get("title"), changes.get("text")
    if not isinstance(title, str) or not isinstance(text, str):
        raise ValueError("Note title and text must be strings.")
    note: JsonObject = {"title": title, "text": text, "referenceId": identifier}
    return await _write(client, slug, original, {"notes": [*current, note]})


def _find(current: list[JsonObject], reference: JsonValue | None) -> int:
    identifier = _reference(reference)
    for index, row in enumerate(current):
        if _reference(row.get("referenceId")) == identifier:
            return index
    raise ValueError("referenceId does not exist on the current recipe; nothing was written.")


async def update_recipe_note(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject:
    original = await _snapshot(client, slug, changes)
    current = deepcopy(_notes(original))
    index = _find(current, changes.get("referenceId"))
    fields = [key for key in ("title", "text") if key in changes]
    if not fields or any(not isinstance(changes[key], str) for key in fields):
        raise ValueError("Supply title and/or text as strings (empty strings are allowed).")
    current[index].update({key: changes[key] for key in fields})
    return await _write(client, slug, original, {"notes": [row for row in current]})


async def delete_recipe_note(client: MealieClient, slug: str, changes: JsonObject) -> JsonObject:
    original = await _snapshot(client, slug, changes)
    current = _notes(original)
    index = _find(current, changes.get("referenceId"))
    identifier = _reference(current[index].get("referenceId"))
    steps = _instructions(original.get("recipeInstructions", []))
    linked = False
    for step in steps:
        if "noteReferences" not in step:
            continue
        references = step["noteReferences"]
        if not isinstance(references, list) or any(not isinstance(row, dict) for row in references):
            raise ValueError("Invalid instruction note references; nothing was written.")
        kept: list[JsonValue] = []
        for row in references:
            assert isinstance(row, dict)
            reference_id = row.get("referenceId")
            # Mealie permits unlinked NoteReference rows with a nullable UUID.
            if reference_id is not None and _reference(reference_id) == identifier:
                linked = True
            else:
                kept.append(row)
        step["noteReferences"] = kept
    if linked and changes.get("removeReferences") is not True:
        raise ValueError(
            "Note is linked from instructions. Set removeReferences=true explicitly to delete it."
        )
    payload: JsonObject = {
        "notes": [row for position, row in enumerate(current) if position != index]
    }
    if linked:
        payload["recipeInstructions"] = [step for step in steps]
    return await _write(client, slug, original, payload)
