"""Collections and advanced planning against the disposable Mealie 3.30 provider."""

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from time import monotonic
from urllib.parse import quote

import httpx2 as httpx

from tests.e2e.scenarios import contains


async def exercise(s):
    slug = s.data["slugs"][0]
    await _cookbooks(s)
    await _personal_and_collaboration(s, slug)
    await exercise_recipe_household(s)
    await _actions(s, slug)
    await _planning(s, slug)


async def exercise_recipe_household(s):
    slug = s.data["slugs"][0]
    path = "/api/households/self/recipes/" + slug
    result = await s.call("get_recipe_household", {"slug": slug})
    persisted = await s.get(path)
    recipe = await s.get("/api/recipes/" + slug)
    s.verify(
        "get_recipe_household",
        result == persisted
        and result["recipeId"] == recipe["id"]
        and result.get("lastMade") == persisted.get("lastMade"),
        "current_household_recipe_and_last_made_match_native_provider",
    )


async def _cookbooks(s):
    created = await s.call(
        "create_cookbook",
        {
            "name": s.prefix + " Cookbook",
            "description": "Weekly meals",
            "public": False,
            "position": 0,
            "queryFilterString": "",
        },
    )
    identifier = created["id"]
    path = "/api/households/cookbooks/" + identifier
    s.remember(path)
    stored = await s.get(path)
    s.verify(
        "create_cookbook",
        stored["name"] == s.prefix + " Cookbook" and stored["public"] is False,
        "private_cookbook_persisted",
    )
    result = await s.call("get_cookbook", {"cookbookId": identifier})
    s.verify("get_cookbook", result == stored, "cookbook_matches_native_provider")
    listed = await s.call("get_cookbooks", {"perPage": 100})
    s.verify("get_cookbooks", contains(listed["items"], identifier), "created_cookbook_listed")
    await s.call(
        "update_cookbook",
        {
            "cookbookId": stored["slug"],
            "changes": {"description": "", "position": 2, "name": " " + s.prefix + " Renamed "},
        },
    )
    updated = await s.get(path)
    s.verify(
        "update_cookbook",
        updated["description"] == ""
        and updated["position"] == 2
        and updated["public"] is False
        and updated["name"] == s.prefix + " Renamed"
        and updated["slug"] != stored["slug"]
        and updated["householdId"] == stored["householdId"],
        "cookbook_update_preserves_visibility_and_ownership",
    )
    await s.call("delete_cookbook", {"cookbookId": updated["slug"]})
    s.verify("delete_cookbook", await s.absent(path), "owned_cookbook_deleted")


async def _personal_and_collaboration(s, slug):
    for name, path in (
        ("get_recipe_favorites", "/api/users/self/favorites"),
        ("get_recipe_ratings", "/api/users/self/ratings"),
    ):
        result = await s.call(name, {})
        s.verify(
            name, result == await s.get(path), "authenticated_user_collection_matches_provider"
        )

    comment = await s.call(
        "create_recipe_comment", {"slug": slug, "text": s.prefix + " Collection"}
    )
    path = "/api/comments/" + comment["id"]
    s.remember(path)
    result = await s.call("get_recipe_comment", {"commentId": comment["id"]})
    s.verify("get_recipe_comment", result == await s.get(path), "single_comment_matches_provider")
    listed = await s.call("list_recipe_comments", {"perPage": 100})
    s.verify(
        "list_recipe_comments", contains(listed["items"], comment["id"]), "owned_comment_listed"
    )
    await s.call("delete_recipe_comment", {"commentId": comment["id"]})
    assert await s.absent(path)

    event = await s.call(
        "create_recipe_timeline_event",
        {"slug": slug, "subject": s.prefix, "eventType": "info", "eventMessage": "Collection"},
    )
    path = "/api/recipes/timeline/events/" + event["id"]
    s.remember(path)
    result = await s.call("get_recipe_timeline_event", {"eventId": event["id"]})
    s.verify(
        "get_recipe_timeline_event",
        result == await s.get(path),
        "single_timeline_event_matches_provider",
    )
    await s.call("delete_recipe_timeline_event", {"eventId": event["id"]})
    assert await s.absent(path)

    share = await s.call("create_recipe_share_link", {"slug": slug})
    path = "/api/shared/recipes/" + share["id"]
    s.remember(path)
    result = await s.call("get_recipe_share_link", {"tokenId": share["id"]})
    s.verify(
        "get_recipe_share_link", result == await s.get(path), "single_share_token_matches_provider"
    )
    await s.call("delete_recipe_share_link", {"tokenId": share["id"]})
    assert await s.absent(path)


