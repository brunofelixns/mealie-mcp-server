"""New numeric contracts advertise the same bounds enforced by strict inputs."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from mealie_mcp_server.models.common import provided_fields
from mealie_mcp_server.models.inputs.mealplan_advanced import (
    GetMealplanIcalFeedInput,
    ListMealplanEntriesInput,
    MealplanEntryIdInput,
    UpdateMealplanEntryInput,
)
from mealie_mcp_server.models.inputs.recipe_collections import ListCollectionsInput
from mealie_mcp_server.models.inputs.recipe_jobs import (
    ImportRecipesFromUrlsInput,
    UpdateRecipeMetadataBatchInput,
)

BOUNDS = [
    pytest.param(ListCollectionsInput, {}, ("page",), 1, None, id="collection-page"),
    pytest.param(ListCollectionsInput, {}, ("perPage",), 1, 1000, id="collection-page-size"),
    pytest.param(ListMealplanEntriesInput, {}, ("page",), 1, None, id="mealplan-page"),
    pytest.param(ListMealplanEntriesInput, {}, ("perPage",), 1, 1000, id="mealplan-page-size"),
    pytest.param(MealplanEntryIdInput, {}, ("entryId",), 1, None, id="entry-id"),
    pytest.param(
        UpdateMealplanEntryInput,
        {"changes": {"text": ""}},
        ("entryId",),
        1,
        None,
        id="update-entry-id",
    ),
    pytest.param(
        GetMealplanIcalFeedInput,
        {"token": "fixture"},
        ("duration",),
        1,
        1440,
        id="calendar-duration",
    ),
    pytest.param(
        ImportRecipesFromUrlsInput,
        {
            "imports": [
                {
                    "url": "https://recipes.test/soup",
                    "categories": [{"name": "Soup", "slug": "soup"}],
                }
            ]
        },
        ("imports", 0, "categories", 0, "recipeCount"),
        0,
        None,
        id="bulk-category-count",
    ),
    pytest.param(
        ImportRecipesFromUrlsInput,
        {
            "imports": [
                {"url": "https://recipes.test/soup", "tags": [{"name": "Soup", "slug": "soup"}]}
            ]
        },
        ("imports", 0, "tags", 0, "recipeCount"),
        0,
        None,
        id="bulk-tag-count",
    ),
    pytest.param(
        UpdateRecipeMetadataBatchInput,
        {"items": [{"slug": "soup", "expectedUpdatedAt": "2026-11-03T00:00:00Z", "name": "Soup"}]},
        ("concurrency",),
        1,
        5,
        id="metadata-concurrency",
    ),
]


def replace_number(arguments, path, value):
    arguments = deepcopy(arguments)
    target = arguments
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return arguments


def number_at(arguments, path):
    for key in path:
        arguments = arguments[key]
    return arguments


@pytest.mark.parametrize("model,arguments,path,minimum,maximum", BOUNDS)
def test_model_schema_rejects_values_outside_runtime_bounds(
    model, arguments, path, minimum, maximum
):
    validator = Draft202012Validator(model.model_json_schema(by_alias=True))
    rejected = [minimum - 1]
    if maximum is not None:
        rejected.append(maximum + 1)
    for value in rejected:
        invalid = replace_number(arguments, path, value)
        with pytest.raises(ValidationError):
            model.model_validate(invalid, strict=True)
        assert not validator.is_valid(invalid), f"Schema accepts out-of-bound {path}={value}"


@pytest.mark.parametrize("model,arguments,path,minimum,maximum", BOUNDS)
@pytest.mark.parametrize("value", [True, False, None, 1.25, "1"])
def test_model_and_schema_reject_non_json_integers(model, arguments, path, minimum, maximum, value):
    invalid = replace_number(arguments, path, value)
    with pytest.raises(ValidationError):
        model.model_validate(invalid, strict=True)
    assert not Draft202012Validator(model.model_json_schema(by_alias=True)).is_valid(invalid)


@pytest.mark.parametrize("model,arguments,path,minimum,maximum", BOUNDS)
@pytest.mark.parametrize("whole_float", [False, True])
def test_valid_bounds_normalize_whole_floats_without_widening_integer_inputs(
    model, arguments, path, minimum, maximum, whole_float
):
    for value in [minimum, maximum if maximum is not None else minimum + 17]:
        valid = replace_number(arguments, path, float(value) if whole_float else value)
        validated = model.model_validate(valid, strict=True)
        normalized = number_at(provided_fields(validated), path)
        assert normalized == value
        assert type(normalized) is int
        assert Draft202012Validator(model.model_json_schema(by_alias=True)).is_valid(valid)


@pytest.mark.parametrize(
    "model,arguments,defaults",
    [
        (ListCollectionsInput, {}, {"page": 1, "perPage": 50}),
        (ListMealplanEntriesInput, {}, {"page": 1, "perPage": 50}),
        (GetMealplanIcalFeedInput, {"token": "fixture"}, {"duration": 60}),
        (
            UpdateRecipeMetadataBatchInput,
            {
                "items": [
                    {"slug": "soup", "expectedUpdatedAt": "2026-11-03T00:00:00Z", "name": "Soup"}
                ]
            },
            {"concurrency": 3},
        ),
    ],
)
def test_omitted_numbers_keep_defaults_without_becoming_supplied(model, arguments, defaults):
    request = model.model_validate(arguments)
    all_fields = request.model_dump(by_alias=True)
    assert {name: all_fields[name] for name in defaults} == defaults
    assert provided_fields(request) == arguments
    assert Draft202012Validator(model.model_json_schema(by_alias=True)).is_valid(arguments)


def test_bulk_recipe_count_preserves_omission_and_explicit_zero():
    arguments = {
        "imports": [
            {
                "url": "https://recipes.test/soup",
                "categories": [{"name": "Soup", "slug": "soup"}],
                "tags": [{"name": "Soup", "slug": "soup", "recipeCount": 0.0}],
            }
        ]
    }
    request = ImportRecipesFromUrlsInput.model_validate(arguments)
    payload = provided_fields(request)
    assert "recipeCount" not in payload["imports"][0]["categories"][0]
    assert payload["imports"][0]["tags"][0]["recipeCount"] == 0
    assert type(payload["imports"][0]["tags"][0]["recipeCount"]) is int
