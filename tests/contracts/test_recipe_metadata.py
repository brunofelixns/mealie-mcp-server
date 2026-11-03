import json

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server


@pytest.mark.parametrize("name", ["update_recipe_metadata"])
async def test_recipe_metadata_mcp_positive(name):
    original = {
        "slug": "soup",
        "updatedAt": "snapshot",
        "nutrition": {"calories": "100"},
        "settings": {"public": False, "showNutrition": True},
        "notes": [{"title": "Keep", "text": "Keep"}],
    }
    writes = []

    def handle(request):
        assert request.url.path == "/api/recipes/soup"
        if request.method == "GET":
            return httpx.Response(200, json=original)
        assert request.method == "PATCH"
        writes.append(json.loads(request.content))
        return httpx.Response(200, json={**original, **writes[-1]})

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    server = create_server(
        settings,
        client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
    )
    async with Client(server) as client:
        result = await client.call_tool(
            name,
            {
                "slug": "soup",
                "expectedUpdatedAt": "snapshot",
                "prepTime": "PT10M",
                "nutrition": {"proteinContent": "5"},
                "settings": {"showNutrition": False},
            },
        )
    payload = json.loads(result.content[0].text)
    assert not result.is_error and payload["notes"] == original["notes"]
    assert writes == [
        {
            "prepTime": "PT10M",
            "nutrition": {"calories": "100", "proteinContent": "5"},
            "settings": {"public": False, "showNutrition": False},
        }
    ]
