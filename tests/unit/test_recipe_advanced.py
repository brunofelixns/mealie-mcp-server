"""Advanced recipe behavior against the actual native HTTP boundary."""

import json
from copy import deepcopy

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_ingredients import update_recipe_ingredients

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
FOOD = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SUB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REF = "11111111-1111-4111-8111-111111111111"


@pytest.mark.parametrize("replacement", [False, True])
async def test_legacy_edit_retains_continuing_row_provider_data(replacement):
    original = {
        "slug": "soup",
        "recipeIngredient": [
            {
                "referenceId": REF,
                "note": "old",
                "food": {
                    "id": FOOD,
                    "name": "Salt",
                    "substitutions": [
                        {"substituteFoodId": SUB},
                        {"note": "Global text alternative"},
                    ],
                },
                "unit": None,
                "substitutions": [
                    {"substituteFoodId": SUB, "note": "keep"},
                    {"note": "Recipe text alternative"},
                ],
                "future": {"zero": 0, "enabled": False},
                "referencedRecipe": None,
            }
        ],
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=original)
        body = json.loads(request.content)
        writes.append(body)
        return httpx.Response(200, json={**original, **body})

    changes = (
        {"ingredients": [{"referenceId": REF, "note": "new", "foodId": FOOD, "foodName": "Salt"}]}
        if replacement
        else {"updateIngredients": [{"referenceId": REF, "note": "new"}]}
    )
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await update_recipe_ingredients(client, "soup", changes)
    stored = writes[0]["recipeIngredient"][0]
    expected = {**original["recipeIngredient"][0], "note": "new"}
    if replacement:
        expected.pop("referencedRecipe")
    assert stored == expected


async def test_legacy_food_update_retains_native_substitutions():
    from mealie_mcp_server.mealie.api.foods import update_food

    original = {
        "id": FOOD,
        "name": "Salt",
        "aliases": [],
        "substitutions": [{"substituteFoodId": SUB, "note": "keep"}],
        "extras": {"keep": True},
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=original)
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**original, **writes[-1]})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await update_food(client, FOOD, {"name": "Sea salt", "aliases": ["sal"]})
    assert writes == [{**original, "name": "Sea salt", "aliases": [{"name": "sal"}]}]


async def test_native_query_filters_and_parser_have_no_implicit_recipe_write():
    from mealie_mcp_server.services import recipe_advanced as service

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json={"items": []} if request.method == "GET" else {"ingredient": {"note": "Salt"}}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await service.search_recipes(
            client,
            {
                "categories": ["soup", "winter"],
                "tools": ["pot"],
                "foods": [FOOD],
                "households": [FOOD],
                "cookbook": "week",
                "requireAllFoods": False,
                "orderBy": "name",
                "orderDirection": "asc",
                "queryFilter": "rating>=0",
                "paginationSeed": "seed",
                "page": 2,
                "perPage": 3,
            },
        )
        await service.get_recipe_suggestions(
            client,
            {"foods": [FOOD], "includeSubstitutions": False, "maxMissingFoods": 0, "limit": 2},
        )
        await service.parse_recipe_ingredient(
            client, {"parser": "brute", "ingredient": "1 tsp Salt"}
        )
        await service.parse_recipe_ingredients(
            client, {"parser": "nlp", "ingredients": ["Salt", "Pepper"]}
        )
    assert calls[0].url.params.get_list("categories") == ["soup", "winter"]
    assert dict(calls[0].url.params) | {} == {
        "categories": "soup",
        "tools": "pot",
        "foods": FOOD,
        "households": FOOD,
        "cookbook": "week",
        "requireAllFoods": "false",
        "orderBy": "name",
        "orderDirection": "asc",
        "queryFilter": "rating>=0",
        "paginationSeed": "seed",
        "page": "2",
        "perPage": "3",
    }
    assert calls[1].url.path == "/api/recipes/suggestions"
    assert dict(calls[1].url.params) == {
        "foods": FOOD,
        "includeSubstitutions": "false",
        "maxMissingFoods": "0",
        "limit": "2",
    }
    assert [(r.method, r.url.path) for r in calls[2:]] == [
        ("POST", "/api/parser/ingredient"),
        ("POST", "/api/parser/ingredients"),
    ]
    assert json.loads(calls[2].content) == {"parser": "brute", "ingredient": "1 tsp Salt"}
    assert json.loads(calls[3].content) == {"parser": "nlp", "ingredients": ["Salt", "Pepper"]}


