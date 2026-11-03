import json

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie

REF = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
TOKEN = "2026-11-03T10:00:00Z"
NOTE = {"referenceId": REF, "title": "Keep", "text": "Original", "unknown": False}
ORIGINAL = {"slug": "soup", "updatedAt": TOKEN, "notes": [NOTE], "recipeInstructions": []}
WRITE = {"slug": "soup", "expectedUpdatedAt": TOKEN}
CASES = [
    ("get_recipe_notes", {"slug": "soup"}, None),
    (
        "add_recipe_note",
        {**WRITE, "referenceId": OTHER, "title": "", "text": ""},
        {"notes": [NOTE, {"referenceId": OTHER, "title": "", "text": ""}]},
    ),
    (
        "update_recipe_note",
        {**WRITE, "referenceId": REF, "text": "Changed"},
        {"notes": [{**NOTE, "text": "Changed"}]},
    ),
    ("delete_recipe_note", {**WRITE, "referenceId": REF}, {"notes": []}),
]


@pytest.mark.parametrize("tool,arguments,payload", CASES, ids=[row[0] for row in CASES])
async def test_recipe_notes_mcp_positive(tool, arguments, payload):
    expected = {**ORIGINAL, **(payload or {})}
    requests = [{"method": "GET", "path": "/api/recipes/soup", "response": ORIGINAL}]
    if payload is not None:
        requests.append(
            {"method": "PATCH", "path": "/api/recipes/soup", "body": payload, "response": expected}
        )
    else:
        expected = {key: ORIGINAL[key] for key in ("slug", "updatedAt", "notes")}
    for request in requests:
        request["query"] = {}
    with FakeMealie(requests) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool, arguments)
        assert not result.is_error
        assert json.loads(result.content[0].text) == expected
        assert len(fake.recorded_requests) == len(requests)


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("get_recipe_notes", {"slug": "soup", "unexpected": True}),
        ("get_recipe_notes", {"slug": 12}),
        ("add_recipe_note", {**WRITE, "title": "X", "text": "Y", "referenceId": None}),
        ("add_recipe_note", {**WRITE, "title": None, "text": "Y"}),
        ("add_recipe_note", {"slug": "soup", "title": "X", "text": "Y"}),
        ("add_recipe_note", {**WRITE, "title": "X", "text": "Y", "reference_id": OTHER}),
        ("update_recipe_note", {**WRITE, "referenceId": REF}),
        ("update_recipe_note", {**WRITE, "referenceId": REF, "text": None}),
        ("update_recipe_note", {**WRITE, "referenceId": "bad", "text": "X"}),
        ("delete_recipe_note", {**WRITE, "referenceId": REF, "removeReferences": 1}),
        ("delete_recipe_note", {**WRITE, "referenceId": REF, "expectedUpdatedAt": ""}),
    ],
)
async def test_recipe_notes_mcp_rejects_invalid_arguments_before_http(tool, arguments):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests


async def test_recipe_notes_mcp_provider_failure_is_sanitized_and_never_retried():
    requests = [
        {"method": "GET", "path": "/api/recipes/soup", "response": ORIGINAL},
        {
            "method": "PATCH",
            "path": "/api/recipes/soup",
            "body": {"notes": []},
            "status": 403,
            "response": {"detail": "private provider body"},
        },
    ]
    for request in requests:
        request["query"] = {}
    with FakeMealie(requests) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                "delete_recipe_note", {**WRITE, "referenceId": REF}, raise_on_error=False
            )
        assert result.is_error
        assert "403" in result.content[0].text
        assert "private provider body" not in result.content[0].text
        assert len(fake.recorded_requests) == 2
