import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.api import foods
from mealie_mcp_server.mealie.client import MealieClient

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    ("operation", "args", "message"),
    [
        ("get_food", [" "], "foodId is required"),
        ("delete_food", [" "], "foodId is required"),
        ("update_food", [" ", {"name": "x"}], "foodId is required"),
        ("update_food", ["id", {}], "At least one field"),
        ("create_food", [{"name": " "}], "Food name cannot be empty"),
        ("merge_foods", ["x", "x"], "must be different"),
        ("merge_foods", ["", "x"], "fromFoodId is required"),
        ("merge_foods", ["x", ""], "toFoodId is required"),
    ],
)
async def test_rejections_do_not_reach_provider(operation, args, message):
    def handler(request):
        pytest.fail("invalid input reached provider")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match=message):
            await getattr(foods, operation)(client, *args)


@pytest.mark.parametrize("status", [404, 409, 500])
async def test_get_errors_add_context_without_raw_provider_body(status):
    def handler(request):
        return httpx.Response(
            status, json={"detail": "private provider body", "token": "fixture-secret"}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError) as raised:
            await foods.get_food(client, "id")
    text = str(raised.value)
    assert ("Food not found" if status == 404 else "Unable to retrieve food") in text
    assert str(status) in text
    assert "private provider body" not in text
    assert "fixture-secret" not in text


@pytest.mark.parametrize("failure_stage", ["source", "target", "put", "verification"])
async def test_merge_errors_do_not_repeat_writes(failure_stage):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if (
            (failure_stage == "source" and len(calls) == 1)
            or (failure_stage == "target" and len(calls) == 2)
            or (failure_stage == "put" and request.method == "PUT")
            or (failure_stage == "verification" and len(calls) == 4)
        ):
            return httpx.Response(500, json={"detail": "private"})
        return httpx.Response(200, json={"id": "id", "name": "food"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError):
            await foods.merge_foods(client, "from", "to")
    assert sum(method == "PUT" for method, _ in calls) == (
        0 if failure_stage in {"source", "target"} else 1
    )


async def test_create_minimal_food_sends_only_name():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "id", "name": "Basil"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        await foods.create_food(client, {"name": " Basil "})
    assert calls == [{"name": "Basil"}]
