"""Controlled native Mealie HTTP/SSE positives, distinct from live AI evidence."""

import base64
import json

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server

ID = "11111111-1111-4111-8111-111111111111"
CASES = [
    (
        "preview_recipe_from_url",
        {"url": "https://recipes.test/soup", "useOpenAI": False},
        "POST",
        "/api/recipes/test-scrape-url",
        {"name": "Soup", "future": [False]},
    ),
    (
        "import_recipe_with_ai",
        {
            "content": "Soup recipe",
            "url": "https://recipes.test/soup",
            "translateLanguage": "es",
            "createNewOrganizers": False,
        },
        "POST",
        "/api/recipes/create/ai",
        "soup",
    ),
    (
        "import_recipe_from_url_with_progress",
        {"url": "https://recipes.test/soup", "includeTags": False},
        "POST",
        "/api/recipes/create/url/stream",
        "soup",
    ),
    (
        "import_recipe_from_html_or_json_with_progress",
        {"data": '{"name":"Soup"}', "url": None, "includeCategories": False},
        "POST",
        "/api/recipes/create/html-or-json/stream",
        "soup",
    ),
    (
        "import_recipe_with_ai_with_progress",
        {"content": "Soup recipe", "createNewOrganizers": False},
        "POST",
        "/api/recipes/create/ai/stream",
        "soup",
    ),
    (
        "import_recipes_from_urls",
        {"imports": [{"url": "https://recipes.test/soup", "tags": [], "categories": None}]},
        "POST",
        "/api/recipes/create/url/bulk",
        {"reportId": ID},
    ),
    (
        "get_recipe_import_reports",
        {},
        "GET",
        "/api/groups/reports",
        [{"id": ID, "category": "bulk_import", "status": "in-progress", "future": 1}],
    ),
    (
        "get_recipe_import_report",
        {"reportId": ID},
        "GET",
        "/api/groups/reports/" + ID,
        {
            "id": ID,
            "category": "bulk_import",
            "status": "finished",
            "entries": [{"success": False}],
            "future": 1,
        },
    ),
    (
        "delete_recipes_bulk",
        {"recipes": ["soup"]},
        "POST",
        "/api/recipes/bulk-actions/delete",
        None,
    ),
    (
        "export_recipes_bulk",
        {"recipes": ["soup"], "exportType": "json"},
        "POST",
        "/api/recipes/bulk-actions/export",
        None,
    ),
    (
        "get_recipe_bulk_exports",
        {},
        "GET",
        "/api/recipes/bulk-actions/export",
        [{"id": ID, "name": "recipes", "future": 1}],
    ),
    (
        "download_recipe_bulk_export",
        {"exportId": ID},
        "GET",
        "/api/recipes/bulk-actions/export/" + ID + "/download",
        {"fileToken": "private-token"},
    ),
    (
        "purge_recipe_bulk_exports",
        {},
        "DELETE",
        "/api/recipes/bulk-actions/export/purge",
        {"message": "deleted"},
    ),
    (
        "update_recipe_metadata_batch",
        {
            "items": [{"slug": "soup", "expectedUpdatedAt": "snapshot", "prepTime": "PT10M"}],
            "concurrency": 2,
        },
        "GET",
        "/api/recipes/soup",
        {"id": ID, "slug": "soup", "updatedAt": "snapshot", "future": [False]},
    ),
]


class EventStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'event: progress\ndata: {"message":"private-token private recipe"}\n\n'
        yield b'event: done\ndata: {"slug":"soup"}\n\n'


