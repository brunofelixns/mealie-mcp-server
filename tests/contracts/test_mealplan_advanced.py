import base64
import json

import httpx2 as httpx
import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.server import create_server
from tests.contracts.test_recipe_collections import spec
from tests.support.fake_mealie import FakeMealie

ID = "22222222-2222-4222-8222-222222222222"
PLAN = "/api/households/mealplans"
RULE = PLAN + "/rules"
ICAL = PLAN + "/ical"
ENTRY = {
    "id": 1,
    "date": "2026-11-03",
    "endDate": "2026-11-09",
    "text": "Note",
    "recipeScale": 2,
    "unknown": [],
    "groupId": ID,
    "userId": ID,
}
RULE_DATA = {
    "id": ID,
    "day": "monday",
    "entryType": "dinner",
    "queryFilterString": "name~soup",
    "unknown": False,
}
CALENDAR = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
CASES = {
    "list_mealplan_entries": (
        {"start_date": "2026-11-03", "end_date": "2026-11-09", "include_week_entries": True},
        [
            spec(
                "GET",
                PLAN,
                query={
                    "start_date": ["2026-11-03"],
                    "end_date": ["2026-11-09"],
                    "include_week_entries": ["true"],
                },
                response={"items": [ENTRY], "total": 1},
            )
        ],
    ),
    "create_mealplan_entry": (
        {
            "date": "2026-11-03",
            "endDate": "2026-11-09",
            "text": "",
            "recipeId": None,
            "recipeScale": 2,
        },
        [
            spec(
                "POST",
                PLAN,
                {
                    "date": "2026-11-03",
                    "endDate": "2026-11-09",
                    "text": "",
                    "recipeId": None,
                    "recipeScale": 2,
                },
                response=ENTRY,
            )
        ],
    ),
    "get_mealplan_entry": ({"entryId": 1}, [spec("GET", PLAN + "/1", response=ENTRY)]),
    "update_mealplan_entry": (
        {"entryId": 1, "changes": {"text": "", "recipeScale": 3}},
        [
            spec("GET", PLAN + "/1", response=ENTRY),
            spec(
                "PUT",
                PLAN + "/1",
                {**ENTRY, "text": "", "recipeScale": 3},
                response={**ENTRY, "text": "", "recipeScale": 3},
            ),
        ],
    ),
    "delete_mealplan_entry": ({"entryId": 1}, [spec("DELETE", PLAN + "/1", response=ENTRY)]),
    "create_random_mealplan_entry": (
        {"date": "2026-11-03", "endDate": "2026-11-09", "entryType": "dinner"},
        [
            spec(
                "POST",
                PLAN + "/random",
                {"date": "2026-11-03", "endDate": "2026-11-09", "entryType": "dinner"},
                response=ENTRY,
            )
        ],
    ),
    "get_mealplan_rules": ({}, [spec("GET", RULE, response={"items": [RULE_DATA], "total": 1})]),
    "create_mealplan_rule": (
        {"day": "monday", "entryType": "dinner", "queryFilterString": ""},
        [
            spec(
                "POST",
                RULE,
                {"day": "monday", "entryType": "dinner", "queryFilterString": ""},
                response=RULE_DATA,
            )
        ],
    ),
    "get_mealplan_rule": ({"ruleId": ID}, [spec("GET", f"{RULE}/{ID}", response=RULE_DATA)]),
    "update_mealplan_rule": (
        {"ruleId": ID, "changes": {"queryFilterString": ""}},
        [
            spec("GET", f"{RULE}/{ID}", response=RULE_DATA),
            spec(
                "PUT",
                f"{RULE}/{ID}",
                {**RULE_DATA, "queryFilterString": ""},
                response={**RULE_DATA, "queryFilterString": ""},
            ),
        ],
    ),
    "delete_mealplan_rule": ({"ruleId": ID}, [spec("DELETE", f"{RULE}/{ID}", response=RULE_DATA)]),
    "get_mealplan_ical_token": (
        {},
        [spec("GET", ICAL, response={"householdId": ID, "mealplanIcalToken": None})],
    ),
    "rotate_mealplan_ical_token": (
        {},
        [spec("POST", ICAL, response={"householdId": ID, "mealplanIcalToken": "new-token"})],
    ),
    "delete_mealplan_ical_token": (
        {},
        [spec("DELETE", ICAL, response={"householdId": ID, "mealplanIcalToken": None})],
    ),
    "get_mealplan_ical_feed": (
        {
            "token": "fixture",
            "types": ["dinner", "snack"],
            "tz": "Europe/Madrid",
            "includeNotes": False,
            "dinner": "19:30:00",
        },
        [
            {
                **spec(
                    "GET",
                    ICAL + "/fixture",
                    query={
                        "types": ["dinner", "snack"],
                        "tz": ["Europe/Madrid"],
                        "includeNotes": ["false"],
                        "dinner": ["19:30:00"],
                    },
                ),
                "responseBase64": base64.b64encode(CALENDAR).decode(),
                "responseContentType": "text/calendar",
            }
        ],
    ),
}


@pytest.mark.parametrize("tool_name", CASES)
async def test_mealplan_advanced_mcp_positive(tool_name):
    arguments, requests = CASES[tool_name]
    if tool_name == "get_mealplan_ical_feed":
        calls = []

        def handle(request):
            calls.append(request)
            assert request.url.path == ICAL + "/fixture"
            assert request.url.params.get_list("types") == ["dinner", "snack"]
            assert request.url.params["includeNotes"] == "false"
            assert request.url.params["tz"] == "Europe/Madrid"
            assert request.url.params["dinner"] == "19:30:00"
            return httpx.Response(200, content=CALENDAR, headers={"content-type": "text/calendar"})

        settings = load_settings(
            {"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"}
        )
        server = create_server(
            settings,
            client_factory=lambda: MealieClient(settings, transport=httpx.MockTransport(handle)),
        )
        async with Client(server) as client:
            result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        assert not result.is_error
        data = json.loads(result.content[0].text)
        assert base64.b64decode(data["dataBase64"]) == CALENDAR
        assert data["size"] == len(CALENDAR)
        assert len(calls) == 1
        return
    with FakeMealie(requests) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        assert not result.is_error
        data = json.loads(result.content[0].text)
        assert data == requests[-1]["response"]
        assert len(fake.recorded_requests) == len(requests)


@pytest.mark.parametrize("tool_name", CASES)
async def test_mealplan_advanced_unknown_field_no_http(tool_name):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                tool_name, {**CASES[tool_name][0], "unexpected": True}, raise_on_error=False
            )
        assert result.is_error
        assert fake.recorded_requests == []


@pytest.mark.parametrize(
    "name,args",
    [
        ("create_mealplan_entry", {"date": "2026-02-30"}),
        ("create_mealplan_entry", {"date": "2026-11-03", "endDate": "2026-11-08"}),
        ("create_random_mealplan_entry", {"date": "2026-11-03", "endDate": "2026-11-10"}),
        ("create_mealplan_entry", {"date": "2026-11-03", "recipeScale": 0}),
        ("create_mealplan_entry", {"date": "2026-11-03", "text": None}),
        ("update_mealplan_entry", {"entryId": 1, "changes": {"userId": ID}}),
        ("get_mealplan_ical_feed", {"token": "fixture", "tz": "Invalid/Timezone"}),
        ("get_mealplan_ical_feed", {"token": "fixture", "dinner": "25:00:00"}),
    ],
)
async def test_mealplan_advanced_invalid_no_http(name, args):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(name, args, raise_on_error=False)
        assert result.is_error
        assert fake.recorded_requests == []
