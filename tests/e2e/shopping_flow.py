"""Verify shopping collection responses by reading the persisted list/items."""

from tests.e2e.scenarios import contains


async def exercise(s):
    created = await s.call("create_shopping_list", {"name": s.prefix + " Shopping"})
    identifier = created["id"]
    path = "/api/households/shopping/lists/" + identifier
    s.remember(path)
    s.verify(
        "create_shopping_list",
        (await s.get(path))["name"] == s.prefix + " Shopping",
        "list_persisted",
    )
    result = await s.call("get_shopping_lists", {"page": 1, "perPage": 100})
    s.verify("get_shopping_lists", contains(result, identifier), "created_list_in_page")
    await s.call("update_shopping_list", {"listId": identifier, "name": s.prefix + " Renamed"})
    s.verify(
        "update_shopping_list",
        (await s.get(path))["name"] == s.prefix + " Renamed",
        "name_persisted",
    )
    result = await s.call("get_shopping_list", {"listId": identifier})
    s.verify(
        "get_shopping_list",
        result["id"] == identifier and result["name"] == s.prefix + " Renamed",
        "identity_and_name_returned",
    )
    item_args = {"shoppingListId": identifier, "note": s.prefix + " item", "quantity": 2}
    await s.call("create_shopping_list_item", item_args)
    single = next(
        row for row in (await s.get(path))["listItems"] if row["note"] == item_args["note"]
    )
    item_path = "/api/households/shopping/items/" + single["id"]
    s.remember(item_path)
    s.verify("create_shopping_list_item", single["quantity"] == 2, "item_quantity_persisted")
    await s.call(
        "update_shopping_list_item",
        {"itemId": single["id"], "note": s.prefix + " changed", "quantity": 0, "checked": True},
    )
    stored = await s.get(item_path)
    s.verify(
        "update_shopping_list_item",
        stored["quantity"] == 0
        and stored["checked"] is True
        and stored["note"] == s.prefix + " changed",
        "zero_checked_and_note_persisted",
    )
    result = await s.call(
        "get_shopping_list_items", {"page": 1, "perPage": 100, "search": s.prefix}
    )
    s.verify("get_shopping_list_items", contains(result, single["id"]), "search_finds_created_item")
    await s.call(
        "create_shopping_list_items_bulk",
        {
            "items": [
                {"shoppingListId": identifier, "note": s.prefix + " bulk A", "quantity": 1},
                {"shoppingListId": identifier, "note": s.prefix + " bulk B", "quantity": 3},
            ]
        },
    )
    bulk = [
        row
        for row in (await s.get(path))["listItems"]
        if (row["note"] or "").startswith(s.prefix + " bulk")
    ]
    s.verify(
        "create_shopping_list_items_bulk",
        len(bulk) == 2 and sorted(row["quantity"] for row in bulk) == [1, 3],
        "both_bulk_rows_persisted",
    )
    for row in bulk:
        s.remember("/api/households/shopping/items/" + row["id"])
    await s.call("delete_shopping_list_items_bulk", {"itemIds": [row["id"] for row in bulk]})
    stored = await s.get(path)
    s.verify(
        "delete_shopping_list_items_bulk",
        all(not contains(stored["listItems"], row["id"]) for row in bulk),
        "bulk_rows_absent",
    )
    await s.call("delete_shopping_list_item", {"itemId": single["id"]})
    s.verify("delete_shopping_list_item", await s.absent(item_path), "single_row_absent")
    recipe_id = s.data["recipe"]["id"]
    await s.call(
        "add_recipe_to_shopping_list",
        {"listId": identifier, "recipeId": recipe_id, "recipeIncrementQuantity": 1},
    )
    s.verify(
        "add_recipe_to_shopping_list",
        contains(await s.get(path), recipe_id),
        "recipe_association_persisted",
    )
    await s.call("remove_recipe_from_shopping_list", {"listId": identifier, "recipeId": recipe_id})
    s.verify(
        "remove_recipe_from_shopping_list",
        not contains(await s.get(path), recipe_id),
        "recipe_association_removed",
    )
    await s.call("delete_shopping_list", {"listId": identifier})
    s.verify("delete_shopping_list", await s.absent(path), "list_absent")
