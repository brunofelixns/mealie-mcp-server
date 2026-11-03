import base64
import json

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie

RID = "11111111-1111-4111-8111-111111111111"
ID = "22222222-2222-4222-8222-222222222222"
PNG = b"\x89PNG\r\n\x1a\nhello"
BASE64 = base64.b64encode(PNG).decode()


def spec(method, path, body=None, query=None, response=None):
    return {
        "method": method,
        "path": path,
        "body": body,
        "query": query or {},
        "response": response,
    }


RESOLVE = spec("GET", "/api/recipes/soup", response={"id": RID})
CASES = {
    "get_recipe_comments": (
        {"slug": "soup"},
        [spec("GET", "/api/recipes/soup/comments", response=[{"id": ID, "unknown": False}])],
    ),
    "create_recipe_comment": (
        {"slug": "soup", "text": " good "},
        [
            RESOLVE,
            spec("POST", "/api/comments", {"recipeId": RID, "text": " good "}, response={"id": ID}),
        ],
    ),
    "update_recipe_comment": (
        {"commentId": ID, "text": "edit"},
        [spec("PUT", f"/api/comments/{ID}", {"id": ID, "text": "edit"}, response={"id": ID})],
    ),
    "delete_recipe_comment": (
        {"commentId": ID},
        [spec("DELETE", f"/api/comments/{ID}", response={"message": "Comment deleted"})],
    ),
    "get_recipe_share_links": (
        {"slug": "soup"},
        [
            RESOLVE,
            spec("GET", "/api/shared/recipes", query={"recipe_id": [RID]}, response=[{"id": ID}]),
        ],
    ),
    "create_recipe_share_link": (
        {"slug": "soup", "expiresAt": "2027-01-01T00:00:00Z"},
        [
            RESOLVE,
            spec(
                "POST",
                "/api/shared/recipes",
                {"recipeId": RID, "expiresAt": "2027-01-01T00:00:00Z"},
                response={"id": ID},
            ),
        ],
    ),
    "delete_recipe_share_link": ({"tokenId": ID}, [spec("DELETE", f"/api/shared/recipes/{ID}")]),
    "get_recipe_timeline": (
        {"slug": "soup", "page": 2, "perPage": 5},
        [
            RESOLVE,
            spec(
                "GET",
                "/api/recipes/timeline/events",
                query={"queryFilter": [f"recipeId={RID}"], "page": ["2"], "perPage": ["5"]},
                response={"items": [], "total": 0},
            ),
        ],
    ),
    "create_recipe_timeline_event": (
        {"slug": "soup", "subject": "Made", "eventType": "info", "eventMessage": ""},
        [
            RESOLVE,
            spec(
                "POST",
                "/api/recipes/timeline/events",
                {"recipeId": RID, "subject": "Made", "eventType": "info", "eventMessage": ""},
                response={"id": ID},
            ),
        ],
    ),
    "update_recipe_timeline_event": (
        {"eventId": ID, "subject": "", "eventMessage": None},
        [
            spec(
                "PUT",
                f"/api/recipes/timeline/events/{ID}",
                {"subject": "", "eventMessage": None},
                response={"id": ID},
            )
        ],
    ),
    "delete_recipe_timeline_event": (
        {"eventId": ID},
        [spec("DELETE", f"/api/recipes/timeline/events/{ID}", response={"id": ID})],
    ),
    "set_recipe_timeline_event_image": (
        {"eventId": ID, "imageBase64": BASE64, "extension": "png"},
        [
            spec(
                "PUT",
                f"/api/recipes/timeline/events/{ID}/image",
                {
                    "fields": {"extension": "png"},
                    "files": {
                        "image": {
                            "filename": "image.png",
                            "content_type": "application/octet-stream",
                            "base64": BASE64,
                        }
                    },
                },
                response={"image": "has image"},
            )
        ],
    ),
}


@pytest.mark.parametrize("tool_name", CASES)
async def test_recipe_collaboration_mcp_positive(tool_name):
    arguments, requests = CASES[tool_name]
    with FakeMealie(requests) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        assert not result.is_error
        assert json.loads(result.content[0].text) == requests[-1]["response"]
        assert len(fake.recorded_requests) == len(requests)


@pytest.mark.parametrize("tool_name", CASES)
async def test_recipe_collaboration_mcp_unknown_field_rejected(tool_name):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                tool_name, {**CASES[tool_name][0], "unexpected": True}, raise_on_error=False
            )
        assert result.is_error
        assert not fake.recorded_requests


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("create_recipe_comment", {"slug": "soup", "text": "   "}),
        ("create_recipe_comment", {"slug": "soup", "text": False}),
        ("update_recipe_comment", {"commentId": "../bad", "text": "edit"}),
        ("get_recipe_comments", {"slug": "../bad"}),
        ("create_recipe_share_link", {"slug": "soup", "expiresAt": None}),
        ("create_recipe_share_link", {"slug": "soup", "expiresAt": "yesterday"}),
        (
            "create_recipe_timeline_event",
            {"slug": "soup", "subject": "Made", "eventType": "cooked"},
        ),
        (
            "create_recipe_timeline_event",
            {"slug": "soup", "subject": "Made", "eventType": "info", "timestamp": None},
        ),
        ("update_recipe_timeline_event", {"eventId": ID, "eventMessage": "requires subject"}),
        ("update_recipe_timeline_event", {"eventId": ID, "subject": "x", "eventType": "info"}),
        ("get_recipe_timeline", {"slug": "soup", "page": True}),
        ("get_recipe_timeline", {"slug": "soup", "perPage": 0}),
        ("set_recipe_timeline_event_image", {"eventId": ID, "imageBase64": "!invalid"}),
        (
            "set_recipe_timeline_event_image",
            {"eventId": ID, "imageBase64": BASE64, "extension": "../png"},
        ),
    ],
)
async def test_recipe_collaboration_mcp_invalid_arguments_rejected(tool_name, arguments):
    with FakeMealie([]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(tool_name, arguments, raise_on_error=False)
        assert result.is_error
        assert not fake.recorded_requests
