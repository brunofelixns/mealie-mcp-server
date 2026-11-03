"""Read real individual media and shared ZIPs without writing host files."""

import base64
from io import BytesIO
from zipfile import ZipFile

from tests.e2e.stack import png


def _bytes(result):
    value = base64.b64decode(result["dataBase64"], validate=True)
    assert len(value) == result["size"] and value
    return value


async def exercise(s):
    slug = s.data["slugs"][0]
    recipe = await s.get("/api/recipes/" + slug)
    listed = await s.call("get_recipe_assets", {"slug": slug})
    s.verify(
        "get_recipe_assets", listed["assets"] == recipe["assets"], "asset_metadata_matches_provider"
    )
    name = recipe["assets"][0]["fileName"]
    attachment = await s.call("download_recipe_asset", {"slug": slug, "fileName": name})
    raw = await s.observer.get(f"/api/media/recipes/{recipe['id']}/assets/{name}")
    raw.raise_for_status()
    s.verify(
        "download_recipe_asset",
        _bytes(attachment) == raw.content,
        "asset_bytes_match_native_download",
    )
    image = await s.call("download_recipe_image", {"slug": slug})
    raw = await s.observer.get(f"/api/media/recipes/{recipe['id']}/images/original.webp")
    raw.raise_for_status()
    s.verify(
        "download_recipe_image", _bytes(image) == raw.content, "hero_image_bytes_match_provider"
    )

    event = await s.call(
        "create_recipe_timeline_event",
        {"slug": slug, "subject": s.prefix + " Media", "eventType": "info"},
    )
    event_path = "/api/recipes/timeline/events/" + event["id"]
    s.remember(event_path)
    await s.call(
        "set_recipe_timeline_event_image",
        {
            "eventId": event["id"],
            "imageBase64": base64.b64encode(png()).decode(),
            "extension": "png",
        },
    )
    image = await s.call("download_recipe_timeline_image", {"slug": slug, "eventId": event["id"]})
    raw = await s.observer.get(
        f"/api/media/recipes/{recipe['id']}/images/timeline/{event['id']}/original.webp"
    )
    raw.raise_for_status()
    s.verify(
        "download_recipe_timeline_image",
        _bytes(image) == raw.content,
        "event_image_bytes_match_provider",
    )
    await s.call(
        "update_recipe_timeline_event",
        {"eventId": event["id"], "subject": event["subject"], "image": "does not have image"},
    )
    absent = await s.observer.get(
        f"/api/media/recipes/{recipe['id']}/images/timeline/{event['id']}/original.webp"
    )
    s.verify(
        "update_recipe_timeline_event",
        absent.status_code == 404,
        "mealie330_image_flag_removes_physical_event_image",
    )
    await s.call("delete_recipe_timeline_event", {"eventId": event["id"]})
    s.verify(
        "delete_recipe_timeline_event", await s.absent(event_path), "temporary_media_event_removed"
    )

    token = await s.call("create_recipe_share_link", {"slug": slug})
    share_path = "/api/shared/recipes/" + token["id"]
    s.remember(share_path)
    shared = await s.call("get_shared_recipe", {"tokenId": token["id"]})
    s.verify(
        "get_shared_recipe",
        shared["id"] == recipe["id"] and shared["slug"] == slug,
        "share_token_reads_selected_recipe",
    )
    result = await s.call("download_shared_recipe", {"tokenId": token["id"]})
    with ZipFile(BytesIO(_bytes(result))) as archive:
        valid = archive.testzip() is None and any(
            path.endswith(".json") for path in archive.namelist()
        )
    s.verify("download_shared_recipe", valid, "shared_archive_is_valid_and_contains_recipe")
    await s.call("delete_recipe_share_link", {"tokenId": token["id"]})
    s.verify(
        "delete_recipe_share_link", await s.absent(share_path), "temporary_share_token_removed"
    )
