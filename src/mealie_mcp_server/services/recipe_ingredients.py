"""Ordered ingredient mutation with narrow persistence checks and local recovery."""

import asyncio
from dataclasses import dataclass

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.organizer_resolution import to_organizer_item
from mealie_mcp_server.services.recipe_organizers import batch_slugs
from mealie_mcp_server.support.concurrency import map_with_concurrency
from mealie_mcp_server.support.mutations import finish_verified_mutation
from mealie_mcp_server.support.recipe_scan import to_array
from mealie_mcp_server.support.strings import trim

DELTA_FIELDS = ("addIngredients", "updateIngredients", "removeIngredientReferenceIds")
COPIED_FIELDS = ("quantity", "note", "display", "originalText", "title", "referenceId")


def _text(value: JsonValue | None) -> str:
    return trim(value) if isinstance(value, str) else ""


def _ref(value: JsonValue | None) -> str:
    return _text(value).lower()


def _pair(row: JsonObject, kind: str) -> None:
    identifier, name = _text(row.get(kind + "Id")), _text(row.get(kind + "Name"))
    if identifier and not name:
        raise ValueError(
            f"{kind}Id was given without {kind}Name — both are required to reference "
            f"an existing {kind}."
        )
    if not identifier and name:
        raise ValueError(
            f"{kind}Name was given without {kind}Id — both are required to reference "
            f"an existing {kind}."
        )


def _payload(row: JsonObject) -> JsonObject:
    _pair(row, "food")
    _pair(row, "unit")
    referenced = _ref(row.get("referencedRecipeId"))
    if referenced and (_text(row.get("foodId")) or _text(row.get("unitId"))):
        raise ValueError(
            "referencedRecipeId cannot be combined with foodId/unitId — a row that references "
            "a recipe is a sub-recipe, not a food."
        )
    result: JsonObject = {"food": None, "unit": None}
    for kind in ("food", "unit"):
        identifier, name = _text(row.get(kind + "Id")), _text(row.get(kind + "Name"))
        if identifier and name:
            result[kind] = {"id": identifier, "name": name}
    result.update({key: row[key] for key in COPIED_FIELDS if key in row})
    if referenced:
        result["referencedRecipe"] = {"id": referenced}
    return result


def _plan(changes: JsonObject) -> bool:
    delta = any(key in changes for key in DELTA_FIELDS)
    if "ingredients" in changes and delta:
        raise ValueError(
            "Use either ingredients (complete replacement) or the delta fields "
            "(addIngredients/updateIngredients/removeIngredientReferenceIds), not both."
        )
    if "ingredients" in changes:
        return True
    if not delta:
        raise ValueError(
            "Provide ingredients (complete replacement) or at least one of addIngredients, "
            "updateIngredients, removeIngredientReferenceIds."
        )
    if not any(changes.get(key) for key in DELTA_FIELDS):
        raise ValueError(
            "The delta contains no operations — supply at least one add, update, or removal."
        )
    return False


def _existing_input(row: JsonObject, index: int) -> JsonObject:
    result: JsonObject = {key: row[key] for key in COPIED_FIELDS if key in row}
    for kind in ("food", "unit"):
        entity = row.get(kind)
        if entity is None:
            continue
        identifier, name = (
            (entity.get("id"), entity.get("name")) if isinstance(entity, dict) else (None, None)
        )
        if (
            not isinstance(identifier, str)
            or not identifier
            or not isinstance(name, str)
            or not name
        ):
            raise ValueError(
                f"Existing ingredient {index} has a {kind} without a usable id and name; "
                "cannot apply a delta safely."
            )
        result[kind + "Id"], result[kind + "Name"] = identifier, name
    return result


@dataclass
class BuiltIngredients:
    inputs: list[JsonObject]
    payload: list[JsonObject]


