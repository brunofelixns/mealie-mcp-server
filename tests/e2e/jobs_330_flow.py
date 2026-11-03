"""Native 3.30 import progress/bulk evidence in the owned disposable provider.

AI is deliberately unconfigured here. Controlled AI-positive multipart/SSE
evidence belongs to tests/contracts/test_recipe_jobs.py, not this live flow.
"""

import asyncio
import base64
import json
from io import BytesIO
from urllib.parse import quote
from zipfile import ZipFile

from tests.e2e.recipe_extensions_flow import _remember_import


async def exercise(s):
    await _preview_and_streams(s)
    await _bulk_import_and_report(s)
    await _metadata_batch(s)
    await _bulk_exports(s)
    await _unconfigured_ai(s)


async def _preview_and_streams(s):
    url = "http://assets:8080/recipe.html?case=" + quote(s.prefix + " preview", safe="")
    before = await s.get("/api/recipes?perPage=-1")
    result = await s.call("preview_recipe_from_url", {"url": url, "useOpenAI": False})
    after = await s.get("/api/recipes?perPage=-1")
    s.verify(
        "preview_recipe_from_url",
        "MCP Native URL Import" in json.dumps(result) and before["total"] == after["total"],
        "native_preview_did_not_create_recipe",
    )
    # The earlier native URL import remains until final scenario cleanup. Mealie
    # 3.30 repository_recipes.create preserves the base name on the first import
    # and chooses the first available numbered suffix after a duplicate slug.
    # These synthetic fixture names and their generated slugs have a 1:1 mapping.
    existing_names = {item["name"] for item in after["items"]}
    expected_name = "MCP Native URL Import"
    suffix = 0
    while expected_name in existing_names:
        suffix += 1
        expected_name = f"MCP Native URL Import ({suffix})"
    streamed = await s.call(
        "import_recipe_from_url_with_progress",
        {
            "url": "http://assets:8080/recipe.html?case=" + quote(s.prefix + " stream", safe=""),
            "includeTags": False,
        },
    )
    _remember_import(s, streamed)
    stored = await s.get("/api/recipes/" + streamed)
    s.verify(
        "import_recipe_from_url_with_progress",
        stored["name"] == expected_name and bool(stored["recipeIngredient"]),
        "native_url_sse_completion_persisted_recipe",
    )
    document = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": s.prefix + " SSE JSON",
        "recipeIngredient": ["1 cup water"],
        "recipeInstructions": ["Boil the water."],
    }
    streamed = await s.call(
        "import_recipe_from_html_or_json_with_progress",
        {
            "data": json.dumps(document),
            "url": None,
            "includeCategories": False,
        },
    )
    _remember_import(s, streamed)
    stored = await s.get("/api/recipes/" + streamed)
    s.verify(
        "import_recipe_from_html_or_json_with_progress",
        stored["name"] == document["name"] and bool(stored["recipeIngredient"]),
        "native_html_json_sse_completion_persisted_recipe",
    )


async def _bulk_import_and_report(s):
    before = {item["slug"] for item in (await s.get("/api/recipes?perPage=-1"))["items"]}
    submitted = await s.call(
        "import_recipes_from_urls",
        {
            "imports": [
                {
                    "url": "http://assets:8080/recipe.html?case="
                    + quote(s.prefix + " bulk", safe=""),
                    "tags": [],
                    "categories": None,
                },
                {"url": "http://assets:8080/does-not-exist.html?case=" + quote(s.prefix, safe="")},
            ]
        },
    )
    report_id = submitted["reportId"]
    path = "/api/groups/reports/" + report_id
    s.remember(path)
    s.verify(
        "import_recipes_from_urls",
        submitted["status"] == "accepted" and submitted["atomic"] is False and bool(report_id),
        "native_bulk_job_returns_report_identifier",
    )
    async with asyncio.timeout(90):
        while True:
            report = await s.call("get_recipe_import_report", {"reportId": report_id})
            if report["status"] != "in-progress":
                break
            await asyncio.sleep(0.25)
    s.verify(
        "get_recipe_import_report",
        report["category"] == "bulk_import"
        and report["status"] == "partial"
        and sorted(entry["success"] for entry in report["entries"]) == [False, True],
        "native_report_exposes_partial_import_outcomes",
    )
    listed = await s.call("get_recipe_import_reports", {})
    s.verify(
        "get_recipe_import_reports",
        any(item["id"] == report_id for item in listed)
        and all(item["category"] == "bulk_import" for item in listed),
        "native_report_list_filtered_to_recipe_imports",
    )
    after = {item["slug"] for item in (await s.get("/api/recipes?perPage=-1"))["items"]}
    created = after - before
    assert len(created) == 1, "Bulk job must create exactly the successful recipe"
    for slug in created:
        _remember_import(s, slug)
    response = await s.observer.delete(path)
    response.raise_for_status()
    assert await s.absent(path)


