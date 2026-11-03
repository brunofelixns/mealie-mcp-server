import base64
import json
from io import BytesIO
from zipfile import ZipFile

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError


def settings():
    return load_settings({"MEALIE_BASE_URL": "https://mealie.test", "MEALIE_API_KEY": "secret"})


async def test_binary_export_is_authenticated_bounded_and_has_metadata():
    def respond(request):
        assert request.headers["authorization"] == "Bearer secret"
        assert request.url.params["template_name"] == "json"
        return httpx.Response(
            200,
            content=b'{"name":"Soup"}',
            headers={
                "content-type": "application/json",
                "content-disposition": 'attachment; filename="soup.json"',
            },
        )

    from mealie_mcp_server.models.inputs.recipe_io import ExportRecipeInput
    from mealie_mcp_server.services.recipe_io import export_recipe

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        result = await export_recipe(client, ExportRecipeInput(slug="soup", templateName="json"))
    assert result == {
        "filename": "soup.json",
        "mediaType": "application/json",
        "size": 15,
        "dataBase64": base64.b64encode(b'{"name":"Soup"}').decode(),
    }


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=b"abcd"),
        httpx.Response(200, content=b"a", headers={"content-length": "100"}),
    ],
)
async def test_binary_response_limit(response):
    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: response)
    ) as client:
        with pytest.raises(MealieTransportError, match="limit"):
            await client.get_binary("/api/recipes/soup/exports", max_bytes=3)


async def test_binary_cross_origin_redirect_is_rejected_without_forwarding_credentials():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.test/signed?secret=value"})

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieApiError, match="outside"):
            await client.get_binary("/api/recipes/soup/exports")
    assert len(calls) == 1


async def test_import_url_preserves_explicit_false_and_returns_native_created_slug():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_url

    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.path == "/api/recipes/create/url"
        assert json.loads(request.content) == {
            "url": "https://recipes.test/soup",
            "includeTags": False,
        }
        return httpx.Response(201, json="created-soup")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        assert (
            await import_recipe_from_url(
                client, ImportRecipeFromUrlInput(url="https://recipes.test/soup", includeTags=False)
            )
            == "created-soup"
        )
    assert len(calls) == 1


async def test_upload_asset_uses_provider_multipart_fields():
    from mealie_mcp_server.models.inputs.recipe_io import UploadRecipeAssetInput
    from mealie_mcp_server.services.recipe_io import upload_recipe_asset

    def respond(request):
        assert request.url.path == "/api/recipes/soup/assets"
        for field in [
            b'name="name"',
            b'name="icon"',
            b'name="extension"',
            b'name="file"',
            b"asset.pdf",
            b"%PDF",
        ]:
            assert field in request.content
        return httpx.Response(
            200,
            json={"name": "Guide", "icon": "mdi-file", "fileName": "guide.pdf", "unknown": False},
        )

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        result = await upload_recipe_asset(
            client,
            UploadRecipeAssetInput(
                slug="soup", name="Guide", icon="mdi-file", extension="pdf", fileBase64="JVBERg=="
            ),
        )
    assert result["unknown"] is False


@pytest.mark.parametrize(
    "arguments",
    [
        {"fileBase64": "%%%"},
        {"fileBase64": ""},
        {"extension": "../pdf"},
        {"slug": "../soup"},
    ],
)
async def test_invalid_asset_never_sends_request(arguments):
    from mealie_mcp_server.models.inputs.recipe_io import UploadRecipeAssetInput
    from mealie_mcp_server.services.recipe_io import upload_recipe_asset

    def respond(_):
        pytest.fail("Invalid upload reached Mealie")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError):
            await upload_recipe_asset(
                client,
                UploadRecipeAssetInput.model_validate(
                    {
                        "slug": "soup",
                        "name": "Guide",
                        "icon": "mdi-file",
                        "extension": "pdf",
                        "fileBase64": "JVBERg==",
                        **arguments,
                    }
                ),
            )


async def test_import_timeout_is_confidential_and_never_retried():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_url

    calls = []

    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout("https://private.test?secret=key")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieTransportError, match="Write outcome may be unknown") as error:
            await import_recipe_from_url(
                client, ImportRecipeFromUrlInput(url="https://recipes.test/soup")
            )
    assert "private" not in str(error.value) and len(calls) == 1


