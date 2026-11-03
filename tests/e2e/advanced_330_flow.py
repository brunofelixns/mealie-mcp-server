"""Verify native search, parser, substitutions and timers on disposable Mealie 3.30."""

from tests.e2e.scenarios import contains


def _steps(recipe):
    return [
        {key: value for key, value in row.items() if key != "id"}
        for row in recipe["recipeInstructions"]
    ]


def _legacy_ingredient(row):
    result = {
        key: row[key]
        for key in ("quantity", "note", "display", "originalText", "title", "referenceId")
        if key in row
    }
    for kind in ("food", "unit"):
        entity = row.get(kind)
        if entity is not None:
            result[kind + "Id"], result[kind + "Name"] = entity["id"], entity["name"]
    if row.get("referencedRecipe"):
        result["referencedRecipeId"] = row["referencedRecipe"]["id"]
    return result


async def exercise(s):
    slug = s.data["slugs"][0]
    path = "/api/recipes/" + slug
    food, substitute = s.data["food"], s.data["targetFood"]
    recipe = await s.get(path)
    result = await s.call(
        "search_recipes",
        {
            "search": recipe["name"],
            "foods": [food["id"]],
            "requireAllFoods": True,
            "orderBy": "name",
            "orderDirection": "asc",
            "page": 1,
            "perPage": 10,
        },
    )
    s.verify(
        "search_recipes",
        contains(result["items"], recipe["id"]),
        "native_search_and_food_filter_find_persisted_recipe",
    )

    original_food = await s.get("/api/foods/" + food["id"])
    original_food_substitutions = original_food.get("substitutions", [])
    await s.call(
        "update_food_substitutions",
        {
            "foodId": food["id"],
            "substitutions": [
                {"substituteFoodId": substitute["id"], "note": "E2E alternative"},
                {"note": "  E2E text-only alternative  "},
            ],
        },
    )
    stored_food = await s.get("/api/foods/" + food["id"])
    s.verify(
        "update_food_substitutions",
        stored_food["substitutions"][0]["substituteFoodId"] == substitute["id"]
        and stored_food["substitutions"][0]["note"] == "E2E alternative"
        and len(stored_food["substitutions"]) == 2
        and stored_food["substitutions"][1]["substituteFoodId"] is None
        and stored_food["substitutions"][1]["note"] == "E2E text-only alternative"
        and stored_food["aliases"] == original_food["aliases"]
        and stored_food["extras"] == original_food["extras"],
        "global_mixed_canonical_and_text_substitutions_preserve_order_and_unrelated_fields",
    )
    await s.call("update_food", {"foodId": food["id"], "description": s.prefix + " preserved"})
    s.verify(
        "update_food",
        (await s.get("/api/foods/" + food["id"]))["substitutions"] == stored_food["substitutions"],
        "legacy_food_update_preserves_native_substitutions",
    )

    recipe = await s.get(path)
    selected = next(
        row for row in recipe["recipeIngredient"] if (row.get("food") or {}).get("id") == food["id"]
    )
    reference = selected["referenceId"]
    await s.call(
        "update_recipe_ingredient_substitutions",
        {
            "slug": slug,
            "expectedUpdatedAt": recipe["updatedAt"],
            "updates": [
                {
                    "referenceId": reference,
                    "substitutions": [
                        {"substituteFoodId": substitute["id"], "note": "Recipe alternative"},
                        {"substituteFoodId": None, "note": "  Recipe text-only alternative  "},
                    ],
                }
            ],
        },
    )
    stored = await s.get(path)
    selected = next(row for row in stored["recipeIngredient"] if row["referenceId"] == reference)
    s.verify(
        "update_recipe_ingredient_substitutions",
        selected["substitutions"][0]["substituteFoodId"] == substitute["id"]
        and selected["substitutions"][0]["note"] == "Recipe alternative"
        and len(selected["substitutions"]) == 2
        and selected["substitutions"][1]["substituteFoodId"] is None
        and selected["substitutions"][1]["note"] == "Recipe text-only alternative"
        and [row["referenceId"] for row in stored["recipeIngredient"]]
        == [row["referenceId"] for row in recipe["recipeIngredient"]]
        and _steps(stored) == _steps(recipe),
        "mixed_row_substitutions_persist_without_reordering_or_changing_step_links",
    )
    result = await s.call(
        "get_recipe_suggestions",
        {
            "foods": [substitute["id"]],
            "tools": [s.data["tool"]["id"]],
            "maxMissingFoods": 0,
            "maxMissingTools": 0,
            "includeFoodsOnHand": False,
            "includeToolsOnHand": False,
            "includeSubstitutions": True,
            "limit": 100,
        },
    )
    s.verify(
        "get_recipe_suggestions",
        contains(result["items"], recipe["id"]),
        "native_suggestions_use_explicit_canonical_food_substitutions",
    )

    unit = s.data["unit"]
    await s.call(
        "update_recipe_ingredients",
        {
            "slug": slug,
            "updateIngredients": [
                {
                    "referenceId": reference,
                    "note": "Legacy edit retains substitutions",
                    "unitId": unit["id"],
                    "unitName": unit["name"],
                }
            ],
        },
    )
    after_delta = await s.get(path)
    changed = next(
        row for row in after_delta["recipeIngredient"] if row["referenceId"] == reference
    )
    s.verify(
        "update_recipe_ingredients",
        changed["substitutions"] == selected["substitutions"]
        and changed["food"]["substitutions"] == selected["food"]["substitutions"]
        and _steps(after_delta) == _steps(stored),
        "legacy_note_and_unit_delta_preserves_recipe_and_food_substitutions",
    )
    await s.call(
        "update_recipe_ingredients",
        {
            "slug": slug,
            "ingredients": [_legacy_ingredient(row) for row in after_delta["recipeIngredient"]],
        },
    )
    after_replacement = await s.get(path)
    s.verify(
        "update_recipe_ingredients",
        after_replacement["recipeIngredient"] == after_delta["recipeIngredient"]
        and _steps(after_replacement) == _steps(after_delta),
        "legacy_replacement_of_continuing_rows_preserves_substitutions_and_references",
    )

    before_timers = await s.get(path)
    expected_steps = _steps(before_timers)
    expected_steps[0]["durationSeconds"] = 60
    await s.call(
        "update_recipe_instruction_durations",
        {
            "slug": slug,
            "expectedUpdatedAt": before_timers["updatedAt"],
            "updates": [{"index": 0, "durationSeconds": 60}],
        },
    )
    timed = await s.get(path)
    s.verify(
        "update_recipe_instruction_durations",
        _steps(timed) == expected_steps
        and timed["recipeIngredient"] == before_timers["recipeIngredient"],
        "timer_persists_with_step_content_and_references_unchanged",
    )
    expected_steps[0]["durationSeconds"] = None
    await s.call(
        "update_recipe_instruction_durations",
        {
            "slug": slug,
            "expectedUpdatedAt": timed["updatedAt"],
            "updates": [{"index": 0, "durationSeconds": None}],
        },
    )
    cleared = await s.get(path)
    s.verify(
        "update_recipe_instruction_durations",
        _steps(cleared) == expected_steps,
        "explicit_null_clears_timer_without_changing_other_steps",
    )

    await _parser(s, food, unit, slug)
    current = await s.get(path)
    await s.call(
        "update_recipe_ingredient_substitutions",
        {
            "slug": slug,
            "expectedUpdatedAt": current["updatedAt"],
            "updates": [{"referenceId": reference, "substitutions": []}],
        },
    )
    cleared = await s.get(path)
    s.verify(
        "update_recipe_ingredient_substitutions",
        next(row for row in cleared["recipeIngredient"] if row["referenceId"] == reference)[
            "substitutions"
        ]
        == [],
        "empty_list_explicitly_clears_recipe_substitutions",
    )
    await s.call(
        "update_food_substitutions",
        {
            "foodId": food["id"],
            "substitutions": [
                {key: row[key] for key in ("substituteFoodId", "note") if key in row}
                for row in original_food_substitutions
            ],
        },
    )
    s.verify(
        "update_food_substitutions",
        (await s.get("/api/foods/" + food["id"]))["substitutions"] == original_food_substitutions,
        "original_food_substitutions_restored_before_merge_cleanup",
    )


