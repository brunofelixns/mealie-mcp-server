"""Snapshot-indexed instruction edits; compare stored content, never ephemeral IDs."""

import re
from dataclasses import dataclass, replace

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient, scalar_string
from mealie_mcp_server.mealie.errors import MealieApiError
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.services.recipe_organizers import batch_slugs
from mealie_mcp_server.support.concurrency import map_with_concurrency
from mealie_mcp_server.support.mutations import finish_verified_mutation
from mealie_mcp_server.support.recipe_scan import is_number, to_array
from mealie_mcp_server.support.strings import trim

UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
DELTA_FIELDS = ("addInstructions", "updateInstructions", "removeInstructionIndexes")


def _string(value: JsonValue | None) -> str:
    return value if isinstance(value, str) else ""


def _records(value: JsonValue | None) -> list[JsonObject]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _references(value: JsonValue | None) -> list[str]:
    return [
        identifier.lower()
        for row in _records(value)
        if isinstance(identifier := row.get("referenceId"), str) and identifier
    ]


def _sorted_refs(values: list[str]) -> tuple[str, ...]:
    return tuple(
        sorted(values, key=lambda value: value.encode("utf-16-be", errors="surrogatepass"))
    )


@dataclass(frozen=True)
class CanonicalInstruction:
    text: str
    title: str
    summary: str
    ingredient_reference_ids: tuple[str, ...]
    note_reference_ids: tuple[str, ...]


@dataclass
class DraftInstruction:
    canonical: CanonicalInstruction
    payload: JsonObject


def _canonical(row: JsonObject) -> CanonicalInstruction:
    return CanonicalInstruction(
        _string(row.get("text")),
        _string(row.get("title")),
        _string(row.get("summary")),
        _sorted_refs(_references(row.get("ingredientReferences"))),
        _sorted_refs(_references(row.get("noteReferences"))),
    )


def _canonical_list(value: JsonValue | None) -> list[CanonicalInstruction]:
    return (
        [_canonical(row if isinstance(row, dict) else {}) for row in value]
        if isinstance(value, list)
        else []
    )


def _first_difference(
    expected: list[CanonicalInstruction], actual: list[CanonicalInstruction]
) -> str | None:
    if len(expected) != len(actual):
        return f"Expected {len(expected)} instruction(s) but Mealie persisted {len(actual)}."
    for index, (wanted, stored) in enumerate(zip(expected, actual, strict=True)):
        for key in ("text", "title", "summary"):
            if getattr(wanted, key) != getattr(stored, key):
                return f"Instruction {index} {key} does not match the requested value."
        if wanted.ingredient_reference_ids != stored.ingredient_reference_ids:
            return f"Instruction {index} ingredient references do not match the requested value."
        if wanted.note_reference_ids != stored.note_reference_ids:
            return f"Instruction {index} note references do not match the expected value."
    return None


def _without_id(row: JsonObject) -> JsonObject:
    return {key: value for key, value in row.items() if key != "id"}


def _payload(
    base: JsonObject,
    canonical: CanonicalInstruction,
    ingredient: list[str] | None = None,
    note: list[str] | None = None,
) -> JsonObject:
    result: JsonObject = {
        **base,
        "text": canonical.text,
        "title": canonical.title,
        "summary": canonical.summary,
    }
    if ingredient is not None:
        result["ingredientReferences"] = [{"referenceId": identifier} for identifier in ingredient]
    if note is not None:
        result["noteReferences"] = [{"referenceId": identifier} for identifier in note]
    return result


def _plan(changes: JsonObject) -> bool:
    delta = any(key in changes for key in DELTA_FIELDS)
    if "instructions" in changes and delta:
        raise ValueError(
            "Use either instructions (complete replacement) or the delta fields "
            "(addInstructions/updateInstructions/removeInstructionIndexes), not both."
        )
    if "instructions" in changes:
        return True
    if not delta:
        raise ValueError(
            "Provide instructions (complete replacement) or at least one of "
            "addInstructions, updateInstructions, removeInstructionIndexes."
        )
    if not any(changes.get(key) for key in DELTA_FIELDS):
        raise ValueError(
            "The delta contains no operations — supply at least one add, update, or removal."
        )
    return False