@pytest.mark.parametrize("kind", ["ingredient", "duration", "food"])
async def test_guarded_writes_preserve_rows_and_verify(kind):
    from mealie_mcp_server.services import recipe_advanced as service

    ingredient = {
        "referenceId": REF,
        "food": {"id": FOOD, "name": "Salt"},
        "unit": None,
        "note": "Keep",
        "future": False,
        "substitutions": [],
    }
    step = {
        "id": FOOD,
        "text": "Cook",
        "durationSeconds": 10,
        "ingredientReferences": [{"referenceId": REF}],
        "noteReferences": [],
        "future": {"keep": True},
    }
    original = {
        "slug": "soup",
        "updatedAt": "snapshot",
        "recipeIngredient": [ingredient],
        "recipeInstructions": [step],
        "other": 0,
    }
    original_food = {
        "id": FOOD,
        "name": "Salt",
        "substitutions": [],
        "aliases": [],
        "extras": {"keep": True},
        "future": False,
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            if request.url.path == f"/api/foods/{SUB}":
                return httpx.Response(200, json={"id": SUB, "name": "Pepper"})
            return httpx.Response(200, json=original_food if kind == "food" else original)
        body = json.loads(request.content)
        writes.append((request.method, request.url.path, body))
        result = deepcopy({**(original_food if kind == "food" else original), **body})
        if kind == "duration":
            result["recipeInstructions"][0]["id"] = SUB
        return httpx.Response(200, json=result)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        if kind == "ingredient":
            result = await service.update_recipe_ingredient_substitutions(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [
                        {
                            "referenceId": REF,
                            "substitutions": [{"substituteFoodId": SUB, "note": None}],
                        }
                    ],
                },
            )
            assert writes == [
                (
                    "PATCH",
                    "/api/recipes/soup",
                    {
                        "recipeIngredient": [
                            {
                                **ingredient,
                                "substitutions": [{"substituteFoodId": SUB, "note": None}],
                            }
                        ]
                    },
                )
            ]
        elif kind == "duration":
            result = await service.update_recipe_instruction_durations(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [{"index": 0, "durationSeconds": None}],
                },
            )
            assert writes[0][0:2] == ("PATCH", "/api/recipes/soup")
            assert writes[0][2] == {
                "recipeInstructions": [
                    {k: v for k, v in {**step, "durationSeconds": None}.items() if k != "id"}
                ]
            }
        else:
            result = await service.update_food_substitutions(
                client, FOOD, {"substitutions": [{"substituteFoodId": SUB}]}
            )
            assert writes == [
                (
                    "PUT",
                    f"/api/foods/{FOOD}",
                    {**original_food, "substitutions": [{"substituteFoodId": SUB}]},
                )
            ]
    assert result["other"] == 0 if kind != "food" else result["extras"] == {"keep": True}


