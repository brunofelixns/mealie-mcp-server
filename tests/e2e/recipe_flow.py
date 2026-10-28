"""Recipe queries and verified mutations against persistent Mealie state."""

import base64
import uuid

from tests.e2e.scenarios import contains
from tests.e2e.stack import png


def batch_ok(value):
    rows = value if isinstance(value, list) else value.get("results", [])
    return bool(rows) and all(row.get("success") is True for row in rows)


async def exercise(s):
    slugs = []
    for label in ("Soup", "Side"):
        name = s.prefix + " " + label
        created = await s.call(
            "create_recipe",
            {"name": name, "ingredients": ["2 pinches salt"], "instructions": ["Mix ingredients."]},
        )
        assert isinstance(created, dict), (
            "create_recipe with ingredient/instruction input returns the recipe"
        )
        slug = created["slug"]
        recipe = await s.get("/api/recipes/" + slug)
        slugs.append(slug)
        s.remember("/api/recipes/" + slug)
        s.verify(
            "create_recipe",
            recipe["name"] == name and bool(recipe["recipeIngredient"]),
            "recipe_and_ingredient_persisted",
        )
    s.data["slugs"] = slugs
    main, side = slugs
    food, unit = s.data["food"], s.data["unit"]
    reference = str(uuid.uuid4())
    ingredient = {
        "referenceId": reference,
        "foodId": food["id"],
        "foodName": food["name"],
        "unitId": unit["id"],
        "unitName": unit["name"],
        "quantity": 2,
        "note": "Original E2E ingredient line",
    }
    await s.call(
        "patch_recipe",
        {"slug": main, "description": s.prefix + " description", "recipeServings": 2},
    )
    stored = await s.get("/api/recipes/" + main)
    s.verify(
        "patch_recipe",
        stored["description"] == s.prefix + " description" and stored["recipeServings"] == 2,
        "scalar_fields_persisted",
    )
    await s.call("update_recipe_ingredients", {"slug": main, "ingredients": [ingredient]})
    stored = await s.get("/api/recipes/" + main)
    s.verify(
        "update_recipe_ingredients",
        stored["recipeIngredient"][0]["referenceId"] == reference
        and stored["recipeIngredient"][0]["food"]["id"] == food["id"],
        "structured_reference_and_food_persisted",
    )
    result = await s.call(
        "update_recipe_ingredients_batch",
        {
            "updates": [
                {"slug": main, "updateIngredients": [{"referenceId": reference, "quantity": 3}]},
                {"slug": side, "ingredients": [{**ingredient, "referenceId": str(uuid.uuid4())}]},
            ]
        },
    )
    s.verify(
        "update_recipe_ingredients_batch",
        batch_ok(result)
        and (await s.get("/api/recipes/" + main))["recipeIngredient"][0]["quantity"] == 3,
        "batch_success_and_quantity_persisted",
    )
    stored = await s.get("/api/recipes/" + main)
    await s.call(
        "update_recipe_instructions",
        {
            "slug": main,
            "expectedUpdatedAt": stored["updatedAt"],
            "instructions": [
                {"text": "Stir the test soup.", "ingredientReferenceIds": [reference]}
            ],
        },
    )
    stored = await s.get("/api/recipes/" + main)
    s.verify(
        "update_recipe_instructions",
        stored["recipeInstructions"][0]["text"] == "Stir the test soup."
        and contains(stored["recipeInstructions"], reference),
        "instruction_and_ingredient_link_persisted",
    )
    updates = []
    for slug in slugs:
        recipe = await s.get("/api/recipes/" + slug)
        updates.append(
            {
                "slug": slug,
                "expectedUpdatedAt": recipe["updatedAt"],
                "addInstructions": [{"text": "Serve the E2E dish."}],
            }
        )
    result = await s.call("update_recipe_instructions_batch", {"updates": updates})
    s.verify("update_recipe_instructions_batch", batch_ok(result), "batch_entries_succeeded")
    for slug in slugs:
        s.verify(
            "update_recipe_instructions_batch",
            contains(
                (await s.get("/api/recipes/" + slug))["recipeInstructions"], "Serve the E2E dish."
            ),
            "appended_instruction_persisted",
        )

    category, tag, equipment = s.data["category"], s.data["tag"], s.data["tool"]
    await s.call(
        "update_recipe_taxonomy",
        {"slug": main, "categories": [category["id"]], "tags": [tag["id"]], "mode": "replace"},
    )
    stored = await s.get("/api/recipes/" + main)
    s.verify(
        "update_recipe_taxonomy",
        contains(stored["recipeCategory"], category["id"]) and contains(stored["tags"], tag["id"]),
        "taxonomy_persisted",
    )
    result = await s.call(
        "update_recipe_taxonomy_batch",
        {"updates": [{"slug": side, "categories": [category["name"]], "tags": [tag["name"]]}]},
    )
    stored = await s.get("/api/recipes/" + side)
    s.verify(
        "update_recipe_taxonomy_batch",
        batch_ok(result)
        and contains(stored["recipeCategory"], category["id"])
        and contains(stored["tags"], tag["id"]),
        "batch_taxonomy_persisted",
    )
    await s.call("update_recipe_tools", {"slug": main, "tools": [equipment["id"]]})
    s.verify(
        "update_recipe_tools",
        contains((await s.get("/api/recipes/" + main))["tools"], equipment["id"]),
        "equipment_persisted",
    )
    result = await s.call(
        "update_recipe_tools_batch", {"updates": [{"slug": side, "tools": [equipment["name"]]}]}
    )
    s.verify(
        "update_recipe_tools_batch",
        batch_ok(result)
        and contains((await s.get("/api/recipes/" + side))["tools"], equipment["id"]),
        "batch_equipment_persisted",
    )

    recipe = await s.get("/api/recipes/" + main)
    s.data["recipe"] = recipe
    result = await s.call(
        "get_recipes",
        {
            "search": recipe["name"],
            "page": 1,
            "perPage": 10,
            "categories": [category["id"]],
            "tags": [tag["id"]],
        },
    )
    s.verify(
        "get_recipes", contains(result, recipe["id"]), "search_and_taxonomy_filter_find_recipe"
    )
    for name in ("get_recipe_detailed", "get_recipe_concise"):
        result = await s.call(name, {"slug": main})
        s.verify(name, contains(result, recipe["name"]), "recipe_content_returned")
    for name in ("get_recipes_batch", "get_recipes_detailed_batch"):
        result = await s.call(name, {"slugs": slugs})
        s.verify(
            name,
            set(result) == set(slugs)
            and all(
                result[slug]["slug"] == slug and result[slug]["name"].startswith(s.prefix)
                for slug in slugs
            ),
            "both_requested_recipes_returned",
        )
    for name, arguments in (
        ("get_recipes_for_classification", {"taxonomyState": "any", "limit": 50}),
        ("get_recipes_for_ingredient_parsing", {"state": "any", "limit": 50}),
        ("get_recipes_for_data_enrichment", {"filters": {"image": False}, "limit": 50}),
    ):
        result = await s.call(name, arguments)
        s.verify(name, contains(result, main), "real_recipe_present_in_queue")
    result = await s.call(
        "find_recipes_for_ingredients", {"ingredients": [food["name"]], "limit": 10}
    )
    s.verify(
        "find_recipes_for_ingredients", contains(result, main), "food_lookup_finds_linked_recipe"
    )

    result = await s.call("set_recipe_rating", {"slug": main, "rating": 4.5, "isFavorite": True})
    rating = await s.get("/api/users/self/ratings/" + recipe["id"])
    s.verify(
        "set_recipe_rating",
        rating["rating"] == 4.5
        and rating["isFavorite"] is True
        and result["userRating"]["rating"] == 4.5,
        "personal_rating_and_favorite_persisted",
    )
    stamp = "2026-10-27T12:00:00Z"
    await s.call("mark_recipe_last_made", {"slug": main, "timestamp": stamp})
    household = await s.get("/api/households/self/recipes/" + main)
    s.verify(
        "mark_recipe_last_made",
        household["lastMade"].startswith("2026-10-27"),
        "household_timestamp_persisted",
    )
    await s.call(
        "set_recipe_image",
        {"slug": main, "imageBase64": base64.b64encode(png(b"\0\0\xff")).decode()},
    )
    media_path = "/api/media/recipes/" + recipe["id"] + "/images/original.webp"
    original_media = await s.observer.get(media_path)
    original_media.raise_for_status()
    s.verify(
        "set_recipe_image",
        bool((await s.get("/api/recipes/" + main))["image"]),
        "binary_image_persisted",
    )
    image_result = await s.call(
        "set_recipe_image_from_url", {"slug": main, "imageUrl": "http://assets:8080/image.png"}
    )
    before = (await s.get("/api/recipes/" + main))["image"]
    media = await s.observer.get(media_path)
    s.verify(
        "set_recipe_image_from_url",
        image_result["image"] == before
        and media.status_code == 200
        and media.headers.get("content-type", "").startswith("image/")
        and media.content.startswith(b"RIFF")
        and media.content != original_media.content,
        "local_url_image_persisted_and_readable",
    )
    name = "set_recipe_image_from_file"
    s.report["lastTool"] = name
    result = await s.client.call_tool(
        name,
        {
            "slug": main,
            "file": {"download_url": "http://assets:8080/image.png", "file_id": "e2e-private-file"},
        },
    )
    assert result.is_error and "private or non-public" in result.content[0].text
    assert (await s.get("/api/recipes/" + main))["image"] == before
    s.records[name] = {
        "tool": name,
        "outcome": "security_rejection",
        "checks": ["private_address_refused", "image_unchanged"],
    }
    s.report["calls"] += 1
    duplicate = await s.call("duplicate_recipe", {"slug": main, "name": s.prefix + " Duplicate"})
    duplicate_slug = duplicate if isinstance(duplicate, str) else duplicate["slug"]
    duplicate_recipe = await s.get("/api/recipes/" + duplicate_slug)
    s.verify(
        "duplicate_recipe",
        duplicate_recipe["id"] != recipe["id"]
        and duplicate_recipe["name"] == s.prefix + " Duplicate",
        "independent_duplicate_persisted",
    )
    slugs.append(duplicate_slug)
    s.remember("/api/recipes/" + duplicate_slug)


async def merge_and_cleanup(s):
    source, target = s.data["food"], s.data["targetFood"]
    result = await s.call("merge_foods", {"fromFoodId": source["id"], "toFoodId": target["id"]})
    recipe = await s.get("/api/recipes/" + s.data["slugs"][0])
    persisted_target = await s.get("/api/foods/" + target["id"])
    s.verify(
        "merge_foods",
        await s.absent("/api/foods/" + source["id"])
        and result["id"] == target["id"]
        and persisted_target["id"] == target["id"]
        and recipe["recipeIngredient"][0]["food"]["id"] == target["id"],
        "source_removed_and_recipe_reference_rewritten",
    )
    for slug in reversed(s.data["slugs"]):
        await s.call("delete_recipe", {"slug": slug})
        s.verify("delete_recipe", await s.absent("/api/recipes/" + slug), "deleted_recipe_absent")