def _validate_refs(
    value: JsonValue | None, known: set[str], what: str, problems: list[str]
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for identifier in value if isinstance(value, list) else []:
        if not isinstance(identifier, str) or not UUID_PATTERN.fullmatch(identifier):
            problems.append(f"{what}: ingredientReferenceId '{identifier}' is not a valid UUID.")
            continue
        key = identifier.lower()
        if key in seen:
            problems.append(f"{what}: duplicate ingredientReferenceId '{identifier}'.")
            continue
        seen.add(key)
        if key not in known:
            problems.append(
                f"{what}: ingredientReferenceId '{identifier}' does not exist on the recipe's "
                "current ingredients. If this ID came from the guarded recipe snapshot, the "
                "ingredient may have no durably stored referenceId: older Mealie rows can have "
                "a NULL reference_id, causing Mealie to synthesize a different UUID on every read. "
                "Pin the ingredient identities with update_recipe_ingredients using the "
                "complete-replacement form: send the recipe's full current ingredient collection "
                "and explicitly preserve/supply a referenceId for every continuing row. Then "
                "re-read the recipe and retry update_recipe_instructions using the newly "
                "returned updatedAt and referenceIds."
            )
            continue
        result.append(key)
    return result


def _new_draft(
    row: JsonObject, known: set[str], what: str, problems: list[str], allow_notes: bool
) -> DraftInstruction | None:
    text = row.get("text")
    if not isinstance(text, str) or not trim(text):
        problems.append(f"{what}: text is required and must not be blank.")
        return None
    ingredient = _validate_refs(row.get("ingredientReferenceIds"), known, what, problems)
    note: list[str] = []
    if allow_notes:
        note_ids = row.get("noteReferenceIds")
        for identifier in note_ids if isinstance(note_ids, list) else []:
            if not isinstance(identifier, str) or not UUID_PATTERN.fullmatch(identifier):
                problems.append(f"{what}: noteReferenceId '{identifier}' is not a valid UUID.")
            else:
                note.append(identifier.lower())
    canonical = CanonicalInstruction(
        text,
        _string(row.get("title")),
        _string(row.get("summary")),
        _sorted_refs(ingredient),
        _sorted_refs(note),
    )
    return DraftInstruction(canonical, _payload({}, canonical, ingredient, note))


def _check_index(
    value: JsonValue | None, length: int, what: str, problems: list[str]
) -> int | None:
    if not is_number(value) or int(value) != value or value < 0 or value >= length:
        problems.append(
            f"{what}: index {value} does not exist (recipe has {length} "
            f"instruction(s), valid indexes 0-{length - 1})."
        )
        return None
    return int(value)


def _replacement(rows: list[JsonObject], known: set[str]) -> list[DraftInstruction]:
    problems: list[str] = []
    result = [
        draft
        for index, row in enumerate(rows)
        if (draft := _new_draft(row, known, f"instructions[{index}]", problems, True))
    ]
    if problems:
        raise ValueError("Invalid instruction request, nothing was written: " + " ".join(problems))
    return result


def _apply_update(raw: JsonObject, update: JsonObject) -> DraftInstruction:
    base = _canonical(raw)
    ingredient = update.get("ingredientReferenceIds")
    new_refs = (
        [identifier.lower() for identifier in ingredient if isinstance(identifier, str)]
        if isinstance(ingredient, list)
        else None
    )
    canonical = replace(
        base,
        text=_string(update["text"]) if "text" in update else base.text,
        title=_string(update["title"]) if "title" in update else base.title,
        summary=_string(update["summary"]) if "summary" in update else base.summary,
        ingredient_reference_ids=_sorted_refs(new_refs)
        if new_refs is not None
        else base.ingredient_reference_ids,
    )
    return DraftInstruction(canonical, _payload(_without_id(raw), canonical, new_refs))


def _delta(
    current: list[JsonObject], changes: JsonObject, known: set[str]
) -> list[DraftInstruction]:
    length = len(current)
    problems: list[str] = []
    removed: set[int] = set()
    removal_list = changes.get("removeInstructionIndexes")
    for value in removal_list if isinstance(removal_list, list) else []:
        index = _check_index(value, length, "Removal", problems)
        if index is None:
            continue
        if index in removed:
            problems.append(f"Removal: duplicate index {index}.")
        removed.add(index)
    updates: dict[int, JsonObject] = {}
    for update in to_array(changes.get("updateInstructions")):
        value = update.get("index")
        what = f"Update of index {value}"
        index = _check_index(value, length, what, problems)
        if index is None:
            continue
        if index in updates:
            problems.append(f"{what}: index appears more than once in updateInstructions.")
        if index in removed:
            problems.append(f"{what}: instruction is both updated and removed.")
        if "text" in update and not trim(_string(update["text"])):
            problems.append(f"{what}: text must not be blank.")
        if not any(key in update for key in ("text", "title", "summary", "ingredientReferenceIds")):
            problems.append(f"{what}: changes no fields.")
        if "ingredientReferenceIds" in update:
            _validate_refs(update["ingredientReferenceIds"], known, what, problems)
        updates[index] = update
    gaps: dict[int, list[DraftInstruction]] = {}
    directions: dict[int, set[str]] = {}
    appended: list[DraftInstruction] = []
    for index, addition in enumerate(to_array(changes.get("addInstructions"))):
        what = f"Addition {index}"
        draft = _new_draft(addition, known, what, problems, False)
        if "insertBeforeIndex" in addition and "insertAfterIndex" in addition:
            problems.append(f"{what}: set insertBeforeIndex or insertAfterIndex, not both.")
            continue
        if "insertBeforeIndex" not in addition and "insertAfterIndex" not in addition:
            if draft is not None:
                appended.append(draft)
            continue
        before = "insertBeforeIndex" in addition
        anchor = _check_index(
            addition.get("insertBeforeIndex" if before else "insertAfterIndex"),
            length,
            what + " anchor",
            problems,
        )
        if anchor is None:
            continue
        if anchor in removed:
            problems.append(f"{what}: anchored to index {anchor}, which is being removed.")
            continue
        if draft is None:
            continue
        gap = anchor if before else anchor + 1
        directions.setdefault(gap, set()).add("before" if before else "after")
        gaps.setdefault(gap, []).append(draft)
    for gap, values in directions.items():
        if len(values) > 1:
            problems.append(
                f"Additions target the same gap (between instruction {gap - 1} and "
                f"{gap}) through opposite anchors (insertAfterIndex and "
                "insertBeforeIndex) — ambiguous; use one direction."
            )
    if problems:
        raise ValueError("Invalid instruction request, nothing was written: " + " ".join(problems))
    result: list[DraftInstruction] = []
    for index in range(length + 1):
        result.extend(gaps.get(index, []))
        if index == length or index in removed:
            continue
        row = current[index]
        result.append(
            _apply_update(row, updates[index])
            if index in updates
            else DraftInstruction(_canonical(row), _without_id(row))
        )
    result.extend(appended)
    return result


class StaleInstructionSnapshotError(ValueError):
    pass


class InstructionVerificationError(ValueError):
    def __init__(
        self, message: str, rollback_succeeded: bool, rollback_error: str | None = None
    ) -> None:
        super().__init__(message)
        self.rollback_succeeded = rollback_succeeded
        self.rollback_error = rollback_error


async def update_recipe_instructions(
    client: MealieClient, slug: str, changes: JsonObject, *, cleanup_timeout: float = 35
) -> JsonObject:
    return (
        await _write_instructions(client, slug, changes, cleanup_timeout=cleanup_timeout)
    ).recipe


@dataclass
class InstructionWriteResult:
    recipe: JsonObject
    request_count: int
    instruction_count: int
    changed: bool


async def _write_instructions(
    client: MealieClient, slug: str, changes: JsonObject, *, cleanup_timeout: float = 35
) -> InstructionWriteResult:
    count = 0
    try:
        expected = changes.get("expectedUpdatedAt")
        if not isinstance(expected, str) or not expected:
            raise ValueError(
                "expectedUpdatedAt is required — pass the exact updatedAt "
                "from a prior get_recipe_detailed."
            )
        replacement = _plan(changes)
        count += 1
        original = await recipes.get_recipe(client, slug)
        if original.get("updatedAt") != expected:
            actual = original.get("updatedAt")
            actual_text = (
                "undefined"
                if "updatedAt" not in original
                else "null"
                if actual is None
                else scalar_string(actual)
                if isinstance(actual, (str, int, float, bool))
                else "[object Object]"
            )
            raise StaleInstructionSnapshotError(
                f"Stale snapshot for recipe '{slug}': expectedUpdatedAt '{expected}' does not "
                f"match the recipe's current updatedAt '{actual_text}'. Nothing was written. "
                "Re-read the recipe with get_recipe_detailed and retry from the new snapshot "
                "(instruction indexes and ingredient referenceIds may have changed)."
            )
        known = set(_references(original.get("recipeIngredient")))
        current = _records(original.get("recipeInstructions"))
        desired = (
            _replacement(to_array(changes.get("instructions")), known)
            if replacement
            else _delta(current, changes, known)
        )
        canonical = [draft.canonical for draft in desired]
        if _first_difference(canonical, [_canonical(row) for row in current]) is None:
            return InstructionWriteResult(original, count, len(desired), False)
    except Exception as error:
        error.__dict__["request_count"] = count
        raise

    async def write_and_verify() -> InstructionWriteResult:
        nonlocal count
        try:
            count += 1
            updated = await recipes.patch_recipe(
                client, slug, {"recipeInstructions": [draft.payload for draft in desired]}
            )
            failure = _first_difference(
                canonical, _canonical_list(updated.get("recipeInstructions"))
            )
            if failure is None:
                return InstructionWriteResult(updated, count, len(desired), True)
            rollback_failure: str | None = None
            count += 1
            try:
                restored = await recipes.patch_recipe(
                    client, slug, {"recipeInstructions": [_without_id(row) for row in current]}
                )
                mismatch = _first_difference(
                    [_canonical(row) for row in current],
                    _canonical_list(restored.get("recipeInstructions")),
                )
                if mismatch:
                    rollback_failure = (
                        "Mealie's response after rollback did not match the original instructions: "
                        + mismatch
                    )
            except Exception as error:
                rollback_failure = str(error)
            if rollback_failure:
                raise InstructionVerificationError(
                    f"Instruction verification failed after Mealie update: {failure} Rollback "
                    f"to the original instructions ALSO failed ({rollback_failure}) — recipe "
                    "state may require manual inspection.",
                    False,
                    rollback_failure,
                )
            raise InstructionVerificationError(
                f"Instruction verification failed after Mealie update: {failure} Original "
                "instructions were restored successfully (instruction ids were regenerated, "
                "which is expected).",
                True,
            )
        except Exception as error:
            error.__dict__["request_count"] = count
            raise

    return await finish_verified_mutation(write_and_verify(), cleanup_timeout=cleanup_timeout)


async def update_recipe_instructions_batch(
    client: MealieClient, updates: list[JsonObject]
) -> JsonObject:
    batch_slugs(updates, limit=25)
    counts = [0] * len(updates)

    async def apply(item: tuple[int, JsonObject]) -> JsonValue:
        index, update = item
        slug = update["slug"]
        assert isinstance(slug, str)
        try:
            result = await _write_instructions(
                client, slug, {key: value for key, value in update.items() if key != "slug"}
            )
            counts[index] = result.request_count
            return {
                "slug": slug,
                "success": True,
                "instructionCount": result.instruction_count,
                "changed": result.changed,
            }
        except Exception as error:
            value = getattr(error, "request_count", 0)
            counts[index] = value if isinstance(value, int) else 0
            detail: JsonObject = {"message": str(error)}
            if isinstance(error, InstructionVerificationError):
                detail["rollbackSucceeded"] = error.rollback_succeeded
                if error.rollback_error is not None:
                    detail["rollbackError"] = error.rollback_error
            elif isinstance(error, StaleInstructionSnapshotError):
                detail["stale"] = True
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
