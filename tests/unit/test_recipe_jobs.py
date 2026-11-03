"""Native job boundaries, bounded SSE and explicit per-item metadata outcomes."""

import asyncio
import json

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError

SETTINGS = load_settings(
    {"MEALIE_BASE_URL": "http://mealie.test/proxy", "MEALIE_API_KEY": "secret"}
)
ID = "11111111-1111-4111-8111-111111111111"


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            if isinstance(chunk, BaseException):
                raise chunk
            yield chunk


async def test_native_ai_repeated_multipart_images_and_false():
    from mealie_mcp_server.models.inputs.recipe_jobs import ImportRecipeWithAiInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_with_ai

    observed = []

    def handle(request):
        observed.append(request)
        assert request.url.path == "/proxy/api/recipes/create/ai"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert request.content.count(b'name="images"') == 2
        assert b'name="createNewOrganizers"\r\n\r\nfalse' in request.content
        assert b'name="content"\r\n\r\nprivate content' in request.content
        return httpx.Response(201, json="soup")

    request = ImportRecipeWithAiInput.model_validate(
        {
            "content": "private content",
            "createNewOrganizers": False,
            "images": [
                {"filename": "a.png", "mediaType": "image/png", "dataBase64": "aGk="},
                {"filename": "b.jpg", "mediaType": "image/jpeg", "dataBase64": "aGk="},
            ],
        }
    )
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await import_recipe_with_ai(client, request) == "soup"
    assert len(observed) == 1


async def test_stream_split_crlf_and_utf8_reports_safe_progress():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_from_url_with_progress

    raw = (
        'event: progress\r\ndata: {"message":"private café secret"}\r\n\r\n'
        'event: done\r\ndata: {"slug":"soup"}\r\n\r\n'
    ).encode()
    progress = []

    async def report(count):
        progress.append(count)

    def handle(request):
        assert json.loads(request.content) == {
            "url": "https://recipe.test/soup",
            "includeTags": False,
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=Chunks([raw[i : i + 1] for i in range(len(raw))]),
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await import_recipe_from_url_with_progress(
            client,
            ImportRecipeFromUrlInput(url="https://recipe.test/soup", includeTags=False),
            report,
        )
    assert result == "soup"
    assert progress == [1]


@pytest.mark.parametrize(
    "chunks",
    [
        [b'event: progress\ndata: {"message":"secret private recipe"}\n\n'],
        [b'event: error\ndata: {"message":"secret signed-url"}\n\n'],
        [b'event: done\ndata: {"bad":"secret"}\n\n'],
        [b"event: progress\ndata: not-json-secret\n\n"],
        [httpx.ReadTimeout("secret signed-url")],
        [httpx.ReadError("private recipe")],
    ],
)
async def test_interrupted_or_invalid_stream_is_confidential_and_never_retried(chunks):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_from_url_with_progress

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Chunks(chunks)
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError) as caught:
            await import_recipe_from_url_with_progress(
                client, ImportRecipeFromUrlInput(url="https://recipe.test")
            )
    assert "secret" not in str(caught.value) and "private" not in str(caught.value)
    assert "unknown" in str(caught.value).lower()
    assert len(requests) == 1


@pytest.mark.parametrize(
    ("raw", "limits"),
    [
        (b":" + b"x" * 21, {"max_line_bytes": 20}),
        (b": ping\n\n" * 20, {"max_bytes": 20}),
        (b"data: {}\n\n" * 3, {"max_events": 2}),
    ],
)
async def test_stream_limits_bound_raw_bytes_lines_and_event_count(raw, limits):
    def handle(request):
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Chunks([raw])
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError, match="limit"):
            async for _ in client.stream_events(
                "/api/recipes/create/url/stream", json={}, **limits
            ):
                pass


async def test_stream_cancellation_closes_without_replaying():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_from_url_with_progress

    calls = []
    closed = []

    class Blocking(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'event: progress\ndata: {"message":"wait"}\n\n'
            await asyncio.Event().wait()

        async def aclose(self):
            closed.append(True)

    def handle(request):
        calls.append(request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=Blocking())

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(
            import_recipe_from_url_with_progress(
                client, ImportRecipeFromUrlInput(url="https://recipe.test")
            )
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(calls) == 1 and closed == [True]


@pytest.mark.parametrize(
    "location", ["https://evil.test/token", "/proxy/api/recipes/create/url/stream"]
)
async def test_stream_never_replays_redirected_post(location):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(307, headers={"location": location})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError):
            async for _ in client.stream_events("/api/recipes/create/url/stream", json={}):
                pass
    assert len(calls) == 1


@pytest.mark.parametrize("status", [400, 401, 403, 422, 500])
async def test_stream_http_errors_redact_provider_body(status):
    async with MealieClient(
        SETTINGS,
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text="secret private body")),
    ) as client:
        with pytest.raises(MealieApiError) as caught:
            async for _ in client.stream_events("/api/recipes/create/url/stream", json={}):
                pass
    assert caught.value.status == status
    assert "secret" not in str(caught.value)