async def test_html_import_preserves_source_null_and_options():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromHtmlOrJsonInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_html_or_json

    def respond(request):
        assert request.url.path == "/api/recipes/create/html-or-json"
        assert json.loads(request.content) == {
            "data": '{"name":"Soup"}',
            "url": None,
            "includeCategories": False,
        }
        return httpx.Response(201, json="soup")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        assert (
            await import_recipe_from_html_or_json(
                client,
                ImportRecipeFromHtmlOrJsonInput(
                    data='{"name":"Soup"}', url=None, includeCategories=False
                ),
            )
            == "soup"
        )


async def test_zip_import_uses_archive_multipart_without_creating_host_files():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromZipInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_zip

    archive = BytesIO()
    with ZipFile(archive, "w") as file:
        file.writestr("recipe.json", '{"name":"Soup"}')

    def respond(request):
        assert request.url.path == "/api/recipes/create/zip"
        assert b'name="archive"; filename="recipe.zip"' in request.content
        assert archive.getvalue() in request.content
        return httpx.Response(201, json="soup")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        assert (
            await import_recipe_from_zip(
                client,
                ImportRecipeFromZipInput(
                    archiveBase64=base64.b64encode(archive.getvalue()).decode()
                ),
            )
            == "soup"
        )


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/drive", "windows\\escape"])
async def test_unsafe_zip_never_reaches_provider(name):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromZipInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_zip

    archive = BytesIO()
    with ZipFile(archive, "w") as file:
        file.writestr(name, "secret")
    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: pytest.fail("unsafe ZIP sent"))
    ) as client:
        with pytest.raises(ValueError, match="unsafe"):
            await import_recipe_from_zip(
                client,
                ImportRecipeFromZipInput(
                    archiveBase64=base64.b64encode(archive.getvalue()).decode()
                ),
            )


@pytest.mark.parametrize("result", [None, {}, [], 0, ""])
async def test_invalid_import_response_is_safe_and_not_retried(result):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_url

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(201, json=result)

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieTransportError):
            await import_recipe_from_url(
                client, ImportRecipeFromUrlInput(url="https://recipes.test/soup")
            )
    assert len(calls) == 1


async def test_binary_refuses_compression_to_prevent_unbounded_decompression():
    async with MealieClient(
        settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, content=b"abc", headers={"content-encoding": "identity"}
            )
        ),
    ) as client:
        assert (await client.get_binary("/api/recipes/soup/exports")).content == b"abc"

    def respond(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200, stream=BinaryStream([b"invalid"]), headers={"content-encoding": "gzip"}
        )

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieTransportError, match="encoding"):
            await client.get_binary("/api/recipes/soup/exports")


class BinaryStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


async def test_streamed_binary_limit_is_checked_without_content_length():
    async with MealieClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, stream=BinaryStream([b"ab", b"cd"]))
        ),
    ) as client:
        with pytest.raises(MealieTransportError, match="limit"):
            await client.get_binary("/api/recipes/soup/exports", max_bytes=3)


async def test_binary_same_origin_redirect_preserves_authentication_and_base_subpath():
    configured = load_settings(
        {"MEALIE_BASE_URL": "https://mealie.test/proxy", "MEALIE_API_KEY": "secret"}
    )
    calls = []

    def respond(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer secret"
        if len(calls) == 1:
            assert request.url.path == "/proxy/api/recipes/soup/exports"
            return httpx.Response(302, headers={"location": "/proxy/api/export/file"})
        return httpx.Response(200, content=b"ZIP")

    async with MealieClient(configured, transport=httpx.MockTransport(respond)) as client:
        assert (await client.get_binary("/api/recipes/soup/exports")).content == b"ZIP"
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload,limit,expected",
    [
        ("YWJj", 3, b"abc"),
        ("YWJjZA==", 3, None),
        ("YWJjZA==", 1, None),
        ("", 3, None),
        ("%%%%", 3, None),
    ],
)
def test_base64_decoded_size_boundary(payload, limit, expected):
    from mealie_mcp_server.services.recipe_io import decode_file

    if expected is None:
        with pytest.raises(ValueError):
            decode_file(payload, limit)
    else:
        assert decode_file(payload, limit) == expected


@pytest.mark.parametrize("length", ["not-a-number", "-1"])
async def test_binary_invalid_content_length_is_confidential(length):
    async with MealieClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=b"secret", headers={"content-length": length})
        ),
    ) as client:
        with pytest.raises(MealieTransportError) as error:
            await client.get_binary("/api/recipes/soup/exports")
    assert "secret" not in str(error.value)


