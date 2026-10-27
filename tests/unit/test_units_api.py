import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.api import units
from mealie_mcp_server.mealie.client import MealieClient

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("operation", "args", "message"),
    [
        ("get_unit", [" "], "unitId is required"),
        ("delete_unit", [" "], "unitId is required"),
        ("update_unit", [" ", {"name": "x"}], "unitId is required"),
        ("update_unit", ["id", {}], "At least one field"),
        ("create_unit", [{"name": " "}], "Unit name cannot be empty"),
    ],
)
async def test_rejections_do_not_reach_provider(operation, args, message):
    def handler(request):
        pytest.fail("invalid input reached provider")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match=message):
            await getattr(units, operation)(client, *args)


async def test_conversion_fields_are_forwarded_without_inference():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "id", "name": "measure"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        await units.create_unit(client, {"name": "measure", "standardQuantity": 2.5})
    assert calls == [{"name": "measure", "standardQuantity": 2.5}]


@pytest.mark.parametrize("status", [404, 409, 500])
async def test_delete_errors_keep_context_and_status(status):
    def handler(request):
        return httpx.Response(status, json={"detail": "private provider body"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as raised:
            await units.delete_unit(client, "id")
    text = str(raised.value)
    assert ("Unit not found" if status == 404 else "Unable to delete unit") in text
    assert str(status) in text
    assert "private provider body" not in text
