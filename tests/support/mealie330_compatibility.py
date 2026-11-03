"""D14's explicit additive expectations; original migration captures stay immutable."""

import json
from copy import deepcopy
from pathlib import Path

SCENARIOS = frozenset(
    {
        "update_recipe_ingredients.basic",
        "update_recipe_ingredients_batch.basic",
        "update_recipe_ingredients.rollback",
        "update_recipe_ingredients.canonical_alias",
    }
)
OVERLAY = json.loads(
    (
        Path(__file__).parents[1] / "fixtures" / "mealie330" / "ingredient-preservation.json"
    ).read_text()
)
assert OVERLAY["documentedDifference"] == "D14"
assert set(OVERLAY["scenarios"]) == SCENARIOS
assert OVERLAY["preservedFields"] == {"providerExtra": {"keep": True}}


def _preserve(recipe):
    if not isinstance(recipe, dict):
        return
    for row in recipe.get("recipeIngredient", []):
        if row.get("referenceId") == OVERLAY["referenceId"]:
            for key, value in OVERLAY["preservedFields"].items():
                if key in row:
                    assert row[key] == value, "D14 cannot alter an existing field"
                else:
                    row[key] = deepcopy(value)


def apply_request_overlay(scenario, requests):
    """Add exactly the documented retained row field, keeping strict equality elsewhere."""
    if scenario not in SCENARIOS:
        return requests
    patched = deepcopy(requests)
    for request in patched:
        _preserve(request.get("body"))
        _preserve(request.get("response"))
    return patched


def apply_result_overlay(scenario, result):
    if scenario not in SCENARIOS or result.get("isError"):
        return result
    patched = deepcopy(result)
    for block in patched.get("content", []):
        if block.get("type") == "text":
            value = json.loads(block["text"])
            original = deepcopy(value)
            _preserve(value)
            if value != original:
                block["text"] = json.dumps(value, separators=(",", ":"))
    return patched