async def test_metadata_batch_preserves_fields_rejects_stale_item_and_order():
    from mealie_mcp_server.models.inputs.recipe_jobs import UpdateRecipeMetadataBatchInput
    from mealie_mcp_server.services.recipe_jobs import update_recipe_metadata_batch

    writes = []
    identities = {"soup": ID, "stale": "22222222-2222-4222-8222-222222222222"}

    def handle(request):
        target = request.url.path.rsplit("/", 1)[-1]
        slug = next((slug for slug, identity in identities.items() if identity == target), target)
        original = {
            "id": identities[slug],
            "slug": slug,
            "updatedAt": "fresh",
            "settings": {"locked": False, "future": 1},
            "future": [1],
        }
        if request.method == "GET":
            return httpx.Response(200, json=original)
        patch = json.loads(request.content)
        writes.append((target, patch))
        return httpx.Response(200, json={**original, **patch})

    request = UpdateRecipeMetadataBatchInput.model_validate(
        {
            "items": [
                {"slug": "soup", "expectedUpdatedAt": "fresh", "settings": {"locked": True}},
                {"slug": "stale", "expectedUpdatedAt": "old", "name": "new"},
            ],
            "concurrency": 2,
        }
    )
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, request)
    assert [item["status"] for item in result["items"]] == ["updated", "rejected"]
    assert writes == [(ID, {"settings": {"locked": True, "future": 1}})]
    assert result["items"][0]["recipe"]["future"] == [1]


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"images": [{"filename": "../bad.png", "mediaType": "image/png", "dataBase64": "aGk="}]},
        {
            "content": "hi",
            "images": [{"filename": "a.png", "mediaType": "image/png", "dataBase64": "%%%"}],
        },
    ],
)
async def test_invalid_ai_upload_is_rejected_before_any_network(args):
    from mealie_mcp_server.models.inputs.recipe_jobs import ImportRecipeWithAiInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_with_ai

    calls = []
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as client:
        with pytest.raises((ValidationError, ValueError)):
            await import_recipe_with_ai(client, ImportRecipeWithAiInput.model_validate(args))
    assert calls == []


@pytest.mark.parametrize("value", ["not-an-id", "00000000-0000-0000-0000-000000000000"])
def test_report_and_export_ids_are_strict_uuid4(value):
    from mealie_mcp_server.models.inputs.recipe_jobs import GetRecipeImportReportInput

    with pytest.raises(ValidationError):
        GetRecipeImportReportInput(reportId=value)


@pytest.mark.parametrize("slugs", [["soup", "soup"], ["soup", " soup "]])
def test_batch_rejects_duplicate_target_before_any_write(slugs):
    from mealie_mcp_server.models.inputs.recipe_jobs import UpdateRecipeMetadataBatchInput

    with pytest.raises(ValidationError):
        UpdateRecipeMetadataBatchInput.model_validate(
            {
                "items": [
                    {"slug": slug, "expectedUpdatedAt": "fresh", "prepTime": "PT1M"}
                    for slug in slugs
                ]
            }
        )


@pytest.mark.parametrize("field,value", [("filename", "bad\r\n.png"), ("mediaType", "text/plain")])
def test_ai_images_reject_unsafe_filename_and_nonimage_media(field, value):
    from mealie_mcp_server.models.inputs.recipe_jobs import AiRecipeImage

    with pytest.raises(ValidationError):
        AiRecipeImage.model_validate(
            {"filename": "safe.png", "mediaType": "image/png", "dataBase64": "aGk=", field: value}
        )