def _build_delta(original: JsonObject, changes: JsonObject) -> BuiltIngredients:
    rows = to_array(original.get("recipeIngredient"))
    existing: dict[str, int] = {}
    duplicates: set[str] = set()
    for index, row in enumerate(rows):
        if key := _ref(row.get("referenceId")):
            if key in existing:
                duplicates.add(key)
            existing[key] = index
    problems: list[str] = []

    def require_existing(identifier: JsonValue | None, what: str) -> str:
        key = _ref(identifier)
        if not key:
            problems.append(f"{what} requires a non-empty referenceId.")
        elif key not in existing:
            problems.append(
                f"{what} references unknown referenceId '{identifier}' "
                "(not present on the recipe as currently stored)."
            )
        elif key in duplicates:
            problems.append(
                f"{what} references referenceId '{identifier}', which is ambiguous — "
                "several existing rows share it."
            )
        else:
            return key
        return ""

    removed: set[str] = set()
    removals = changes.get("removeIngredientReferenceIds")
    for identifier in removals if isinstance(removals, list) else []:
        key = require_existing(identifier, "Removal")
        if not key:
            continue
        if key in removed:
            problems.append(f"Duplicate removal of referenceId '{identifier}'.")
        removed.add(key)
    patches: dict[str, JsonObject] = {}
    for update in to_array(changes.get("updateIngredients")):
        identifier = update.get("referenceId")
        key = require_existing(identifier, "Update")
        if not key:
            continue
        if key in patches:
            problems.append(f"Duplicate update of referenceId '{identifier}'.")
        if key in removed:
            problems.append(f"referenceId '{identifier}' is both updated and removed.")
        for kind in ("food", "unit"):
            if kind + "Id" not in update and kind + "Name" not in update:
                continue
            if not _text(update.get(kind + "Id")) or not _text(update.get(kind + "Name")):
                problems.append(
                    f"Update of referenceId '{identifier}' must supply both {kind}Id and "
                    f"{kind}Name as non-blank values to replace the {kind}; a {kind} cannot "
                    "be cleared with a delta update (use the complete-replacement form)."
                )
        fields = {name: value for name, value in update.items() if name != "referenceId"}
        if not fields:
            problems.append(f"Update of referenceId '{identifier}' changes no fields.")
        patches[key] = fields
    added: set[str] = set()
    appended: list[JsonObject] = []
    before: dict[str, list[JsonObject]] = {}
    after: dict[str, list[JsonObject]] = {}
    for addition in to_array(changes.get("addIngredients")):
        ingredient = {
            key: value
            for key, value in addition.items()
            if key not in ("insertAfterReferenceId", "insertBeforeReferenceId")
        }
        key = _ref(ingredient.get("referenceId"))
        if key:
            if key in existing:
                problems.append(
                    f"Addition uses referenceId '{ingredient.get('referenceId')}', "
                    "which already exists on the recipe."
                )
            if key in added:
                problems.append(
                    f"Duplicate referenceId '{ingredient.get('referenceId')}' among additions."
                )
            added.add(key)
        if "insertAfterReferenceId" in addition and "insertBeforeReferenceId" in addition:
            problems.append(
                "An addition may set insertAfterReferenceId or insertBeforeReferenceId, not both."
            )
            continue
        anchor = addition.get("insertAfterReferenceId", addition.get("insertBeforeReferenceId"))
        if anchor is None:
            appended.append(ingredient)
            continue
        anchor_key = require_existing(anchor, "Addition anchor")
        if not anchor_key:
            continue
        if anchor_key in removed:
            problems.append(
                f"Addition is anchored to referenceId '{anchor}', which is being removed."
            )
            continue
        target = after if "insertAfterReferenceId" in addition else before
        target.setdefault(anchor_key, []).append(ingredient)
    if problems:
        raise ValueError("Invalid ingredient delta, nothing was written: " + " ".join(problems))
    inputs: list[JsonObject] = []
    payload: list[JsonObject] = []

    def emit(additions: list[JsonObject]) -> None:
        for ingredient in additions:
            inputs.append(ingredient)
            payload.append(_payload(ingredient))

    for index, row in enumerate(rows):
        key = _ref(row.get("referenceId"))
        if key and key in removed:
            continue
        emit(before.get(key, []))
        current = _existing_input(row, index)
        if key in patches:
            _pair(patches[key], "food")
            _pair(patches[key], "unit")
            current = {**current, **patches[key]}
            payload.append({**row, **_payload(current)})
        else:
            payload.append(row)
        inputs.append(current)
        emit(after.get(key, []))
    emit(appended)
    return BuiltIngredients(inputs, payload)