async def _parser(s, food, unit, slug):
    before_recipe = await s.get("/api/recipes/" + slug)
    vocabulary = {}
    for kind in ("foods", "units"):
        vocabulary[kind] = {
            row["id"]: row
            for row in (await s.get("/api/" + kind + "?page=1&perPage=1000"))["items"]
        }
    first = "2 " + unit["name"] + " " + food["name"]
    second = "3 " + unit["name"] + " " + food["name"]
    parsed = await s.call("parse_recipe_ingredient", {"parser": "brute", "ingredient": first})
    s.verify(
        "parse_recipe_ingredient",
        isinstance(parsed.get("ingredient"), dict) and parsed.get("input") == first,
        "explicit_native_brute_parser_returns_input_and_structured_preview",
    )
    batch = await s.call(
        "parse_recipe_ingredients", {"parser": "brute", "ingredients": [first, second]}
    )
    s.verify(
        "parse_recipe_ingredients",
        len(batch) == 2
        and [row.get("input") for row in batch] == [first, second]
        and all(isinstance(row.get("ingredient"), dict) for row in batch)
        and (await s.get("/api/recipes/" + slug))["recipeIngredient"]
        == before_recipe["recipeIngredient"],
        "batch_preview_keeps_order_and_never_applies_ingredients_to_recipe",
    )
    for kind in ("foods", "units"):
        rows = (await s.get("/api/" + kind + "?page=1&perPage=1000"))["items"]
        unchanged = {row["id"]: row for row in rows} == vocabulary[kind]
        for row in rows:
            if row["id"] not in vocabulary[kind]:
                path = "/api/" + kind + "/" + row["id"]
                s.remember(path)
                singular = "food" if kind == "foods" else "unit"
                await s.call("delete_" + singular, {singular + "Id": row["id"]})
                s.verify(
                    "delete_" + singular,
                    await s.absent(path),
                    "native_parser_created_vocabulary_cleaned",
                )
        for tool in ("parse_recipe_ingredient", "parse_recipe_ingredients"):
            s.verify(tool, unchanged, "native_parser_does_not_persist_" + kind)