async def test_metadata_batch_concurrency_is_bounded_and_outcomes_are_explicit():
    from mealie_mcp_server.models.inputs.recipe_jobs import UpdateRecipeMetadataBatchInput
    from mealie_mcp_server.services.recipe_jobs import update_recipe_metadata_batch

    active = 0
    peak = 0
    writes = []
    identities = {
        slug: f"{index:08d}-1111-4111-8111-111111111111"
        for index, slug in enumerate(["timeout", "denied", "server", "verification"], start=1)
    }

    async def handle(request):
        nonlocal active, peak
        target = request.url.path.rsplit("/", 1)[-1]
        slug = next((slug for slug, identity in identities.items() if identity == target), target)
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.001)
            if request.method == "GET":
                return httpx.Response(
                    200, json={"id": identities[slug], "updatedAt": "fresh", "slug": slug}
                )
            writes.append(slug)
            if slug == "timeout":
                raise httpx.ReadTimeout("secret private body")
            if slug == "denied":
                return httpx.Response(403, text="secret")
            if slug == "server":
                return httpx.Response(500, text="secret")
            return httpx.Response(200, json={"slug": slug, "prepTime": "wrong"})
        finally:
            active -= 1

    request = UpdateRecipeMetadataBatchInput.model_validate(
        {
            "items": [
                {"slug": slug, "expectedUpdatedAt": "fresh", "prepTime": "PT1M"}
                for slug in ["timeout", "denied", "server", "verification"]
            ],
            "concurrency": 2,
        }
    )
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await update_recipe_metadata_batch(client, request)
    assert [item["status"] for item in result["items"]] == [
        "unknown",
        "failed",
        "unknown",
        "unknown",
    ]
    assert sorted(writes) == ["denied", "server", "timeout", "verification"] and peak == 2
    assert "secret" not in json.dumps(result) and "private" not in json.dumps(result)


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "application/json"},
        {"content-type": "text/event-stream", "content-encoding": "gzip"},
    ],
)
async def test_stream_rejects_non_sse_and_compressed_responses(headers):
    async with MealieClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, headers=headers, stream=Chunks([]))
        ),
    ) as client:
        with pytest.raises(MealieTransportError, match="unknown"):
            async for _ in client.stream_events("/api/recipes/create/url/stream", json={}):
                pass


async def test_stream_ignores_sse_ids_retry_comments_and_requires_event_terminator():
    raw = b': keepalive\r\rretry: 1\rid: hidden\revent: done\rdata: {"slug":"soup"}\r\r'
    async with MealieClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=Chunks([raw])
            )
        ),
    ) as client:
        events = [
            event async for event in client.stream_events("/api/recipes/create/url/stream", json={})
        ]
    assert [(event.event, event.data) for event in events] == [("done", {"slug": "soup"})]


@pytest.mark.parametrize(
    "raw",
    [
        b"event: \xff\ndata: {}\n\n",
        b"event: done\ndata: NaN\n\n",
        b"event: unknown\ndata: {}\n\n",
        b"event: done\ndata: []\n\n",
        b'event: done\ndata: {"slug":"soup"}',
    ],
)
async def test_invalid_sse_or_unterminated_completion_is_uncertain(raw):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_from_url_with_progress

    async with MealieClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=Chunks([raw])
            )
        ),
    ) as client:
        with pytest.raises(MealieTransportError, match="unknown"):
            await import_recipe_from_url_with_progress(
                client, ImportRecipeFromUrlInput(url="https://recipes.test")
            )


@pytest.mark.parametrize(
    "operation,response",
    [
        ("preview", []),
        ("bulk", {}),
        ("bulk", {"reportId": "not-uuid"}),
        ("reports", {}),
        ("reports", [{"category": "backup"}]),
        ("report", {"category": "backup"}),
        ("exports", {}),
        ("exports", [{}]),
        ("download", {"fileToken": ""}),
        ("download", {}),
        ("purge", []),
    ],
)
async def test_native_job_results_are_validated(operation, response):
    from mealie_mcp_server.models.inputs import recipe_jobs as m
    from mealie_mcp_server.services import recipe_jobs as jobs

    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=response))
    ) as client:
        with pytest.raises(MealieTransportError):
            match operation:
                case "preview":
                    await jobs.preview_recipe_from_url(
                        client, m.PreviewRecipeFromUrlInput(url="https://recipes.test")
                    )
                case "bulk":
                    await jobs.import_recipes_from_urls(
                        client,
                        m.ImportRecipesFromUrlsInput(
                            imports=[m.BulkRecipeUrl(url="https://recipes.test")]
                        ),
                    )
                case "reports":
                    await jobs.get_recipe_import_reports(client)
                case "report":
                    await jobs.get_recipe_import_report(
                        client, m.GetRecipeImportReportInput(reportId=ID)
                    )
                case "exports":
                    await jobs.get_recipe_bulk_exports(client)
                case "download":
                    await jobs.download_recipe_bulk_export(
                        client, m.DownloadRecipeBulkExportInput(exportId=ID)
                    )
                case "purge":
                    await jobs.purge_recipe_bulk_exports(client)