def _compatible_name(entity: JsonObject, requested: str, kind: str) -> bool:
    keys = (
        ("name", "pluralName", "abbreviation", "pluralAbbreviation")
        if kind == "unit"
        else ("name", "pluralName")
    )
    names = [entity.get(key) for key in keys] + [
        alias.get("name") for alias in to_array(entity.get("aliases"))
    ]
    return any(_ref(name) == _ref(requested) for name in names if _text(name))


def _verify(inputs: list[JsonObject], persisted: JsonValue | None) -> str | None:
    rows = to_array(persisted)
    if len(rows) != len(inputs):
        return f"Requested {len(inputs)} ingredient(s) but Mealie persisted {len(rows)}."
    for index, (requested, row) in enumerate(zip(inputs, rows, strict=True)):
        for kind in ("food", "unit"):
            identifier, name = (
                _text(requested.get(kind + "Id")),
                _text(requested.get(kind + "Name")),
            )
            if not identifier or not name:
                continue
            entity = row.get(kind)
            if entity is None or entity is False:
                return (
                    f"Ingredient {index} requested {kind}Id '{identifier}' ('{name}'), "
                    f"but Mealie persisted no {kind} association."
                )
            data = entity if isinstance(entity, dict) else {}
            actual_id = to_organizer_item(data)["id"]
            if data.get("id") != identifier:
                return (
                    f"Ingredient {index} requested {kind}Id '{identifier}' with "
                    f"{kind}Name '{name}', but Mealie persisted {kind} '{actual_id}'."
                )
            if not _compatible_name(data, name, kind):
                return (
                    f"Ingredient {index} requested {kind}Id '{identifier}' with "
                    f"{kind}Name '{name}', but Mealie persisted {kind} '{actual_id}' "
                    f"named '{to_organizer_item(data)['name']}'."
                )
        if referenced := _ref(requested.get("referencedRecipeId")):
            entity = row.get("referencedRecipe")
            if entity is None or entity is False:
                return (
                    f"Ingredient {index} requested referencedRecipeId '{referenced}', "
                    "but Mealie persisted no referenced recipe."
                )
            data = entity if isinstance(entity, dict) else {}
            if data.get("id") != referenced:
                return (
                    f"Ingredient {index} requested referencedRecipeId '{referenced}', "
                    "but Mealie persisted referenced recipe "
                    f"'{to_organizer_item(data)['id']}'."
                )
    return None


class IngredientVerificationError(ValueError):
    def __init__(
        self, message: str, rollback_succeeded: bool, rollback_error: str | None = None
    ) -> None:
        super().__init__(message)
        self.rollback_succeeded = rollback_succeeded
        self.rollback_error = rollback_error


async def update_recipe_ingredients(
    client: MealieClient, slug: str, changes: JsonObject, *, cleanup_timeout: float = 35
) -> JsonObject:
    result = await _write_ingredients(client, slug, changes, cleanup_timeout=cleanup_timeout)
    return result.recipe


@dataclass
class IngredientWriteResult:
    recipe: JsonObject
    request_count: int
    ingredient_count: int