@pytest.mark.parametrize("name", [case[0] for case in CASES])
async def test_recipe_jobs_mcp_positive(name):
    _, args, method, path, response = next(case for case in CASES if case[0] == name)
    calls = []

    def handle(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer fixture"
        if request.url.path == "/api/utils/download":
            assert name == "download_recipe_bulk_export"
            assert request.url.params["token"] == "private-token"
            return httpx.Response(
                200, content=b"PKexport", headers={"content-type": "application/zip"}
            )
        if name == "update_recipe_metadata_batch":
            assert request.url.path == (path if len(calls) == 1 else "/api/recipes/" + ID)
            if request.method == "PATCH":
                assert json.loads(request.content) == {"prepTime": "PT10M"}
                return httpx.Response(200, json={**response, "prepTime": "PT10M"})
        else:
            assert request.url.path == path
        assert request.method == method
        if "with_ai" in name:
            assert request.headers["content-type"].startswith("multipart/form-data;")
            assert b'name="content"\r\n\r\nSoup recipe' in request.content
            assert b'name="createNewOrganizers"\r\n\r\nfalse' in request.content
            assert (
                b"translateLanguage" in request.content if name == "import_recipe_with_ai" else True
            )
        elif method == "POST":
            assert json.loads(request.content) == args
        if name == "get_recipe_import_reports":
            assert list(request.url.params.multi_items()) == [("report_type", "bulk_import")]
        if path.endswith("/stream"):
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=EventStream()
            )
        return (
            httpx.Response(200, content=b"null")
            if response is None
            else httpx.Response(200, json=response)
        )

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    progress_messages = []

    async def progress(progress, total, message):
        progress_messages.append(message)

    async with Client(server, progress_handler=progress) as client:
        result = await client.call_tool(name, args)
    assert not result.is_error
    payload = json.loads(result.content[0].text)
    if name == "download_recipe_bulk_export":
        assert base64.b64decode(payload["dataBase64"]) == b"PKexport"
        assert len(calls) == 2 and "private-token" not in result.content[0].text
    elif name == "import_recipes_from_urls":
        assert payload == {"reportId": ID, "status": "accepted", "atomic": False}
    elif name == "delete_recipes_bulk":
        assert payload == {
            "status": "completed",
            "atomic": False,
            "perItemOutcomes": "notReported",
            "providerResult": None,
        }
    elif name == "export_recipes_bulk":
        assert payload == {"status": "accepted", "atomic": False, "providerResult": None}
    elif name == "update_recipe_metadata_batch":
        assert payload["items"][0]["status"] == "updated"
        assert payload["items"][0]["recipe"]["future"] == [False]
        assert [(call.method, call.url.path) for call in calls] == [
            ("GET", "/api/recipes/soup"),
            ("GET", "/api/recipes/" + ID),
            ("PATCH", "/api/recipes/" + ID),
        ]
    else:
        assert payload == response
    if path.endswith("/stream"):
        assert progress_messages == ["Mealie import in progress."]


@pytest.mark.parametrize("name", [case[0] for case in CASES])
async def test_recipe_jobs_mcp_rejects_unknown_arguments_before_network(name):
    args = next(case[1] for case in CASES if case[0] == name)
    calls = []
    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(
            settings, transport=httpx.MockTransport(lambda request: calls.append(request))
        ),
    )
    async with Client(server) as client:
        result = await client.call_tool(name, {**args, "unexpected": True}, raise_on_error=False)
    assert result.is_error and calls == []


@pytest.mark.parametrize("name", ["import_recipe_with_ai", "import_recipe_with_ai_with_progress"])
async def test_recipe_jobs_unconfigured_native_ai_failure_is_safe_without_retries(name):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(400, text="private recipe signed-url secret")

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        result = await client.call_tool(name, {"content": "private recipe"}, raise_on_error=False)
    assert result.is_error and len(calls) == 1
    assert result.content[0].text == "Mealie API error 400."


async def test_metadata_batch_mcp_rejects_slug_and_uuid_aliases_before_any_patch():
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(
            200,
            json={
                "id": ID,
                "slug": "soup",
                "updatedAt": "snapshot",
                "settings": {"locked": False, "future": 1},
            },
        )

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        result = await client.call_tool(
            "update_recipe_metadata_batch",
            {
                "items": [
                    {"slug": "soup", "expectedUpdatedAt": "snapshot", "settings": {"locked": True}},
                    {"slug": ID, "expectedUpdatedAt": "snapshot", "settings": {"public": True}},
                ]
            },
            raise_on_error=False,
        )
    assert result.is_error
    assert "same recipe" in result.content[0].text
    assert calls == [("GET", "/api/recipes/soup"), ("GET", "/api/recipes/" + ID)]
