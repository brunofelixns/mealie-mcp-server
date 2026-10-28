"""Exercise every mealplan tool, including ordered mutations and cleanup."""

from datetime import UTC, datetime

from tests.e2e.recipe_flow import batch_ok
from tests.e2e.scenarios import contains


async def exercise(s):
    today = datetime.now(UTC).date().isoformat()
    recipe_id = s.data["recipe"]["id"]
    first = await s.call(
        "create_mealplan", {"date": today, "recipeId": recipe_id, "entryType": "dinner"}
    )
    path = "/api/households/mealplans/"
    s.remember(path + str(first["id"]))
    s.verify(
        "create_mealplan",
        (await s.get(path + str(first["id"])))["recipeId"] == recipe_id,
        "recipe_plan_persisted",
    )
    bulk = await s.call(
        "create_mealplan_bulk",
        {
            "entries": [
                {"date": today, "title": s.prefix + " Breakfast", "entryType": "breakfast"},
                {"date": today, "recipeId": recipe_id, "entryType": "lunch"},
            ]
        },
    )
    s.verify(
        "create_mealplan_bulk",
        batch_ok(bulk) and bulk["created"] == 2 and bulk["failed"] == 0,
        "both_entries_created",
    )
    ids = sorted(row["entry"]["id"] for row in bulk["results"])
    for identifier in ids:
        s.remember(path + str(identifier))
        s.verify(
            "create_mealplan_bulk",
            (await s.get(path + str(identifier)))["date"] == today,
            "bulk_entry_persisted",
        )
    for name, arguments in (
        ("get_all_mealplans", {"startDate": today, "endDate": today, "page": 1, "perPage": 100}),
        ("get_mealplan_with_recipes", {"startDate": today, "endDate": today}),
        ("get_todays_mealplan", {}),
    ):
        result = await s.call(name, arguments)
        s.verify(
            name,
            contains(result, first["id"]) and contains(result, recipe_id),
            "created_plan_and_recipe_returned",
        )
    removed_id = ids.pop(0)
    patch = await s.call(
        "patch_mealplan",
        {
            "actions": [
                {
                    "action": "append",
                    "date": today,
                    "title": s.prefix + " Extra",
                    "entryType": "dinner",
                },
                {"action": "replace", "id": str(first["id"]), "title": s.prefix + " Updated"},
                {"action": "delete", "id": str(removed_id)},
            ]
        },
    )
    s.verify(
        "patch_mealplan",
        patch["summary"] == {"failed": 0, "deleted": 1, "replaced": 1, "appended": 1}
        and all(row["ok"] is True for row in patch["results"])
        and await s.absent(path + str(removed_id)),
        "all_three_phases_succeeded",
    )
    s.verify(
        "patch_mealplan",
        (await s.get(path + str(first["id"])))["title"] == s.prefix + " Updated",
        "replacement_persisted",
    )
    appended = next(row["entry"]["id"] for row in patch["results"] if row["action"] == "append")
    s.remember(path + str(appended))
    ids += [first["id"], appended]
    result = await s.call(
        "patch_mealplan",
        {"actions": [{"action": "delete", "id": str(identifier)} for identifier in ids]},
    )
    s.verify(
        "patch_mealplan",
        result["summary"]["failed"] == 0
        and result["summary"]["deleted"] == len(ids)
        and all(row["ok"] is True for row in result["results"]),
        "owned_plans_deleted",
    )
