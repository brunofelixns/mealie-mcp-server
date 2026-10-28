import base64

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.support import recipe_image

PNG = b"\x89PNG\r\n\x1a\n\x01\x02\x03"
JPG = b"\xff\xd8\xff\xe0\x01\x02"
GIF = b"GIF89a...."
WEBP = b"RIFF\x01\0\0\0WEBPVP8 "
SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("data", "extension"), [(PNG, "png"), (JPG, "jpg"), (GIF, "gif"), (WEBP, "webp")]
)
def test_detects_image_from_magic_bytes(data, extension):
    assert recipe_image.decode_recipe_image(base64.b64encode(data).decode()) == (data, extension)


def test_data_uri_ecmascript_whitespace_urlsafe_base64_and_jpeg_alias():
    encoded = base64.urlsafe_b64encode(JPG).decode().rstrip("=")
    assert recipe_image.decode_recipe_image(
        "\ufeffdata:image/jpeg;base64,\n" + encoded, ".JPEG"
    ) == (JPG, "jpg")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "not valid base64"),
        ("!bad", "not valid base64"),
        ("A", "empty image"),
        ("iVBO", "Unsupported"),
        (base64.b64encode(b"hello").decode(), "Unsupported"),
        ("\x1c" + base64.b64encode(PNG).decode(), "not valid base64"),
    ],
)
def test_invalid_image_data_rejected(payload, message):
    with pytest.raises(ValueError, match=message):
        recipe_image.decode_recipe_image(payload)


def test_ten_mib_boundary_and_extension_mismatch():
    at_limit = PNG + b"\0" * (recipe_image.RECIPE_IMAGE_MAX_BYTES - len(PNG))
    assert len(recipe_image.decode_recipe_image(base64.b64encode(at_limit).decode())[0]) == len(
        at_limit
    )
    with pytest.raises(ValueError, match="10 MB limit"):
        recipe_image.decode_recipe_image(base64.b64encode(at_limit + b"x").decode())
    with pytest.raises(ValueError, match="does not match"):
        recipe_image.decode_recipe_image(base64.b64encode(PNG).decode(), "jpg")


async def test_file_hints_are_not_authority_and_invalid_bytes_never_upload(monkeypatch):
    calls = []
    downloads = []

    async def download(url, max_bytes):
        downloads.append((url, max_bytes))
        return PNG

    monkeypatch.setattr(recipe_image, "download_bounded", download, raising=False)

    def handle(request):
        calls.append(request)
        assert request.method == "PUT" and request.url.path == "/api/recipes/soup/image"
        assert PNG in request.content and b"image.png" in request.content
        return httpx.Response(200, json={"image": "v1"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await recipe_image.set_recipe_image_from_file(
            client,
            "soup",
            {
                "download_url": "https://files.test/x",
                "file_id": "file-1",
                "mime_type": "image/jpeg",
                "file_name": "wrong.gif",
            },
        )
    assert result == {"image": "v1"}
    assert len(calls) == 1 and downloads == [("https://files.test/x", 10 * 1024 * 1024)]


async def test_null_image_deletes_once_and_validation_happens_before_http():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"message": "deleted"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await recipe_image.set_recipe_image(client, "soup", "invalid!!")
        result = await recipe_image.set_recipe_image(client, "soup", None)
    assert result == {"message": "deleted"} and len(calls) == 1
    assert calls[0].method == "DELETE"
