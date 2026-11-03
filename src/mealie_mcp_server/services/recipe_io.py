"""Native Mealie IO. Imports create recipes and may create provider organizers."""

import base64
import binascii
from email.message import Message
from io import BytesIO
from pathlib import PurePosixPath
from typing import cast
from zipfile import BadZipFile, ZipFile

from pydantic import JsonValue

from mealie_mcp_server.mealie.client import MealieClient, encode_path_segment
from mealie_mcp_server.mealie.errors import MealieTransportError
from mealie_mcp_server.models.common import JsonObject, provided_fields
from mealie_mcp_server.models.inputs.recipe_io import (
    ARCHIVE_MAX_BYTES,
    EXPORT_MAX_BYTES,
    IMPORT_MAX_BYTES,
    UPLOAD_MAX_BYTES,
    CreateRecipeAssetFromUrlInput,
    ExportRecipeInput,
    ImportRecipeFromHtmlOrJsonInput,
    ImportRecipeFromUrlInput,
    ImportRecipeFromZipInput,
    UploadRecipeAssetInput,
)

ASSET_EXTENSIONS = frozenset(
    (
        "avif bmp gif heic heif jpg jpeg png webp m4v mov mp4 webm m4a mp3 "
        "docx md odt pdf rtf txt csv json"
    ).split()
)


def decode_file(payload: str, max_bytes: int) -> bytes:
    if len(payload) > 4 * ((max_bytes + 2) // 3):
        raise ValueError("File exceeds the size limit.")
    try:
        data = base64.b64decode(payload, validate=True)
    except ValueError, binascii.Error:
        raise ValueError("File must contain valid base64 data.") from None
    if not data or len(data) > max_bytes:
        raise ValueError("File is empty or exceeds the size limit.")
    return data


def recipe_path(slug: str) -> str:
    return "/api/recipes/" + encode_path_segment(slug, "slug")


def created_slug(result: JsonValue) -> str:
    if not isinstance(result, str) or not result.strip():
        raise MealieTransportError(
            "Mealie returned an invalid import response. Write outcome may be unknown."
        )
    return result


def asset_response(result: JsonValue) -> JsonObject:
    if not isinstance(result, dict) or any(
        not isinstance(result.get(key), str) for key in ("name", "fileName", "icon")
    ):
        raise MealieTransportError(
            "Mealie returned an invalid asset response. Write outcome may be unknown."
        )
    return result


async def upload_recipe_asset(client: MealieClient, request: UploadRecipeAssetInput) -> JsonValue:
    extension = request.extension.lower()
    if extension not in ASSET_EXTENSIONS:
        raise ValueError("Unsupported asset extension.")
    data = decode_file(request.file_base64, UPLOAD_MAX_BYTES)
    return asset_response(
        await client.request(
            "POST",
            recipe_path(request.slug) + "/assets",
            data={"name": request.name, "icon": request.icon, "extension": extension},
            files={"file": ("asset." + extension, data, "application/octet-stream")},
        )
    )


async def create_recipe_asset_from_url(
    client: MealieClient, request: CreateRecipeAssetFromUrlInput
) -> JsonValue:
    return asset_response(
        await client.request(
            "POST", recipe_path(request.slug) + "/assets/url", json={"url": request.url}
        )
    )


async def import_recipe_from_url(client: MealieClient, request: ImportRecipeFromUrlInput) -> str:
    return created_slug(
        await client.request("POST", "/api/recipes/create/url", json=provided_fields(request))
    )


async def import_recipe_from_html_or_json(
    client: MealieClient, request: ImportRecipeFromHtmlOrJsonInput
) -> str:
    if len(request.data.encode("utf-8")) > IMPORT_MAX_BYTES:
        raise ValueError("Import data exceeds the size limit.")
    return created_slug(
        await client.request(
            "POST", "/api/recipes/create/html-or-json", json=provided_fields(request)
        )
    )


async def import_recipe_from_zip(client: MealieClient, request: ImportRecipeFromZipInput) -> str:
    data = decode_file(request.archive_base64, ARCHIVE_MAX_BYTES)
    try:
        with ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if (
                not members
                or len(members) > 1000
                or sum(m.file_size for m in members) > 100 * 1024 * 1024
            ):
                raise ValueError("Archive exceeds the expanded size or member limit.")
            for member in members:
                path = PurePosixPath(member.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.filename
                    or ":" in member.filename
                    or member.flag_bits & 1
                ):
                    raise ValueError("Archive contains an unsafe or encrypted member.")
    except BadZipFile:
        raise ValueError("File must be a valid ZIP archive.") from None
    return created_slug(
        await client.request(
            "POST",
            "/api/recipes/create/zip",
            files={"archive": ("recipe.zip", data, "application/zip")},
        )
    )


async def get_recipe_export_formats(client: MealieClient) -> JsonValue:
    result = await client.request("GET", "/api/recipes/exports")
    if not isinstance(result, dict) or any(
        not isinstance(result.get(key), list)
        or any(not isinstance(item, str) for item in cast(list[JsonValue], result[key]))
        for key in ("json", "zip")
    ):
        raise MealieTransportError("Mealie returned invalid export formats.")
    return result


async def export_recipe(client: MealieClient, request: ExportRecipeInput) -> JsonObject:
    response = await client.get_binary(
        recipe_path(request.slug) + "/exports",
        params=[("template_name", request.template_name)],
        max_bytes=EXPORT_MAX_BYTES,
    )
    if not response.content:
        raise MealieTransportError("Mealie returned an empty export.")
    message = Message()
    message["content-disposition"] = response.content_disposition or ""
    filename = message.get_filename() or "recipe-export"
    if (
        any(ord(c) < 32 for c in filename)
        or any(c in filename for c in ("/", "\\"))
        or filename in {".", ".."}
        or len(filename) > 255
    ):
        filename = "recipe-export"
    return {
        "filename": filename,
        "mediaType": response.content_type,
        "size": len(response.content),
        "dataBase64": base64.b64encode(response.content).decode("ascii"),
    }
