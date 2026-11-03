"""Verify additional recipe operations against the disposable Mealie provider."""

import base64
import json
import uuid
from io import BytesIO
from urllib.parse import quote
from zipfile import ZipFile

from tests.e2e.scenarios import contains
from tests.e2e.stack import png


async def exercise(s):
    slug = s.data["slugs"][0]
    await _notes_and_metadata(s, slug)
    await _collaboration(s, slug)
    await _assets_and_import_export(s, slug)


async def _notes_and_metadata(s, slug):
    path = "/api/recipes/" + slug
    recipe = await s.get(path)
    await s.call(
        "update_recipe_metadata",
        {
            "slug": slug,
            "expectedUpdatedAt": recipe["updatedAt"],
            "prepTime": "10 minutes",
            "cookTime": "20 minutes",
            "nutrition": {"calories": "123"},
            "settings": {"disableComments": False, "showAssets": True},
            "extras": {"e2eVerification": s.prefix},
        },
    )
    stored = await s.get(path)
    s.verify(
        "update_recipe_metadata",
        stored["prepTime"] == "10 minutes"
        and stored["cookTime"] == "20 minutes"
        and stored["nutrition"]["calories"] == "123"
        and stored["settings"]["disableComments"] is False
        and stored["settings"]["showAssets"] is True
        and stored["extras"]["e2eVerification"] == s.prefix
        and stored["recipeIngredient"] == recipe["recipeIngredient"],
        "metadata_persisted_without_replacing_ingredients",
    )
    reference = str(uuid.uuid4())
    original_notes = stored["notes"]
    await s.call(
        "add_recipe_note",
        {
            "slug": slug,
            "expectedUpdatedAt": stored["updatedAt"],
            "referenceId": reference,
            "title": s.prefix + " Storage",
            "text": "Refrigerate after cooling.",
        },
    )
    stored = await s.get(path)
    s.verify(
        "add_recipe_note",
        stored["notes"][:-1] == original_notes
        and stored["notes"][-1]["referenceId"] == reference
        and stored["notes"][-1]["text"] == "Refrigerate after cooling.",
        "note_appended_with_stable_identity",
    )
    result = await s.call("get_recipe_notes", {"slug": slug})
    current = await s.get(path)
    s.verify(
        "get_recipe_notes",
        result["notes"] == current["notes"] and result["updatedAt"] == current["updatedAt"],
        "notes_and_snapshot_match_persisted_recipe",
    )
    await s.call(
        "update_recipe_note",
        {
            "slug": slug,
            "expectedUpdatedAt": current["updatedAt"],
            "referenceId": reference,
            "title": "",
            "text": "Use within three days.",
        },
    )
    stored = await s.get(path)
    s.verify(
        "update_recipe_note",
        stored["notes"][:-1] == original_notes
        and stored["notes"][-1]["referenceId"] == reference
        and stored["notes"][-1]["title"] == ""
        and stored["notes"][-1]["text"] == "Use within three days.",
        "note_edited_in_place_with_empty_title",
    )
    await s.call(
        "delete_recipe_note",
        {"slug": slug, "expectedUpdatedAt": stored["updatedAt"], "referenceId": reference},
    )
    s.verify(
        "delete_recipe_note",
        (await s.get(path))["notes"] == original_notes,
        "only_created_note_removed",
    )


