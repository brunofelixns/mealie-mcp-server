import json

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.inputs.mealplan_advanced import CreateMealplanEntryInput
from mealie_mcp_server.services import mealplan_advanced as service

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    "data",
    [
        {"date": "2026-02-30"},
        {"date": "2026-11-03", "endDate": "2026-11-08"},
        {"date": "2026-11-03", "recipeScale": 0},
        {"date": "2026-11-03", "text": None},
    ],
)
def test_entry_validation(data):
    with pytest.raises(ValidationError):
        CreateMealplanEntryInput.model_validate(data)


async def test_entry_put_preserves_unknown_and_native_fields():
    current = {
        "id": 1,
        "date": "2026-11-03",
        "endDate": "2026-11-09",
        "text": "note",
        "recipeScale": 2,
        "entryType": "dinner",
        "groupId": "group",
        "userId": "user",
        "unknown": {"future": False},
        "recipeId": None,
    }
    calls = []

    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=current)
        assert json.loads(request.content) == {**current, "title": "new"}
        return httpx.Response(200, json={**current, "title": "new"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await service.update_mealplan_entry(client, 1, {"title": "new"})
    assert result["unknown"] == {"future": False}
    assert calls == ["GET", "PUT"]


async def test_partial_date_update_validates_merged_week_before_put():
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json={"id": 1, "date": "2026-11-03", "endDate": "2026-11-09"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await service.update_mealplan_entry(client, 1, {"date": "2026-11-04"})
    assert calls == ["GET"]


@pytest.mark.parametrize(
    "operation", ["create", "random", "delete", "rule_create", "rule_delete", "rotate", "disable"]
)
@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_planning_write_failures_are_not_replayed(operation, failure):
    calls = []

    def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            if operation == "create":
                await service.create_mealplan_entry(client, {"date": "2026-11-03"})
            elif operation == "random":
                await service.create_random_mealplan_entry(client, {"date": "2026-11-03"})
            elif operation == "delete":
                await service.delete_mealplan_entry(client, 1)
            elif operation == "rule_create":
                await service.create_mealplan_rule(client, {"day": "unset"})
            elif operation == "rule_delete":
                await service.delete_mealplan_rule(client, "22222222-2222-4222-8222-222222222222")
            elif operation == "rotate":
                await service.rotate_mealplan_ical_token(client)
            else:
                await service.delete_mealplan_ical_token(client)
    assert len(calls) == 1


@pytest.mark.parametrize("operation", ["entry", "rule"])
@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_planning_put_failure_does_not_replay(operation, failure):
    calls = []

    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "date": "2026-11-03",
                    "endDate": None,
                    "text": "Old",
                    "day": "unset",
                },
            )
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            if operation == "entry":
                await service.update_mealplan_entry(client, 1, {"text": "New"})
            else:
                await service.update_mealplan_rule(
                    client, "22222222-2222-4222-8222-222222222222", {"day": "monday"}
                )
    assert calls == ["GET", "PUT"]