async def test_binary_timeout_is_confidential_and_not_retried():
    calls = []

    def respond(request):
        calls.append(request)
        raise httpx.ReadTimeout("https://mealie.test?signature=secret")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieTransportError, match="download timed out") as error:
            await client.get_binary("/api/recipes/soup/exports")
    assert len(calls) == 1 and "signature" not in str(error.value)


async def test_binary_non_success_does_not_read_or_expose_provider_body():
    async with MealieClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(403, stream=BinaryStream([b"private recipe body"]))
        ),
    ) as client:
        with pytest.raises(MealieApiError) as error:
            await client.get_binary("/api/recipes/soup/exports")
    assert error.value.status == 403 and not error.value.body


@pytest.mark.parametrize("result", [{}, {"json": [], "zip": "zip"}, {"json": [1], "zip": []}, None])
async def test_invalid_export_formats_response(result):
    from mealie_mcp_server.services.recipe_io import get_recipe_export_formats

    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=result))
    ) as client:
        with pytest.raises(MealieTransportError):
            await get_recipe_export_formats(client)


async def test_html_import_utf8_byte_limit_precedes_provider_request():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromHtmlOrJsonInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_html_or_json

    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: pytest.fail("oversize sent"))
    ) as client:
        with pytest.raises(ValueError, match="size limit"):
            await import_recipe_from_html_or_json(
                client, ImportRecipeFromHtmlOrJsonInput(data="é" * (1024 * 1024 + 1))
            )


@pytest.mark.parametrize("member_count", [0, 1001])
async def test_zip_member_limit_precedes_provider_request(member_count):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromZipInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_zip

    archive = BytesIO()
    with ZipFile(archive, "w") as file:
        for index in range(member_count):
            file.writestr(f"{index}.txt", "")
    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: pytest.fail("oversize sent"))
    ) as client:
        with pytest.raises(ValueError, match="member limit"):
            await import_recipe_from_zip(
                client,
                ImportRecipeFromZipInput(
                    archiveBase64=base64.b64encode(archive.getvalue()).decode()
                ),
            )


async def test_malformed_zip_precedes_provider_request():
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromZipInput
    from mealie_mcp_server.services.recipe_io import import_recipe_from_zip

    async with MealieClient(
        settings(), transport=httpx.MockTransport(lambda _: pytest.fail("invalid sent"))
    ) as client:
        with pytest.raises(ValueError, match="valid ZIP"):
            await import_recipe_from_zip(client, ImportRecipeFromZipInput(archiveBase64="YWJj"))


@pytest.mark.parametrize("filename", ["../../secret", "C:\\private", "..", "x" * 256])
async def test_unsafe_export_filename_is_replaced(filename):
    from mealie_mcp_server.models.inputs.recipe_io import ExportRecipeInput
    from mealie_mcp_server.services.recipe_io import export_recipe

    async with MealieClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"{}",
                headers={"content-disposition": f'attachment; filename="{filename}"'},
            )
        ),
    ) as client:
        result = await export_recipe(client, ExportRecipeInput(slug="soup", templateName="json"))
    assert result["filename"] == "recipe-export"


@pytest.mark.parametrize(
    "url",
    [
        "file:///secret",
        "https://user:secret@recipes.test",
        "https://recipes.test/#fragment",
        "https://recipes.test:invalid",
        "https://recipes.test/\n",
    ],
)
def test_import_url_is_strict_and_safe(url):
    from mealie_mcp_server.models.inputs.recipe_io import ImportRecipeFromUrlInput

    with pytest.raises(ValueError):
        ImportRecipeFromUrlInput(url=url)


async def test_asset_invalid_provider_response_is_rejected_without_replaying_write():
    from mealie_mcp_server.models.inputs.recipe_io import CreateRecipeAssetFromUrlInput
    from mealie_mcp_server.services.recipe_io import create_recipe_asset_from_url

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"secret": "private file body"})

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(MealieTransportError, match="invalid asset response") as error:
            await create_recipe_asset_from_url(
                client,
                CreateRecipeAssetFromUrlInput(slug="soup", url="https://recipes.test/image.png"),
            )
    assert len(calls) == 1 and "private" not in str(error.value)


async def test_binary_does_not_buffer_redirect_bodies():
    class Unreadable(httpx.AsyncByteStream):
        async def __aiter__(self):
            pytest.fail("Redirect body must not be buffered")
            yield b"unreachable"

    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                302, stream=Unreadable(), headers={"location": "/api/export/file"}
            )
        return httpx.Response(200, content=b"data")

    async with MealieClient(settings(), transport=httpx.MockTransport(respond)) as client:
        assert (await client.get_binary("/api/recipes/soup/exports")).content == b"data"