async def _write_ingredients(
    client: MealieClient, slug: str, changes: JsonObject, *, cleanup_timeout: float = 35
) -> IngredientWriteResult:
    replacement = _plan(changes)
    count = 0
    try:
        rows = to_array(changes.get("ingredients"))
        built = BuiltIngredients(rows, [_payload(row) for row in rows]) if replacement else None
        original = await recipes.get_recipe(client, slug)
        count += 1
        if built is None:
            built = _build_delta(original, changes)
        own_id = _ref(original.get("id"))
        if own_id and any(_ref(row.get("referencedRecipeId")) == own_id for row in built.inputs):
            raise ValueError(
                f"referencedRecipeId '{own_id}' is the recipe being edited — "
                "a recipe cannot reference itself. No changes were written."
            )
        referenced_ids = list(
            dict.fromkeys(
                value for row in built.inputs if (value := _ref(row.get("referencedRecipeId")))
            )
        )

        async def resolve(identifier: str) -> None:
            try:
                referenced = await recipes.get_recipe(client, identifier)
            except MealieApiError as error:
                if error.status == 404:
                    raise ValueError(
                        f"referencedRecipeId '{identifier}' does not match any recipe in Mealie. "
                        "No changes were written."
                    ) from None
                raise
            if referenced.get("id") != identifier:
                raise ValueError(
                    f"referencedRecipeId '{identifier}' resolved to a different recipe "
                    f"('{to_organizer_item(referenced)['id']}'). No changes were written."
                )

        await asyncio.gather(*(resolve(identifier) for identifier in referenced_ids))
        count += len(referenced_ids)
    except Exception as error:
        error.__dict__["request_count"] = count
        raise

    async def write_and_verify() -> IngredientWriteResult:
        nonlocal count
        try:
            assert built is not None
            updated = await recipes.patch_recipe(
                client, slug, {"recipeIngredient": [*built.payload]}
            )
            count += 1
            failure = _verify(built.inputs, updated.get("recipeIngredient"))
            if not failure:
                return IngredientWriteResult(updated, count, len(built.inputs))
            rollback = to_array(original.get("recipeIngredient"))
            if replacement:
                rollback = [
                    {**row, "referenceId": reference}
                    if index < len(built.inputs)
                    and (reference := _text(built.inputs[index].get("referenceId")))
                    else row
                    for index, row in enumerate(rollback)
                ]
            try:
                await recipes.patch_recipe(client, slug, {"recipeIngredient": [*rollback]})
            except Exception as error:
                count += 1
                message = str(error)
                raise IngredientVerificationError(
                    f"Structured ingredient verification failed after Mealie update: {failure} "
                    f"Rollback to the original recipe ALSO failed ({message}) — "
                    "recipe state may require manual inspection.",
                    False,
                    message,
                ) from error
            count += 1
            raise IngredientVerificationError(
                f"Structured ingredient verification failed after Mealie update: {failure} "
                "Original recipe was restored successfully.",
                True,
            )
        except Exception as error:
            error.__dict__["request_count"] = count
            raise

    return await finish_verified_mutation(write_and_verify(), cleanup_timeout=cleanup_timeout)


async def update_recipe_ingredients_batch(
    client: MealieClient, updates: list[JsonObject]
) -> JsonObject:
    batch_slugs(updates, limit=25)
    counts = [0] * len(updates)

    async def apply(item: tuple[int, JsonObject]) -> JsonValue:
        index, update = item
        slug = update["slug"]
        assert isinstance(slug, str)
        try:
            result = await _write_ingredients(
                client, slug, {key: value for key, value in update.items() if key != "slug"}
            )
            counts[index] = result.request_count
            return {"slug": slug, "success": True, "ingredientCount": result.ingredient_count}
        except Exception as error:
            request_count = getattr(error, "request_count", 0)
            counts[index] = request_count if isinstance(request_count, int) else 0
            detail: JsonObject = {"message": str(error)}
            if isinstance(error, IngredientVerificationError):
                detail["rollbackSucceeded"] = error.rollback_succeeded
                if error.rollback_error is not None:
                    detail["rollbackError"] = error.rollback_error
            elif isinstance(error, MealieApiError):
                detail["status"] = error.status
            return {"slug": slug, "success": False, "error": detail}

    results = await map_with_concurrency(list(enumerate(updates)), 5, apply)
    succeeded = sum(
        isinstance(result, dict) and result.get("success") is True for result in results
    )
    return {
        "requestedCount": len(updates),
        "succeededCount": succeeded,
        "failedCount": len(updates) - succeeded,
        "results": results,
        "apiRequestCount": sum(counts),
    }