async def _collaboration(s, slug):
    recipe = await s.get("/api/recipes/" + slug)
    comment = await s.call("create_recipe_comment", {"slug": slug, "text": s.prefix + " Good"})
    comment_path = "/api/comments/" + comment["id"]
    s.remember(comment_path)
    s.verify(
        "create_recipe_comment",
        (await s.get(comment_path))["text"] == s.prefix + " Good",
        "comment_persisted_for_authenticated_user",
    )
    comments = await s.call("get_recipe_comments", {"slug": slug})
    persisted = await s.get("/api/recipes/" + slug + "/comments")
    s.verify(
        "get_recipe_comments",
        contains(comments, comment["id"]) and comments == persisted,
        "recipe_comment_list_matches_provider",
    )
    await s.call(
        "update_recipe_comment", {"commentId": comment["id"], "text": s.prefix + " Edited"}
    )
    s.verify(
        "update_recipe_comment",
        (await s.get(comment_path))["text"] == s.prefix + " Edited",
        "comment_edit_persisted",
    )
    await s.call("delete_recipe_comment", {"commentId": comment["id"]})
    s.verify("delete_recipe_comment", await s.absent(comment_path), "comment_removed")

    shared = await s.call("create_recipe_share_link", {"slug": slug})
    share_path = "/api/shared/recipes/" + shared["id"]
    s.remember(share_path)
    s.verify(
        "create_recipe_share_link",
        (await s.get(share_path))["recipeId"] == recipe["id"],
        "share_token_persisted_for_recipe",
    )
    links = await s.call("get_recipe_share_links", {"slug": slug})
    persisted = await s.get("/api/shared/recipes?recipe_id=" + recipe["id"])
    s.verify(
        "get_recipe_share_links",
        contains(links, shared["id"]) and links == persisted,
        "filtered_share_tokens_match_provider",
    )
    await s.call("delete_recipe_share_link", {"tokenId": shared["id"]})
    s.verify("delete_recipe_share_link", await s.absent(share_path), "share_token_revoked")

    event = await s.call(
        "create_recipe_timeline_event",
        {
            "slug": slug,
            "subject": s.prefix + " Cooked",
            "eventType": "info",
            "eventMessage": "Done",
        },
    )
    event_path = "/api/recipes/timeline/events/" + event["id"]
    s.remember(event_path)
    stored = await s.get(event_path)
    s.verify(
        "create_recipe_timeline_event",
        stored["recipeId"] == recipe["id"]
        and stored["subject"] == s.prefix + " Cooked"
        and stored["eventMessage"] == "Done",
        "timeline_entry_persisted",
    )
    timeline = await s.call("get_recipe_timeline", {"slug": slug, "perPage": 100})
    persisted = await s.get(
        "/api/recipes/timeline/events?perPage=100&queryFilter=recipeId=" + recipe["id"]
    )
    s.verify(
        "get_recipe_timeline",
        contains(timeline["items"], event["id"])
        and {row["id"] for row in timeline["items"]} == {row["id"] for row in persisted["items"]},
        "recipe_timeline_matches_filtered_provider_entries",
    )
    await s.call(
        "update_recipe_timeline_event",
        {"eventId": event["id"], "subject": s.prefix + " Served", "eventMessage": "Updated"},
    )
    stored = await s.get(event_path)
    s.verify(
        "update_recipe_timeline_event",
        stored["subject"] == s.prefix + " Served" and stored["eventMessage"] == "Updated",
        "timeline_edit_persisted",
    )
    await s.call(
        "set_recipe_timeline_event_image",
        {
            "eventId": event["id"],
            "imageBase64": base64.b64encode(png()).decode(),
            "extension": "png",
        },
    )
    s.verify(
        "set_recipe_timeline_event_image",
        (await s.get(event_path))["image"] == "has image",
        "timeline_image_state_persisted",
    )
    await s.call("delete_recipe_timeline_event", {"eventId": event["id"]})
    s.verify("delete_recipe_timeline_event", await s.absent(event_path), "timeline_entry_removed")


def _remember_import(s, slug):
    assert isinstance(slug, str) and slug
    assert slug not in s.data["slugs"], "Import unexpectedly reused an existing recipe slug"
    s.data["slugs"].append(slug)
    s.remember("/api/recipes/" + slug)


def _template(formats, kind):
    options = formats[kind]
    assert options, "Mealie did not advertise a " + kind + " export template"
    return next((name for name in options if "mealie" in name.lower()), options[0])