async def _metadata_batch(s):
    slug = s.data["slugs"][0]
    recipe = await s.get("/api/recipes/" + slug)
    stale_slug = s.data["slugs"][1]
    stale_before = await s.get("/api/recipes/" + stale_slug)
    result = await s.call(
        "update_recipe_metadata_batch",
        {
            "concurrency": 2,
            "items": [
                {"slug": slug, "expectedUpdatedAt": recipe["updatedAt"], "prepTime": "13 minutes"},
                {
                    "slug": stale_slug,
                    "expectedUpdatedAt": "stale-e2e-snapshot",
                    "prepTime": "99 minutes",
                },
            ],
        },
    )
    stored = await s.get("/api/recipes/" + slug)
    stale_after = await s.get("/api/recipes/" + stale_slug)
    s.verify(
        "update_recipe_metadata_batch",
        [item["status"] for item in result["items"]] == ["updated", "rejected"]
        and result["atomic"] is False
        and stored["prepTime"] == "13 minutes"
        and stored["recipeIngredient"] == recipe["recipeIngredient"]
        and stale_after == stale_before,
        "ordered_partial_batch_preserves_unrelated_fields_and_rejects_stale_snapshot",
    )
    duplicate = await s.client.call_tool(
        "update_recipe_metadata_batch",
        {
            "concurrency": 2,
            "items": [
                {"slug": slug, "expectedUpdatedAt": stored["updatedAt"], "prepTime": "97 minutes"},
                {
                    "slug": stored["id"],
                    "expectedUpdatedAt": stored["updatedAt"],
                    "prepTime": "98 minutes",
                },
            ],
        },
    )
    s.report["calls"] += 1
    after_duplicate = await s.get("/api/recipes/" + stored["id"])
    s.verify(
        "update_recipe_metadata_batch",
        duplicate.is_error
        and "same recipe" in duplicate.content[0].text
        and after_duplicate == stored,
        "slug_uuid_alias_batch_rejected_without_changing_native_recipe",
    )


async def _bulk_exports(s):
    slug = await s.call("create_recipe", {"name": s.prefix + " bulk delete target"})
    _remember_import(s, slug)
    recipe = await s.get("/api/recipes/" + slug)
    before = {item["id"] for item in await s.get("/api/recipes/bulk-actions/export")}
    submitted = await s.call("export_recipes_bulk", {"recipes": [slug], "exportType": "json"})
    s.verify(
        "export_recipes_bulk", submitted["status"] == "accepted", "native_bulk_export_accepted"
    )
    exports = await s.call("get_recipe_bulk_exports", {})
    created = [item for item in exports if item["id"] not in before]
    s.verify("get_recipe_bulk_exports", len(created) == 1, "native_export_list_contains_new_export")
    downloaded = await s.call("download_recipe_bulk_export", {"exportId": created[0]["id"]})
    content = base64.b64decode(downloaded["dataBase64"], validate=True)
    with ZipFile(BytesIO(content)) as archive:
        assert archive.testzip() is None
        matching = any(
            recipe["name"] in archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".json")
        )
    s.verify(
        "download_recipe_bulk_export",
        len(content) == downloaded["size"] and matching and "fileToken" not in downloaded,
        "native_bulk_export_zip_roundtrip_without_exposing_token",
    )
    await s.call("purge_recipe_bulk_exports", {})
    s.verify(
        "purge_recipe_bulk_exports",
        await s.get("/api/recipes/bulk-actions/export") == [],
        "native_export_records_purged_in_disposable_group",
    )
    deleted = await s.call("delete_recipes_bulk", {"recipes": [slug]})
    s.verify(
        "delete_recipes_bulk",
        deleted["atomic"] is False and await s.absent("/api/recipes/" + slug),
        "explicit_native_bulk_delete_target_absent",
    )
    s.data["slugs"].remove(slug)


async def _unconfigured_ai(s):
    settings = await s.get("/api/groups/ai-providers/settings")
    assert settings["providers"] == [] and settings["defaultProviderId"] is None
    assert settings["aiEnabled"] is False
    before = await s.get("/api/recipes?perPage=-1")
    for name in ("import_recipe_with_ai", "import_recipe_with_ai_with_progress"):
        result = await s.client.call_tool(name, {"content": s.prefix + " unconfigured AI source"})
        s.report["calls"] += 1
        assert result.is_error, "Disposable Mealie must keep its AI provider unconfigured"
        message = result.content[0].text
        expected = (
            "Mealie API error 400."
            if name == "import_recipe_with_ai"
            else "Mealie reported an import failure."
        )
        assert expected in message and s.prefix not in message
        after = await s.get("/api/recipes?perPage=-1")
        assert after["total"] == before["total"]
        s.records[name] = {
            "tool": name,
            "outcome": "configuration_rejection",
            "checks": [
                "provider_ai_unconfigured",
                "write_not_replayed",
                "recipe_count_unchanged",
                "provider_body_redacted",
                "controlled_positive_evidence_in_contract_tests_only",
            ],
        }
