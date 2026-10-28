"""Real organizer, food, unit and equipment CRUD/lookup with persisted IDs."""

from tests.e2e.scenarios import contains


async def prepare(s):
    for singular, plural, id_field in (
        ("category", "categories", "categoryId"),
        ("tag", "tags", "tagId"),
    ):
        path = "/api/organizers/" + plural
        item = await s.call("create_" + singular, {"name": s.prefix + " " + singular})
        s.remember(path + "/" + item["id"])
        s.verify(
            "create_" + singular,
            (await s.get(path + "/" + item["id"]))["name"] == item["name"],
            "created_value_persisted",
        )
        name = s.prefix + " renamed " + singular
        updated = await s.call("update_" + singular, {id_field: item["id"], "name": name})
        s.verify(
            "update_" + singular,
            (await s.get(path + "/" + item["id"]))["name"] == name,
            "rename_persisted",
        )
        s.data[singular] = updated
        result = await s.call("get_" + singular, {id_field: item["id"]})
        s.verify(
            "get_" + singular,
            result["id"] == item["id"] and result["name"] == name,
            "identity_and_name",
        )
        result = await s.call("get_" + singular + "_by_slug", {singular + "Slug": updated["slug"]})
        s.verify(
            "get_" + singular + "_by_slug",
            result["id"] == item["id"],
            "slug_resolves_created_identity",
        )
        result = await s.call("get_" + plural, {"page": 1, "perPage": 100})
        s.verify("get_" + plural, contains(result, item["id"]), "created_identity_in_page")
        result = await s.call("get_empty_" + plural, {})
        s.verify("get_empty_" + plural, contains(result, item["id"]), "unused_identity_is_empty")

    for singular, plural, id_field, extra in (
        ("food", "foods", "foodId", {"aliases": [s.prefix + " salt alias"]}),
        ("unit", "units", "unitId", {"abbreviation": "sp", "fraction": True}),
        ("tool", "tools", "toolId", {}),
    ):
        path = "/api/organizers/tools" if singular == "tool" else "/api/" + plural
        name = s.prefix + " " + singular
        item = await s.call("create_" + singular, {"name": name, **extra})
        s.data[singular] = item
        s.remember(path + "/" + item["id"])
        s.verify(
            "create_" + singular,
            (await s.get(path + "/" + item["id"]))["name"] == name,
            "created_value_persisted",
        )
        changes = (
            {"name": name + " updated"}
            if singular == "tool"
            else {"description": s.prefix + " description"}
        )
        updated = await s.call("update_" + singular, {id_field: item["id"], **changes})
        s.data[singular] = updated
        stored = await s.get(path + "/" + item["id"])
        s.verify(
            "update_" + singular,
            all(stored[key] == value for key, value in changes.items()),
            "updated_fields_persisted",
        )
        result = await s.call("get_" + singular, {id_field: item["id"]})
        s.verify("get_" + singular, result["id"] == item["id"], "created_identity_returned")
        result = await s.call(
            "get_" + plural, {"search": updated["name"], "page": 1, "perPage": 10}
        )
        s.verify("get_" + plural, contains(result, item["id"]), "search_finds_created_identity")
        lookup = "get_" + singular + "_matches"
        result = await s.call(lookup, {"queries": [updated["name"]], "maxMatchesPerQuery": 3})
        s.verify(lookup, contains(result, item["id"]), "lookup_resolves_real_identity")

    target = await s.call("create_food", {"name": s.prefix + " merged food"})
    s.data["targetFood"] = target
    s.remember("/api/foods/" + target["id"])
    s.verify(
        "create_food",
        (await s.get("/api/foods/" + target["id"]))["name"] == target["name"],
        "merge_target_persisted",
    )


async def cleanup(s):
    for name, item, path, field in (
        ("food", s.data["targetFood"], "/api/foods/", "foodId"),
        ("unit", s.data["unit"], "/api/units/", "unitId"),
        ("tool", s.data["tool"], "/api/organizers/tools/", "toolId"),
        ("category", s.data["category"], "/api/organizers/categories/", "categoryId"),
        ("tag", s.data["tag"], "/api/organizers/tags/", "tagId"),
    ):
        await s.call("delete_" + name, {field: item["id"]})
        s.verify("delete_" + name, await s.absent(path + item["id"]), "deleted_identity_absent")