async def _actions(s, slug):
    # The target is owned by this isolated Compose stack. No public hook is contacted.
    action_path = "/action?case=" + quote(s.prefix, safe="")
    action_url = "http://assets:8080" + action_path
    created = await s.call(
        "create_recipe_action",
        {"actionType": "post", "title": s.prefix + " Action", "url": action_url},
    )
    identifier = created["id"]
    path = "/api/households/recipe-actions/" + identifier
    s.remember(path)
    stored = await s.get(path)
    s.verify(
        "create_recipe_action",
        stored["url"] == action_url and stored["actionType"] == "post",
        "controlled_internal_action_persisted",
    )
    result = await s.call("get_recipe_action", {"actionId": identifier})
    s.verify("get_recipe_action", result == stored, "action_matches_native_provider")
    listed = await s.call("get_recipe_actions", {"perPage": 100})
    s.verify("get_recipe_actions", contains(listed["items"], identifier), "owned_action_listed")
    await s.call(
        "update_recipe_action",
        {"actionId": identifier, "changes": {"title": s.prefix + " Updated"}},
    )
    updated = await s.get(path)
    s.verify(
        "update_recipe_action",
        updated["title"] == s.prefix + " Updated"
        and updated["url"] == stored["url"]
        and updated["householdId"] == stored["householdId"]
        and updated["groupId"] == stored["groupId"],
        "action_update_preserves_native_ownership",
    )
    result = await s.call(
        "trigger_recipe_action", {"actionId": identifier, "slug": slug, "recipe_scale": 2}
    )
    assert result is None and await s.get(path) == updated
    deadline = monotonic() + 10
    async with httpx.AsyncClient(timeout=5, trust_env=False) as observer:
        while True:
            receipts = (await observer.get("http://assets:8080/receipts")).raise_for_status().json()
            received = any(
                row.get("path") == action_path and row.get("method") == "POST" for row in receipts
            )
            if received or monotonic() >= deadline:
                break
            await asyncio.sleep(0.1)
    s.verify("trigger_recipe_action", received, "native_action_delivered_to_owned_internal_fixture")
    await s.call("delete_recipe_action", {"actionId": identifier})
    s.verify("delete_recipe_action", await s.absent(path), "owned_action_deleted")


