"""Native import/export jobs, bounded progress and guarded partial batch edits.

AI execution belongs to Mealie's configured provider. No local AI credentials,
fallback imports, reconnects or automatic write retries are used here.
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from uuid import UUID

from pydantic import JsonValue

from mealie_mcp_server.mealie.api import recipes
from mealie_mcp_server.mealie.client import MealieClient, MultipartFiles, encode_path_segment
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.common import JsonObject, provided_fields
from mealie_mcp_server.models.inputs.recipe_io import (
    EXPORT_MAX_BYTES,
    IMPORT_MAX_BYTES,
    ImportRecipeFromHtmlOrJsonInput,
    ImportRecipeFromUrlInput,
)
from mealie_mcp_server.models.inputs.recipe_jobs import (
    AI_IMAGE_MAX_BYTES,
    AI_TOTAL_IMAGE_MAX_BYTES,
    BatchMetadataItem,
    DeleteRecipesBulkInput,
    DownloadRecipeBulkExportInput,
    ExportRecipesBulkInput,
    GetRecipeImportReportInput,
    ImportRecipesFromUrlsInput,
    ImportRecipeWithAiInput,
    PreviewRecipeFromUrlInput,
    UpdateRecipeMetadataBatchInput,
    uuid4_string,
)
from mealie_mcp_server.services.recipe_io import created_slug, decode_file
from mealie_mcp_server.services.recipe_metadata import update_recipe_metadata

type ProgressCallback = Callable[[int], Awaitable[None]]
UNKNOWN = " Write outcome may be unknown; inspect recipes before another import."


def _completed_slug(result: JsonValue) -> str:
    value = created_slug(result)
    try:
        encode_path_segment(value)
        if len(value) > 255 or any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError
    except ValueError:
        raise MealieTransportError(
            "Mealie returned an invalid import completion." + UNKNOWN
        ) from None
    return value


def _ai_parts(request: ImportRecipeWithAiInput) -> MultipartFiles:
    parts: list[tuple[str, tuple[str | None, bytes | str, str | None]]] = []
    values = provided_fields(request)
    for name in ("content", "url", "translateLanguage", "createNewOrganizers"):
        value = values.get(name)
        if value is None:
            # Null optional Form fields represent absence in Mealie's native schema.
            continue
        text = ("true" if value else "false") if isinstance(value, bool) else str(value)
        if len(text.encode("utf-8")) > IMPORT_MAX_BYTES:
            raise ValueError("AI import content exceeds the size limit.")
        parts.append((name, (None, text, None)))
    size = 0
    for image in request.images:
        content = decode_file(image.data_base64, AI_IMAGE_MAX_BYTES)
        size += len(content)
        if size > AI_TOTAL_IMAGE_MAX_BYTES:
            raise ValueError("AI import images exceed the combined size limit.")
        parts.append(("images", (image.filename, content, image.media_type)))
    return parts


async def preview_recipe_from_url(
    client: MealieClient, request: PreviewRecipeFromUrlInput
) -> JsonValue:
    result = await client.request(
        "POST", "/api/recipes/test-scrape-url", json=provided_fields(request)
    )
    if not isinstance(result, dict):
        raise MealieTransportError("Mealie returned an invalid scrape preview.")
    return result


async def import_recipe_with_ai(client: MealieClient, request: ImportRecipeWithAiInput) -> str:
    parts = _ai_parts(request)
    try:
        result = await client.request("POST", "/api/recipes/create/ai", files=parts)
    except MealieTransportError:
        raise MealieTransportError("Mealie AI import could not be confirmed." + UNKNOWN) from None
    return _completed_slug(result)


async def _import_progress(
    client: MealieClient,
    path: str,
    *,
    payload: JsonValue | None = None,
    files: MultipartFiles | None = None,
    progress: ProgressCallback | None = None,
) -> str:
    stream = (
        client.stream_events(path, files=files)
        if files is not None
        else client.stream_events(path, json=payload)
    )
    count = 0
    async with aclosing(stream):
        async for event in stream:
            if event.event == "done":
                if not isinstance(event.data, dict):
                    raise MealieTransportError(
                        "Mealie returned an invalid import completion." + UNKNOWN
                    )
                return _completed_slug(event.data.get("slug"))
            if event.event == "error":
                # Provider messages may contain source content, credentials or signed
                # URLs. Surface a safe failure, never the free-form message itself.
                raise MealieTransportError("Mealie reported an import failure." + UNKNOWN)
            if (
                event.event != "progress"
                or not isinstance(event.data, dict)
                or not isinstance(event.data.get("message"), str)
            ):
                raise MealieTransportError("Mealie returned invalid import progress." + UNKNOWN)
            count += 1
            if progress is not None:
                await progress(count)
    raise MealieTransportError("Mealie import stream ended before completion." + UNKNOWN)


async def import_recipe_from_url_with_progress(
    client: MealieClient,
    request: ImportRecipeFromUrlInput,
    progress: ProgressCallback | None = None,
) -> str:
    return await _import_progress(
        client,
        "/api/recipes/create/url/stream",
        payload=provided_fields(request),
        progress=progress,
    )


async def import_recipe_from_html_or_json_with_progress(
    client: MealieClient,
    request: ImportRecipeFromHtmlOrJsonInput,
    progress: ProgressCallback | None = None,
) -> str:
    if len(request.data.encode("utf-8")) > IMPORT_MAX_BYTES:
        raise ValueError("Import data exceeds the size limit.")
    return await _import_progress(
        client,
        "/api/recipes/create/html-or-json/stream",
        payload=provided_fields(request),
        progress=progress,
    )


async def import_recipe_with_ai_with_progress(
    client: MealieClient,
    request: ImportRecipeWithAiInput,
    progress: ProgressCallback | None = None,
) -> str:
    return await _import_progress(
        client, "/api/recipes/create/ai/stream", files=_ai_parts(request), progress=progress
    )


async def import_recipes_from_urls(
    client: MealieClient, request: ImportRecipesFromUrlsInput
) -> JsonObject:
    try:
        result = await client.request(
            "POST", "/api/recipes/create/url/bulk", json=provided_fields(request)
        )
    except MealieTransportError:
        raise MealieTransportError("Mealie bulk import could not be confirmed." + UNKNOWN) from None
    try:
        if not isinstance(result, dict) or not isinstance(result.get("reportId"), str):
            raise ValueError
        uuid4_string(str(result["reportId"]))
    except ValueError:
        raise MealieTransportError(
            "Mealie returned an invalid bulk import report identifier." + UNKNOWN
        ) from None
    return {**result, "status": "accepted", "atomic": False}


async def get_recipe_import_reports(client: MealieClient) -> JsonValue:
    result = await client.request(
        "GET", "/api/groups/reports", params=[("report_type", "bulk_import")]
    )
    if not isinstance(result, list) or any(
        not isinstance(item, dict) or item.get("category") != "bulk_import" for item in result
    ):
        raise MealieTransportError("Mealie returned invalid import reports.")
    return result


async def get_recipe_import_report(
    client: MealieClient, request: GetRecipeImportReportInput
) -> JsonValue:
    result = await client.request(
        "GET", "/api/groups/reports/" + encode_path_segment(request.report_id)
    )
    if not isinstance(result, dict) or result.get("category") != "bulk_import":
        raise MealieTransportError("Mealie did not return a recipe import report.")
    return result


async def delete_recipes_bulk(client: MealieClient, request: DeleteRecipesBulkInput) -> JsonObject:
    result = await client.request(
        "POST", "/api/recipes/bulk-actions/delete", json=provided_fields(request)
    )
    return {
        "status": "completed",
        "atomic": False,
        "perItemOutcomes": "notReported",
        "providerResult": result,
    }


async def export_recipes_bulk(client: MealieClient, request: ExportRecipesBulkInput) -> JsonObject:
    result = await client.request(
        "POST", "/api/recipes/bulk-actions/export", json=provided_fields(request)
    )
    return {"status": "accepted", "atomic": False, "providerResult": result}


async def get_recipe_bulk_exports(client: MealieClient) -> JsonValue:
    result = await client.request("GET", "/api/recipes/bulk-actions/export")
    if not isinstance(result, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in result
    ):
        raise MealieTransportError("Mealie returned invalid bulk exports.")
    return result


async def download_recipe_bulk_export(
    client: MealieClient, request: DownloadRecipeBulkExportInput
) -> JsonObject:
    result = await client.request(
        "GET",
        "/api/recipes/bulk-actions/export/" + encode_path_segment(request.export_id) + "/download",
    )
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("fileToken"), str)
        or not result["fileToken"]
        or len(str(result["fileToken"])) > 8192
    ):
        raise MealieTransportError("Mealie returned an invalid export download token.")
    response = await client.get_binary(
        "/api/utils/download",
        params=[("token", str(result["fileToken"]))],
        max_bytes=EXPORT_MAX_BYTES,
    )
    if not response.content:
        raise MealieTransportError("Mealie returned an empty bulk export.")
    return {
        "filename": "recipes-" + request.export_id + ".zip",
        "mediaType": response.content_type,
        "size": len(response.content),
        "dataBase64": base64.b64encode(response.content).decode("ascii"),
    }


async def purge_recipe_bulk_exports(client: MealieClient) -> JsonValue:
    result = await client.request("DELETE", "/api/recipes/bulk-actions/export/purge")
    if not isinstance(result, dict):
        raise MealieTransportError(
            "Mealie returned an invalid export purge response. Write outcome may be unknown."
        )
    return result


async def update_recipe_metadata_batch(
    client: MealieClient, request: UpdateRecipeMetadataBatchInput
) -> JsonObject:
    semaphore = asyncio.Semaphore(request.concurrency)

    async def resolve(item: BatchMetadataItem) -> str | JsonObject:
        async with semaphore:
            try:
                recipe = await recipes.get_recipe(client, item.slug)
                identity = recipe.get("id")
                if not isinstance(identity, str):
                    raise ValueError("Invalid recipe identity.")
                return str(UUID(uuid4_string(identity)))
            except MealieApiError as error:
                return {
                    "slug": item.slug,
                    "status": "failed",
                    "error": f"Mealie API error {error.status}; no metadata write was issued.",
                }
            except ValueError, MealieTransportError:
                return {
                    "slug": item.slug,
                    "status": "failed",
                    "error": "Recipe identity could not be resolved; no metadata write was issued.",
                }

    # Native recipe reads accept both slugs and UUIDs. Resolve the entire batch
    # before writing so aliases cannot overwrite each other's nested snapshots.
    targets = await asyncio.gather(*(resolve(item) for item in request.items))
    identities = [target for target in targets if isinstance(target, str)]
    if len(set(identities)) != len(identities):
        raise ValueError("Metadata batch cannot edit the same recipe twice.")

    async def update(item: BatchMetadataItem, target: str | JsonObject) -> JsonObject:
        if not isinstance(target, str):
            return target
        async with semaphore:
            try:
                # Re-read through the stable ID immediately before constructing
                # the patch; identity preflight is not a fresh metadata snapshot.
                recipe = await update_recipe_metadata(client, target, provided_fields(item))
                return {"slug": item.slug, "status": "updated", "recipe": recipe}
            except ValueError as error:
                stale = str(error).startswith("Stale snapshot")
                return {
                    "slug": item.slug,
                    "status": "rejected" if stale else "unknown",
                    "error": "Stale metadata snapshot."
                    if stale
                    else "Metadata update could not be verified; inspect recipe before retrying.",
                }
            except MealieApiError as error:
                return {
                    "slug": item.slug,
                    "status": "failed" if error.status < 500 else "unknown",
                    "error": f"Mealie API error {error.status}.",
                }
            except MealieTransportError:
                return {
                    "slug": item.slug,
                    "status": "unknown",
                    "error": "Metadata request failed; inspect recipe before retrying.",
                }

    items = await asyncio.gather(
        *(update(item, target) for item, target in zip(request.items, targets, strict=True))
    )
    return {"atomic": False, "items": list(items)}
