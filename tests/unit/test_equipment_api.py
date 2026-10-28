import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.api import equipment
from mealie_mcp_server.mealie.client import MealieClient

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("operation", "args", "message"),
    [
        ("get_tool", [" "], "toolId is required"),
        ("delete_tool", [" "], "toolId is required"),
        ("update_tool", [" ", {"name": "x"}], "toolId is required"),
        ("create_tool", [" "], "Tool name cannot be empty"),
        ("update_tool", ["id", {}], "At least one field"),
        ("update_tool", ["id", {"name": " "}], "Tool name cannot be empty"),
    ],
)
async def test_rejections_do_not_reach_mealie(operation, args, message):
    def handle(request):
        pytest.fail("invalid input reached Mealie")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match=message):
            await getattr(equipment, operation)(client, *args)


async def test_rename_preserves_households_and_strips_response_only_fields():
    calls = []
    existing = {
        "id": "id",
        "name": "Pan",
        "householdsWithTool": ["a", "b"],
        "slug": "pan",
        "createdAt": "old",
    }

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=existing)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await equipment.update_tool(client, "id", {"name": " Wok "})
    assert [(r.method, r.url.path) for r in calls] == [
        ("GET", "/api/organizers/tools/id"),
        ("PUT", "/api/organizers/tools/id"),
    ]
    assert json.loads(calls[1].content) == {
        "id": "id",
        "name": "Wok",
        "householdsWithTool": ["a", "b"],
    }


@pytest.mark.parametrize("status", [404, 400, 500])
async def test_delete_errors_keep_status_and_tool_context(status):
    def handle(request):
        return httpx.Response(status, json={"detail": "private body"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError) as raised:
            await equipment.delete_tool(client, "id")
    assert str(status) in str(raised.value)
    assert ("Tool not found" if status == 404 else "Unable to delete tool") in str(raised.value)
    assert "private body" not in str(raised.value)