@pytest.mark.parametrize("kind", ["ai", "html"])
async def test_import_limits_count_utf8_bytes_before_network(kind):
    from mealie_mcp_server.models.inputs.recipe_io import (
        IMPORT_MAX_BYTES,
        ImportRecipeFromHtmlOrJsonInput,
    )
    from mealie_mcp_server.models.inputs.recipe_jobs import ImportRecipeWithAiInput
    from mealie_mcp_server.services import recipe_jobs as jobs

    content = "é" * (IMPORT_MAX_BYTES // 2 + 1)
    calls = []
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as client:
        with pytest.raises(ValueError, match="size limit"):
            if kind == "ai":
                await jobs.import_recipe_with_ai(client, ImportRecipeWithAiInput(content=content))
            else:
                await jobs.import_recipe_from_html_or_json_with_progress(
                    client, ImportRecipeFromHtmlOrJsonInput(data=content)
                )
    assert calls == []


async def test_combined_ai_image_limit_is_checked_before_upload(monkeypatch):
    from mealie_mcp_server.models.inputs.recipe_jobs import ImportRecipeWithAiInput
    from mealie_mcp_server.services import recipe_jobs as jobs

    monkeypatch.setattr(jobs, "AI_TOTAL_IMAGE_MAX_BYTES", 3)
    request = ImportRecipeWithAiInput.model_validate(
        {
            "images": [
                {"filename": name, "mediaType": "image/png", "dataBase64": "aGk="}
                for name in ["a.png", "b.png"]
            ]
        }
    )
    calls = []
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as client:
        with pytest.raises(ValueError, match="combined size limit"):
            await jobs.import_recipe_with_ai(client, request)
    assert calls == []


async def test_empty_bulk_export_download_fails_without_returning_token():
    from mealie_mcp_server.models.inputs.recipe_jobs import DownloadRecipeBulkExportInput
    from mealie_mcp_server.services.recipe_jobs import download_recipe_bulk_export

    def handle(request):
        if (
            request.url.path.endswith("/download")
            and request.url.path != "/proxy/api/utils/download"
        ):
            return httpx.Response(200, json={"fileToken": "private-token"})
        return httpx.Response(200, content=b"")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError, match="empty bulk export") as caught:
            await download_recipe_bulk_export(client, DownloadRecipeBulkExportInput(exportId=ID))
    assert "private-token" not in str(caught.value)


@pytest.mark.parametrize(
    "slug", ["https://signed.test/token", "private\ncontent", " " * 10, "x" * 256]
)
async def test_ai_import_rejects_invalid_completion_slug_without_exposing_it(slug):
    from mealie_mcp_server.models.inputs.recipe_jobs import ImportRecipeWithAiInput
    from mealie_mcp_server.services.recipe_jobs import import_recipe_with_ai

    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: httpx.Response(201, json=slug))
    ) as client:
        with pytest.raises(MealieTransportError, match="unknown") as caught:
            await import_recipe_with_ai(client, ImportRecipeWithAiInput(content="soup"))
    assert slug not in str(caught.value)


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("private"), httpx.ConnectError("secret")])
@pytest.mark.parametrize("operation", ["ai", "bulk"])
async def test_native_import_transport_failure_never_retries(failure, operation):
    from mealie_mcp_server.models.inputs.recipe_jobs import (
        BulkRecipeUrl,
        ImportRecipesFromUrlsInput,
        ImportRecipeWithAiInput,
    )
    from mealie_mcp_server.services.recipe_jobs import (
        import_recipe_with_ai,
        import_recipes_from_urls,
    )

    calls = []

    def handle(request):
        calls.append(request)
        raise failure

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError, match="unknown"):
            if operation == "ai":
                await import_recipe_with_ai(client, ImportRecipeWithAiInput(content="soup"))
            else:
                await import_recipes_from_urls(
                    client,
                    ImportRecipesFromUrlsInput(imports=[BulkRecipeUrl(url="https://recipes.test")]),
                )
    assert len(calls) == 1


async def test_stream_requires_open_client_and_strict_relative_path_and_limits():
    client = MealieClient(SETTINGS)
    with pytest.raises(RuntimeError, match="context"):
        async for _ in client.stream_events("/api/recipes/create/url/stream"):
            pass
    async with client:
        for path, kwargs in [
            ("https://evil.test", {}),
            ("/api/ok", {"max_bytes": 0}),
            ("/api/ok", {"json": {}, "files": {}}),
        ]:
            with pytest.raises(ValueError):
                async for _ in client.stream_events(path, **kwargs):
                    pass