async def _planning(s, slug):
    recipe = await s.get("/api/recipes/" + slug)
    start = datetime.now(UTC).date()
    end = (start + timedelta(days=6)).isoformat()
    created = await s.call(
        "create_mealplan_entry",
        {
            "date": start.isoformat(),
            "endDate": end,
            "entryType": "dinner",
            "recipeId": recipe["id"],
            "recipeScale": 2,
            "title": s.prefix + " Weekly",
            "text": "Weekly planning note",
        },
    )
    identifier = created["id"]
    path = "/api/households/mealplans/" + str(identifier)
    s.remember(path)
    stored = await s.get(path)
    s.verify(
        "create_mealplan_entry",
        stored["endDate"] == end
        and stored["recipeScale"] == 2
        and stored["text"] == "Weekly planning note",
        "weekly_entry_dates_scale_text_persisted",
    )
    result = await s.call("get_mealplan_entry", {"entryId": identifier})
    s.verify("get_mealplan_entry", result == stored, "entry_matches_native_provider")
    listed = await s.call(
        "list_mealplan_entries",
        {
            "start_date": start.isoformat(),
            "end_date": end,
            "include_week_entries": True,
            "perPage": 100,
        },
    )
    s.verify(
        "list_mealplan_entries",
        contains(listed["items"], identifier),
        "weekly_entry_in_native_listing",
    )
    await s.call(
        "update_mealplan_entry", {"entryId": identifier, "changes": {"text": "", "recipeScale": 3}}
    )
    updated = await s.get(path)
    s.verify(
        "update_mealplan_entry",
        updated["text"] == ""
        and updated["recipeScale"] == 3
        and updated["endDate"] == end
        and updated["recipeId"] == recipe["id"]
        and updated["userId"] == stored["userId"],
        "entry_update_preserves_week_recipe_ownership",
    )

    rule = await s.call(
        "create_mealplan_rule",
        {"day": "unset", "entryType": "dinner", "queryFilterString": "id=" + recipe["id"]},
    )
    rule_id = rule["id"]
    rule_path = "/api/households/mealplans/rules/" + rule_id
    s.remember(rule_path)
    rule_stored = await s.get(rule_path)
    s.verify(
        "create_mealplan_rule",
        rule_stored["entryType"] == "dinner" and rule_stored["day"] == "unset",
        "native_rule_persisted",
    )
    result = await s.call("get_mealplan_rule", {"ruleId": rule_id})
    s.verify("get_mealplan_rule", result == rule_stored, "rule_matches_native_provider")
    listed = await s.call("get_mealplan_rules", {"perPage": 100})
    s.verify("get_mealplan_rules", contains(listed["items"], rule_id), "owned_rule_listed")
    random = await s.call(
        "create_random_mealplan_entry",
        {"date": start.isoformat(), "endDate": end, "entryType": "dinner"},
    )
    random_path = "/api/households/mealplans/" + str(random["id"])
    s.remember(random_path)
    random_stored = await s.get(random_path)
    s.verify(
        "create_random_mealplan_entry",
        random_stored["recipeId"] == recipe["id"] and random_stored["endDate"] == end,
        "native_random_entry_obeys_rule_and_week",
    )
    await s.call("update_mealplan_rule", {"ruleId": rule_id, "changes": {"queryFilterString": ""}})
    rule_updated = await s.get(rule_path)
    s.verify(
        "update_mealplan_rule",
        rule_updated["queryFilterString"] == ""
        and rule_updated["day"] == "unset"
        and rule_updated["householdId"] == rule_stored["householdId"],
        "rule_update_preserves_native_ownership",
    )
    await s.call("delete_mealplan_rule", {"ruleId": rule_id})
    s.verify("delete_mealplan_rule", await s.absent(rule_path), "owned_rule_deleted")

    await _calendar(s)
    await s.call("delete_mealplan_entry", {"entryId": identifier})
    s.verify("delete_mealplan_entry", await s.absent(path), "owned_weekly_entry_deleted")
    await s.call("delete_mealplan_entry", {"entryId": random["id"]})
    assert await s.absent(random_path)


async def _calendar(s):
    path = "/api/households/mealplans/ical"
    original = await s.call("get_mealplan_ical_token", {})
    s.verify(
        "get_mealplan_ical_token",
        original == await s.get(path),
        "calendar_token_matches_native_provider",
    )
    # Every scenario owns its disposable household; never rotate a user calendar.
    assert original["mealplanIcalToken"] is None
    try:
        rotated = await s.call("rotate_mealplan_ical_token", {})
        token = rotated["mealplanIcalToken"]
        s.verify(
            "rotate_mealplan_ical_token",
            isinstance(token, str) and bool(token) and rotated == await s.get(path),
            "calendar_enabled_with_native_token",
        )
        calendar = await s.call(
            "get_mealplan_ical_feed",
            {
                "token": token,
                "types": ["dinner"],
                "tz": "Europe/Madrid",
                "dinner": "19:30:00",
                "includeNotes": True,
            },
        )
        raw = base64.b64decode(calendar["dataBase64"], validate=True)
        s.verify(
            "get_mealplan_ical_feed",
            b"BEGIN:VCALENDAR" in raw and b"END:VCALENDAR" in raw and calendar["size"] == len(raw),
            "bounded_native_calendar_downloaded",
        )
        await s.call("delete_mealplan_ical_token", {})
        s.verify(
            "delete_mealplan_ical_token",
            (await s.get(path))["mealplanIcalToken"] is None,
            "calendar_token_disabled",
        )
    finally:
        (await s.observer.delete(path)).raise_for_status()