@pytest.mark.parametrize("kind", ["ingredient", "duration"])
async def test_stale_snapshot_prevents_writes(kind):
    from mealie_mcp_server.services import recipe_advanced as service

    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json={"updatedAt": "new"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        method = (
            service.update_recipe_ingredient_substitutions
            if kind == "ingredient"
            else service.update_recipe_instruction_durations
        )
        with pytest.raises(ValueError, match="Stale snapshot"):
            await method(client, "soup", {"expectedUpdatedAt": "old", "updates": []})
    assert calls == ["GET"]


@pytest.mark.parametrize("value", [0, -1, 2147483648, True, 1.5, "1"])
def test_duration_bounds_and_types_reject_before_http(value):
    from mealie_mcp_server.models.inputs.recipe_advanced import (
        UpdateRecipeInstructionDurationsInput,
    )

    with pytest.raises(ValidationError):
        UpdateRecipeInstructionDurationsInput.model_validate(
            {
                "slug": "soup",
                "expectedUpdatedAt": "snapshot",
                "updates": [{"index": 0, "durationSeconds": value}],
            }
        )


@pytest.mark.parametrize("kind", ["ingredient", "food", "duration"])
@pytest.mark.parametrize("failure", ["mismatch", "server_error"])
async def test_failed_write_is_reported_without_replay(kind, failure):
    from mealie_mcp_server.mealie.errors import MealieApiError
    from mealie_mcp_server.services import recipe_advanced as service

    original = {
        "updatedAt": "snapshot",
        "recipeIngredient": [{"referenceId": REF, "food": {"id": FOOD}, "substitutions": []}],
        "recipeInstructions": [{"text": "Cook", "durationSeconds": None}],
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            if request.url.path.startswith("/api/foods/"):
                return httpx.Response(
                    200,
                    json={
                        "id": SUB if request.url.path.endswith(SUB) else FOOD,
                        "name": "Food",
                        "substitutions": [],
                    },
                )
            return httpx.Response(200, json=original)
        writes.append(request.method)
        if failure == "server_error":
            return httpx.Response(503, json={"detail": "private"})
        return httpx.Response(
            200, json={"id": FOOD, "substitutions": []} if kind == "food" else original
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "server_error" else ValueError) as caught:
            if kind == "ingredient":
                await service.update_recipe_ingredient_substitutions(
                    client,
                    "soup",
                    {
                        "expectedUpdatedAt": "snapshot",
                        "updates": [
                            {"referenceId": REF, "substitutions": [{"substituteFoodId": SUB}]}
                        ],
                    },
                )
            elif kind == "food":
                await service.update_food_substitutions(
                    client, FOOD, {"substitutions": [{"substituteFoodId": SUB}]}
                )
            else:
                await service.update_recipe_instruction_durations(
                    client,
                    "soup",
                    {
                        "expectedUpdatedAt": "snapshot",
                        "updates": [{"index": 0, "durationSeconds": 1}],
                    },
                )
    assert len(writes) == 1 and "private" not in str(caught.value)


@pytest.mark.parametrize(
    "substitutions",
    [
        [{"substituteFoodId": FOOD}],
        [{"substituteFoodId": SUB}, {"substituteFoodId": SUB}],
        [{"substituteFoodId": SUB}, {"note": None}],
    ],
)
async def test_invalid_substitution_identities_never_write(substitutions):
    from mealie_mcp_server.services import recipe_advanced as service

    methods = []

    def handle(request):
        methods.append(request.method)
        identifier = SUB if request.url.path.endswith(SUB) else FOOD
        return httpx.Response(200, json={"id": identifier, "name": "Food", "substitutions": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await service.update_food_substitutions(client, FOOD, {"substitutions": substitutions})
    assert methods and set(methods) == {"GET"}


@pytest.mark.parametrize("target_status,returned_id", [(404, None), (200, FOOD)])
async def test_nonexistent_or_wrong_food_target_never_writes(target_status, returned_id):
    from mealie_mcp_server.mealie.errors import MealieApiError
    from mealie_mcp_server.services import recipe_advanced as service

    methods = []

    def handle(request):
        methods.append(request.method)
        if request.url.path.endswith(SUB):
            return httpx.Response(target_status, json={"id": returned_id})
        return httpx.Response(200, json={"id": FOOD, "substitutions": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if target_status == 404 else ValueError):
            await service.update_food_substitutions(
                client, FOOD, {"substitutions": [{"substituteFoodId": SUB}]}
            )
    assert methods == ["GET", "GET"]


@pytest.mark.parametrize("kind", ["ingredient", "food", "duration"])
async def test_noop_clearing_does_not_write(kind):
    from mealie_mcp_server.services import recipe_advanced as service

    methods = []
    original = {
        "id": FOOD,
        "substitutions": [],
        "updatedAt": "snapshot",
        "recipeIngredient": [{"referenceId": REF, "food": None, "substitutions": []}],
        "recipeInstructions": [{"id": FOOD, "text": "Cook", "durationSeconds": None}],
    }

    def handle(request):
        methods.append(request.method)
        return httpx.Response(200, json=original)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        if kind == "ingredient":
            result = await service.update_recipe_ingredient_substitutions(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [{"referenceId": REF, "substitutions": []}],
                },
            )
        elif kind == "food":
            result = await service.update_food_substitutions(client, FOOD, {"substitutions": []})
        else:
            result = await service.update_recipe_instruction_durations(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [{"index": 0, "durationSeconds": None}],
                },
            )
    assert result == original and methods == ["GET"]


@pytest.mark.parametrize(
    "reference,duplicate_row,duplicate_update",
    [(SUB, False, False), (REF, True, False), (REF, False, True)],
)
async def test_invalid_or_ambiguous_ingredient_reference_never_writes(
    reference, duplicate_row, duplicate_update
):
    from mealie_mcp_server.services import recipe_advanced as service

    row = {"referenceId": REF, "food": {"id": FOOD}, "substitutions": []}
    methods = []

    def handle(request):
        methods.append(request.method)
        return httpx.Response(
            200,
            json={
                "updatedAt": "snapshot",
                "recipeIngredient": [row, row] if duplicate_row else [row],
            },
        )

    update = {"referenceId": reference, "substitutions": []}
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="referenceId"):
            await service.update_recipe_ingredient_substitutions(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [update, update] if duplicate_update else [update],
                },
            )
    assert methods == ["GET"]


@pytest.mark.parametrize(
    "updates",
    [
        [{"index": 1, "durationSeconds": 2}],
        [{"index": 0, "durationSeconds": 2}, {"index": 0, "durationSeconds": 3}],
        [{"index": 0}],
        [{"index": 0, "durationSeconds": True}],
    ],
)
async def test_invalid_duration_requests_never_write(updates):
    from mealie_mcp_server.services import recipe_advanced as service

    methods = []

    def handle(request):
        methods.append(request.method)
        return httpx.Response(
            200, json={"updatedAt": "snapshot", "recipeInstructions": [{"text": "Cook"}]}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await service.update_recipe_instruction_durations(
                client, "soup", {"expectedUpdatedAt": "snapshot", "updates": updates}
            )
    assert methods == ["GET"]


@pytest.mark.parametrize("food", [{"id": "not-a-uuid"}, {"name": "Unresolved"}, None])
async def test_recipe_substitutions_require_existing_canonical_food_identity(food):
    from mealie_mcp_server.services import recipe_advanced as service

    methods = []
    original = {
        "updatedAt": "snapshot",
        "recipeIngredient": [{"referenceId": REF, "food": food, "substitutions": []}],
    }

    def handle(request):
        methods.append(request.method)
        if request.url.path.endswith(SUB):
            return httpx.Response(200, json={"id": SUB, "name": "Pepper"})
        return httpx.Response(
            200, json={**original, **(json.loads(request.content) if request.content else {})}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="canonical food"):
            await service.update_recipe_ingredient_substitutions(
                client,
                "soup",
                {
                    "expectedUpdatedAt": "snapshot",
                    "updates": [{"referenceId": REF, "substitutions": [{"substituteFoodId": SUB}]}],
                },
            )
    assert methods == ["GET"]


def test_d14_overlay_is_allowlisted_and_additive_only():
    from pathlib import Path

    from tests.support.mealie330_compatibility import (
        SCENARIOS,
        apply_request_overlay,
        apply_result_overlay,
    )

    fixtures = Path(__file__).parents[1] / "fixtures" / "compatibility"
    scenarios = json.loads((fixtures / "scenarios.json").read_text())
    changed = set()
    for name, scenario in scenarios.items():
        original = deepcopy(scenario["requests"])
        patched = apply_request_overlay(name, original)
        assert scenario["requests"] == original
        if patched != original:
            changed.add(name)
            restored = deepcopy(patched)
            for old, new in zip(original, restored, strict=True):
                for key in ("body", "response"):
                    if not isinstance(old.get(key), dict) or not isinstance(new.get(key), dict):
                        continue
                    old_rows = old[key].get("recipeIngredient", [])
                    new_rows = new[key].get("recipeIngredient", [])
                    for old_row, new_row in zip(old_rows, new_rows, strict=True):
                        if "providerExtra" not in old_row and "providerExtra" in new_row:
                            assert old_row.get("referenceId") == REF
                            assert new_row.pop("providerExtra") == {"keep": True}
            assert restored == original
    assert (
        changed
        == SCENARIOS
        == {
            "update_recipe_ingredients.basic",
            "update_recipe_ingredients_batch.basic",
            "update_recipe_ingredients.rollback",
            "update_recipe_ingredients.canonical_alias",
        }
    )
    sample = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"recipeIngredient": [{"referenceId": REF, "note": None}]}),
            }
        ]
    }
    assert apply_result_overlay("unlisted", sample) == sample
    patched_result = apply_result_overlay("update_recipe_ingredients.basic", sample)
    parsed = json.loads(patched_result["content"][0]["text"])
    assert parsed == {
        "recipeIngredient": [{"referenceId": REF, "note": None, "providerExtra": {"keep": True}}]
    }
    assert json.loads(sample["content"][0]["text"]) == {
        "recipeIngredient": [{"referenceId": REF, "note": None}]
    }
    with pytest.raises(AssertionError):
        apply_request_overlay(
            "update_recipe_ingredients.basic",
            [
                {
                    "method": "PATCH",
                    "body": {
                        "recipeIngredient": [{"referenceId": REF, "providerExtra": {"keep": False}}]
                    },
                }
            ],
        )


