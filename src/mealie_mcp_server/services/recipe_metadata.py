"""Focused metadata mutation without resetting omitted nested provider fields."""

from copy import deepcopy

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.common import JsonObject


def _mapping(value: JsonValue | None, field: str) -> JsonObject:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {field} object in recipe metadata.")
    return deepcopy(value)


def _same(actual: JsonValue, expected: JsonValue) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(_same(actual[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_same(left, right) for left, right in zip(actual, expected, strict=True))
        )
    return (type(actual) is type(expected) and actual == expected) or (
        isinstance(actual, (float, int))
        and not isinstance(actual, bool)
        and isinstance(expected, (float, int))
        and not isinstance(expected, bool)
        and actual == expected
    )


def _contains(actual: JsonValue, expected: JsonValue) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _contains(actual[key], value) for key, value in expected.items()
        )
    return _same(actual, expected)


async def update_recipe_metadata(
    client: MealieClient, slug: str, changes: JsonObject
) -> JsonObject:
    values = {
        key: value for key, value in changes.items() if key not in {"slug", "expectedUpdatedAt"}
    }
    if not values or all(value == {} or value == [] for value in values.values()):
        raise ValueError("Provide at least one metadata change.")
    extras = values.get("extras", {})
    removals = values.pop("removeExtraKeys", [])
    if not isinstance(extras, dict) or not isinstance(removals, list):
        raise ValueError("Invalid extras mutation.")
    if any(key in extras for key in removals if isinstance(key, str)):
        raise ValueError("An extra key cannot be both set and removed.")
    original = await recipes.get_recipe(client, slug)
    if original.get("updatedAt") != changes.get("expectedUpdatedAt"):
        raise ValueError("Stale snapshot. Re-read get_recipe_detailed before editing metadata.")
    patch: JsonObject = {}
    for field, value in values.items():
        desired = value
        if field in {"settings", "nutrition"} and value is not None:
            if not isinstance(value, dict):
                raise ValueError(f"Invalid {field} mutation.")
            if not value:
                continue
            desired = {**_mapping(original.get(field), field), **value}
        if field == "extras":
            desired = {**_mapping(original.get(field), field), **extras}
            for key in removals:
                if isinstance(key, str):
                    desired.pop(key, None)
        if field not in original or not _same(original[field], desired):
            patch[field] = desired
    if removals and "extras" not in values:
        desired_extras = _mapping(original.get("extras"), "extras")
        for key in removals:
            if isinstance(key, str):
                desired_extras.pop(key, None)
        if not _same(original.get("extras"), desired_extras):
            patch["extras"] = desired_extras
    if not patch:
        return original
    updated = await recipes.patch_recipe(client, slug, patch)
    if any(
        field not in updated
        or not _contains(updated[field], value)
        or (field == "extras" and not _same(updated[field], value))
        for field, value in patch.items()
    ):
        raise ValueError(
            "Metadata verification failed after the write. Inspect get_recipe_detailed; "
            "the write was not retried or rolled back automatically."
        )
    return updated