async def _assets_and_import_export(s, slug):
    asset = await s.call(
        "upload_recipe_asset",
        {
            "slug": slug,
            "name": s.prefix + " attachment",
            "icon": "mdi-file-image",
            "extension": "png",
            "fileBase64": base64.b64encode(png(b"\0\xff\0")).decode(),
        },
    )
    stored = await s.get("/api/recipes/" + slug)
    s.verify(
        "upload_recipe_asset",
        any(row["fileName"] == asset["fileName"] for row in stored["assets"]),
        "uploaded_asset_metadata_persisted",
    )
    asset = await s.call(
        "create_recipe_asset_from_url", {"slug": slug, "url": "http://assets:8080/image.png"}
    )
    stored = await s.get("/api/recipes/" + slug)
    s.verify(
        "create_recipe_asset_from_url",
        any(row["fileName"] == asset["fileName"] for row in stored["assets"])
        and len(stored["assets"]) >= 2,
        "url_asset_added_without_replacing_uploaded_asset",
    )
    native_slug = await s.call(
        "import_recipe_from_url",
        {"url": "http://assets:8080/recipe.html?case=" + quote(s.prefix, safe="")},
    )
    _remember_import(s, native_slug)
    native = await s.get("/api/recipes/" + native_slug)
    s.verify(
        "import_recipe_from_url",
        native["name"] == "MCP Native URL Import" and bool(native["recipeIngredient"]),
        "native_url_import_created_recipe_and_ingredients",
    )
    document = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": s.prefix + " Native JSON Import",
        "description": "Disposable JSON import verification",
        "recipeIngredient": ["1 teaspoon salt"],
        "recipeInstructions": [{"@type": "HowToStep", "text": "Mix and serve."}],
    }
    json_slug = await s.call("import_recipe_from_html_or_json", {"data": json.dumps(document)})
    _remember_import(s, json_slug)
    imported = await s.get("/api/recipes/" + json_slug)
    s.verify(
        "import_recipe_from_html_or_json",
        imported["name"] == document["name"]
        and bool(imported["recipeIngredient"])
        and contains(imported["recipeInstructions"], "Mix and serve."),
        "structured_json_import_persisted_content",
    )
    formats = await s.call("get_recipe_export_formats", {})
    persisted_formats = await s.get("/api/recipes/exports")
    s.verify(
        "get_recipe_export_formats",
        formats == persisted_formats and bool(formats["json"]) and bool(formats["zip"]),
        "json_and_zip_templates_advertised_by_provider",
    )
    exported = await s.call(
        "export_recipe", {"slug": json_slug, "templateName": _template(formats, "json")}
    )
    raw = base64.b64decode(exported["dataBase64"], validate=True)
    decoded = json.loads(raw)
    s.verify(
        "export_recipe",
        len(raw) == exported["size"]
        and contains(decoded, (await s.get("/api/recipes/" + json_slug))["name"]),
        "json_export_contains_persisted_recipe_content",
    )
    exported_zip = await s.call(
        "export_recipe", {"slug": json_slug, "templateName": _template(formats, "zip")}
    )
    archive = base64.b64decode(exported_zip["dataBase64"], validate=True)
    with ZipFile(BytesIO(archive)) as zipped:
        members = zipped.namelist()
        assert zipped.testzip() is None
        exported_recipe_present = any(
            member.endswith(".json") and contains(json.loads(zipped.read(member)), imported["name"])
            for member in members
        )
    s.verify(
        "export_recipe",
        len(archive) == exported_zip["size"] and exported_recipe_present,
        "zip_export_is_valid_and_contains_recipe_json",
    )
    # Recreate the exported source from its native archive without slug/identity collisions.
    await s.call("delete_recipe", {"slug": json_slug})
    s.verify("delete_recipe", await s.absent("/api/recipes/" + json_slug), "zip_source_removed")
    s.data["slugs"].remove(json_slug)
    zip_slug = await s.call("import_recipe_from_zip", {"archiveBase64": exported_zip["dataBase64"]})
    _remember_import(s, zip_slug)
    restored = await s.get("/api/recipes/" + zip_slug)
    s.verify(
        "import_recipe_from_zip",
        restored["name"] == imported["name"]
        and contains(restored["recipeInstructions"], "Mix and serve.")
        and bool(restored["recipeIngredient"]),
        "native_zip_roundtrip_restores_recipe_content",
    )
