import base64
import json

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server

RID = "11111111-1111-4111-8111-111111111111"
EID = "22222222-2222-4222-8222-222222222222"
TOKEN = "33333333-3333-4333-8333-333333333333"
RECIPE = {"id": RID, "slug": "soup", "assets": [{"fileName": "notes.pdf", "future": True}]}
CASES = {
    "get_recipe_assets": ({"slug": "soup"}, ["/api/recipes/soup"]),
    "download_recipe_asset": (
        {"slug": "soup", "fileName": "notes.pdf"},
        ["/api/recipes/soup", f"/api/media/recipes/{RID}/assets/notes.pdf"],
    ),
    "download_recipe_image": (
        {"slug": "soup"},
        ["/api/recipes/soup", f"/api/media/recipes/{RID}/images/original.webp"],
    ),
    "download_recipe_timeline_image": (
        {"slug": "soup", "eventId": EID},
        [
            "/api/recipes/soup",
            "/api/recipes/timeline/events/" + EID,
            f"/api/media/recipes/{RID}/images/timeline/{EID}/original.webp",
        ],
    ),
    "get_shared_recipe": ({"tokenId": TOKEN}, ["/api/recipes/shared/" + TOKEN]),
    "download_shared_recipe": ({"tokenId": TOKEN}, ["/api/recipes/shared/" + TOKEN + "/zip"]),
}


@pytest.mark.parametrize("name", CASES)
async def test_recipe_media_mcp_positive(name):
    arguments, expected = CASES[name]
    calls = []

    def handle(request):
        assert request.method == "GET"
        calls.append(request.url.path)
        if request.url.path.startswith("/api/media/") or request.url.path.endswith("/zip"):
            return httpx.Response(
                200, content=b"contents", headers={"content-type": "application/octet-stream"}
            )
        if "/timeline/events/" in request.url.path:
            return httpx.Response(200, json={"id": EID, "recipeId": RID})
        return httpx.Response(200, json=RECIPE)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with Client(
        create_server(
            settings,
            client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
        )
    ) as client:
        result = await client.call_tool(name, arguments)
    payload = json.loads(result.content[0].text)
    assert not result.is_error and calls == expected
    if name.startswith("download"):
        assert base64.b64decode(payload["dataBase64"]) == b"contents" and payload["size"] == 8
    else:
        assert payload == RECIPE


@pytest.mark.parametrize(
    "name,args",
    [
        ("download_recipe_asset", {"slug": "soup", "fileName": "../private-secret"}),
        ("get_shared_recipe", {"tokenId": "private-secret"}),
        ("download_recipe_timeline_image", {"slug": "soup", "eventId": "private-secret"}),
    ],
)
async def test_media_invalid_inputs_do_not_reach_provider(name, args):
    def forbidden(request):
        raise AssertionError("Invalid media arguments reached provider")

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with Client(
        create_server(
            settings,
            client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(forbidden)),
        )
    ) as client:
        result = await client.call_tool(name, args, raise_on_error=False)
    assert result.is_error and "private-secret" not in result.content[0].text