async def test_legacy_replacement_preserves_only_fields_outside_old_input_contract():
    original = {
        "recipeIngredient": [
            {
                "referenceId": REF,
                "food": None,
                "unit": None,
                "note": "omit me",
                "title": "omit me too",
                "quantity": 3,
                "referencedRecipe": {"id": FOOD},
                "substitutions": [{"substituteFoodId": SUB}],
                "providerExtra": {"keep": True},
            }
        ]
    }
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=original)
        payload = json.loads(request.content)
        writes.append(payload)
        return httpx.Response(200, json={**original, **payload})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await update_recipe_ingredients(client, "soup", {"ingredients": [{"referenceId": REF}]})
    assert writes == [
        {
            "recipeIngredient": [
                {
                    "referenceId": REF,
                    "food": None,
                    "unit": None,
                    "substitutions": [{"substituteFoodId": SUB}],
                    "providerExtra": {"keep": True},
                }
            ]
        }
    ]


@pytest.mark.parametrize("kind", ["ingredient", "food"])
@pytest.mark.parametrize("id_note", [None, "  "])
async def test_mixed_text_and_canonical_substitutions_preserve_presence_order_and_clear(
    kind, id_note
):
    from mealie_mcp_server.models.common import provided_fields
    from mealie_mcp_server.models.inputs.recipe_advanced import (
        UpdateFoodSubstitutionsInput,
        UpdateRecipeIngredientSubstitutionsInput,
    )
    from mealie_mcp_server.services import recipe_advanced as service

    mixed = [
        {"substituteFoodId": SUB, "note": id_note},
        {"note": "Use broth instead"},
        {"substituteFoodId": None, "note": "  Use water  "},
    ]
    row = {"referenceId": REF, "food": {"id": FOOD}, "substitutions": [], "providerExtra": False}
    state = {"id": FOOD, "updatedAt": "snapshot", "substitutions": [], "recipeIngredient": [row]}
    calls = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        if request.url.path.endswith(SUB):
            return httpx.Response(200, json={"id": SUB, "name": "Alternative"})
        if request.method != "GET":
            state.update(deepcopy(body))
            substitutions = (
                state["recipeIngredient"][0]["substitutions"]
                if kind == "ingredient"
                else state["substitutions"]
            )
            for item in substitutions:
                item.setdefault("substituteFoodId", None)
                item.setdefault("note", None)
                if isinstance(item["note"], str):
                    item["note"] = item["note"].strip() or None
                item["substituteFood"] = {"id": SUB} if item["substituteFoodId"] else None
        return httpx.Response(200, json=state)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        if kind == "ingredient":
            request = UpdateRecipeIngredientSubstitutionsInput.model_validate(
                {
                    "slug": "soup",
                    "expectedUpdatedAt": "snapshot",
                    "updates": [{"referenceId": REF, "substitutions": mixed}],
                }
            )
            changes = provided_fields(request)
            changes.pop("slug")
            await service.update_recipe_ingredient_substitutions(client, "soup", changes)
            written = calls[-1][2]["recipeIngredient"][0]["substitutions"]
            changes["updates"][0]["substitutions"] = []
            await service.update_recipe_ingredient_substitutions(client, "soup", changes)
            assert state["recipeIngredient"][0]["providerExtra"] is False
            assert state["recipeIngredient"][0]["referenceId"] == REF
            assert state["recipeIngredient"][0]["substitutions"] == []
        else:
            request = UpdateFoodSubstitutionsInput.model_validate(
                {"foodId": FOOD, "substitutions": mixed}
            )
            changes = provided_fields(request)
            changes.pop("foodId")
            await service.update_food_substitutions(client, FOOD, changes)
            written = calls[-1][2]["substitutions"]
            await service.update_food_substitutions(client, FOOD, {"substitutions": []})
            assert state["substitutions"] == []
    assert written == mixed
    assert [path for method, path, body in calls if method == "GET" and path.endswith(SUB)] == [
        f"/api/foods/{SUB}"
    ]
    assert [method for method, path, body in calls if method != "GET"] == (
        ["PATCH", "PATCH"] if kind == "ingredient" else ["PUT", "PUT"]
    )


