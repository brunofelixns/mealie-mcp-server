import base64
import re

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment
from mealie_mcp_server.models.common import JsonObject
from mealie_mcp_server.support.safe_download import download_bounded
from mealie_mcp_server.support.strings import JS_WHITESPACE, trim

RECIPE_IMAGE_MAX_BYTES = 10 * 1024 * 1024


def decode_recipe_image(payload: str, extension: str | None = None) -> tuple[bytes, str]:
    whitespace = "[" + re.escape(JS_WHITESPACE) + "]"
    clean = re.sub(
        r"^" + whitespace + r"*data:[^,]*;base64,", "", payload, count=1, flags=re.IGNORECASE
    )
    clean = clean.translate(dict.fromkeys(map(ord, JS_WHITESPACE)))
    if not clean or not re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", clean):
        raise ValueError("imageBase64 is not valid base64-encoded data.")
    clean = clean.rstrip("=")
    if len(clean) % 4 == 1:
        clean = clean[:-1]
    data = base64.urlsafe_b64decode(clean + "=" * (-len(clean) % 4))
    if not data:
        raise ValueError("imageBase64 decoded to an empty image.")
    detected = validate_image_bytes(data)
    if extension is not None:
        normalized = trim(extension).lower().removeprefix(".")
        if normalized == "jpeg":
            normalized = "jpg"
        if normalized != detected:
            raise ValueError(
                f'extension "{extension}" does not match the image data, which is {detected}.'
            )
    return data, detected


def validate_image_bytes(data: bytes) -> str:
    if len(data) > RECIPE_IMAGE_MAX_BYTES:
        raise ValueError("Image exceeds the 10 MB limit.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"GIF8"):
        return "gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    raise ValueError("Unsupported image data: expected PNG, JPEG, WebP, or GIF.")


async def upload_recipe_image(
    client: MealieClient, slug: str, data: bytes, extension: str
) -> JsonValue:
    return await client.request(
        "PUT",
        "/api/recipes/" + encode_path_segment(slug, "slug") + "/image",
        data={"extension": extension},
        files={"image": (f"image.{extension}", data, "application/octet-stream")},
    )


async def set_recipe_image(
    client: MealieClient, slug: str, payload: str | None, extension: str | None = None
) -> JsonValue:
    if payload is None:
        return await client.request(
            "DELETE", "/api/recipes/" + encode_path_segment(slug, "slug") + "/image"
        )
    data, detected = decode_recipe_image(payload, extension)
    return await upload_recipe_image(client, slug, data, detected)


async def set_recipe_image_from_file(
    client: MealieClient, slug: str, file: JsonObject
) -> JsonValue:
    url = file["download_url"]
    assert isinstance(url, str)
    data = await download_bounded(url, RECIPE_IMAGE_MAX_BYTES)
    if not data:
        raise ValueError("Downloaded file is empty.")
    return await upload_recipe_image(client, slug, data, validate_image_bytes(data))
