import base64
import json
from io import BytesIO
from zipfile import ZipFile

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.models.inputs.recipe_media import DownloadRecipeAssetInput
from mealie_mcp_server.services.recipe_media import (
    download_recipe_asset,
    download_recipe_image,
    download_recipe_timeline_image,
    download_shared_recipe,
    get_recipe_assets,
    get_shared_recipe,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
RID = "11111111-1111-4111-8111-111111111111"
EID = "22222222-2222-4222-8222-222222222222"
TOKEN = "33333333-3333-4333-8333-333333333333"
RECIPE = {
    "id": RID,
    "slug": "soup",
    "updatedAt": "snapshot",
    "assets": [{"fileName": "notes.pdf", "name": "Notes", "future": 0}],
}


@pytest.mark.parametrize(
    "operation,path",
    [
        ("asset", f"/api/media/recipes/{RID}/assets/notes.pdf"),
        ("image", f"/api/media/recipes/{RID}/images/min-original.webp"),
        ("timeline", f"/api/media/recipes/{RID}/images/timeline/{EID}/original.webp"),
    ],
)
async def test_media_downloads_are_resolved_from_current_recipe_and_return_binary(operation, path):
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        assert request.headers["authorization"] == "Bearer fixture"
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json=RECIPE)
        if request.url.path == "/api/recipes/timeline/events/" + EID:
            return httpx.Response(200, json={"id": EID, "recipeId": RID})
        assert request.url.path == path
        return httpx.Response(
            200, content=b"file-content", headers={"content-type": "application/pdf"}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        if operation == "asset":
            result = await download_recipe_asset(client, "soup", "notes.pdf")
        elif operation == "image":
            result = await download_recipe_image(client, "soup", "min-original.webp")
        else:
            result = await download_recipe_timeline_image(client, "soup", EID, "original.webp")
    assert base64.b64decode(result["dataBase64"]) == b"file-content"
    assert result["size"] == 12 and result["mediaType"] == "application/pdf"
    assert calls[-1] == ("GET", path)


async def test_media_listing_retains_unknown_asset_fields():
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=RECIPE))
    ) as client:
        result = await get_recipe_assets(client, "soup")
    assert result == RECIPE


@pytest.mark.parametrize(
    "defect", ["missing", "malformed_assets", "bad_recipe_id", "different_event"]
)
async def test_media_refuses_missing_or_mismatched_identity_before_binary_download(defect):
    calls = []
    recipe = {**RECIPE}
    if defect == "malformed_assets":
        recipe["assets"] = "invalid"
    if defect == "bad_recipe_id":
        recipe["id"] = "../secret"

    def handle(request):
        calls.append(request.url.path)
        if "/timeline/events/" in request.url.path:
            return httpx.Response(200, json={"id": EID, "recipeId": TOKEN})
        return httpx.Response(200, json=recipe)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            if defect == "different_event":
                await download_recipe_timeline_image(client, "soup", EID, "original.webp")
            else:
                await download_recipe_asset(
                    client, "soup", "absent.pdf" if defect == "missing" else "notes.pdf"
                )
    assert not any(path.startswith("/api/media/") for path in calls)


@pytest.mark.parametrize(
    "filename", ["../secret", "a/b.pdf", "a\\b.pdf", ".", "..", "bad\nfile.pdf"]
)
def test_asset_paths_reject_traversal_and_controls(filename):
    with pytest.raises(ValidationError):
        DownloadRecipeAssetInput.model_validate({"slug": "soup", "fileName": filename})


async def test_shared_read_and_zip_use_only_configured_origin_and_safe_names():
    buf = BytesIO()
    with ZipFile(buf, "w") as archive:
        archive.writestr("recipe.json", json.dumps(RECIPE))
    content = buf.getvalue()

    def handle(request):
        assert request.url.host == "mealie.test"
        assert request.url.path.startswith("/api/recipes/shared/" + TOKEN)
        if request.url.path.endswith("/zip"):
            return httpx.Response(
                200,
                content=content,
                headers={
                    "content-type": "application/zip",
                    "content-disposition": 'attachment; filename="../../unsafe.zip"',
                },
            )
        return httpx.Response(200, json=RECIPE)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await get_shared_recipe(client, TOKEN) == RECIPE
        result = await download_shared_recipe(client, TOKEN)
    assert result["filename"] == "shared-recipe.zip"
    assert base64.b64decode(result["dataBase64"]) == content


@pytest.mark.parametrize("mode", ["redirect", "oversize", "http"])
async def test_media_download_failures_are_bounded_and_confidential(mode):
    binary_calls = []

    def handle(request):
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json=RECIPE)
        binary_calls.append(request.url.host)
        if mode == "redirect":
            return httpx.Response(
                302, headers={"location": "https://outside.test/private?secret=value"}
            )
        if mode == "oversize":
            return httpx.Response(200, headers={"content-length": str(21 * 1024 * 1024)})
        return httpx.Response(403, json={"detail": "private-secret"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(Exception) as caught:
            await download_recipe_asset(client, "soup", "notes.pdf")
    assert binary_calls == ["mealie.test"]
    assert "secret" not in str(caught.value)