@pytest.mark.parametrize(
    "item",
    [
        {},
        {"note": None},
        {"note": ""},
        {"note": "  \t "},
        {"substituteFoodId": None},
        {"substituteFoodId": None, "note": " "},
    ],
)
def test_text_only_substitution_requires_nonblank_note(item):
    from mealie_mcp_server.models.inputs.recipe_advanced import FoodSubstitutionInput

    with pytest.raises(ValidationError):
        FoodSubstitutionInput.model_validate(item)


async def test_text_only_substitutions_on_unresolved_ingredient_do_not_create_foods():
    from mealie_mcp_server.services import recipe_advanced as service

    original = {
        "updatedAt": "snapshot",
        "recipeIngredient": [
            {"referenceId": REF, "food": None, "note": "Original", "substitutions": []}
        ],
    }
    calls = []

    def handle(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        return httpx.Response(200, json={**original, **(body or {})})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await service.update_recipe_ingredient_substitutions(
            client,
            "soup",
            {
                "expectedUpdatedAt": "snapshot",
                "updates": [{"referenceId": REF, "substitutions": [{"note": "Use stock"}]}],
            },
        )
    assert [(method, path) for method, path, body in calls] == [
        ("GET", "/api/recipes/soup"),
        ("PATCH", "/api/recipes/soup"),
    ]
    assert result["recipeIngredient"] == [
        {
            "referenceId": REF,
            "food": None,
            "note": "Original",
            "substitutions": [{"note": "Use stock"}],
        }
    ]


async def test_text_only_substitution_verification_detects_lost_text_without_replay():
    from mealie_mcp_server.services import recipe_advanced as service

    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"id": FOOD, "substitutions": []})
        writes.append(json.loads(request.content))
        return httpx.Response(
            200, json={"id": FOOD, "substitutions": [{"substituteFoodId": None, "note": None}]}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="verification failed"):
            await service.update_food_substitutions(
                client, FOOD, {"substitutions": [{"note": "Keep this alternative"}]}
            )
    assert writes == [{"id": FOOD, "substitutions": [{"note": "Keep this alternative"}]}]
