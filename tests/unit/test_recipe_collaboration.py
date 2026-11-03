import base64
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.services import recipe_collaboration as service

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
RID = "11111111-1111-4111-8111-111111111111"
ID = "22222222-2222-4222-8222-222222222222"
PNG = b"\x89PNG\r\n\x1a\nhello"


async def test_comment_create_resolves_slug_and_uses_authenticated_user():
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            assert request.url.path == "/api/recipes/soup"
            return httpx.Response(200, json={"id": RID})
        assert request.url.path == "/api/comments"
        assert json.loads(request.content) == {"recipeId": RID, "text": "good"}
        return httpx.Response(201, json={"id": ID, "extra": False})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.create_recipe_comment(client, "soup", "good") == {
            "id": ID,
            "extra": False,
        }
    assert [call.method for call in calls] == ["GET", "POST"]


async def test_comment_listing_preserves_unknown_fields_and_order():
    expected = [{"id": ID, "text": "", "unknown": []}, {"id": RID, "other": None}]

    def handle(request):
        assert request.url.path == "/api/recipes/soup/comments"
        return httpx.Response(200, json=expected)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.get_recipe_comments(client, "soup") == expected


@pytest.mark.parametrize("operation", ["update", "delete"])
@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_comment_write_permissions_and_unknown_outcome_are_not_retried(operation, failure):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.path == f"/api/comments/{ID}"
        if operation == "update":
            assert json.loads(request.content) == {"id": ID, "text": "edit"}
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Comment does not belong to user"})

    error = MealieApiError if failure == "permission" else MealieTransportError
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(error):
            if operation == "update":
                await service.update_recipe_comment(client, ID, "edit")
            else:
                await service.delete_recipe_comment(client, ID)
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [{}, {"expiresAt": "2027-01-01T00:00:00Z"}])
async def test_share_create_omits_unspecified_expiry(changes):
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"id": RID})
        assert request.url.path == "/api/shared/recipes"
        assert json.loads(request.content) == {"recipeId": RID, **changes}
        return httpx.Response(201, json={"id": ID})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.create_recipe_share_link(client, "soup", changes) == {"id": ID}
    assert len(calls) == 2


async def test_share_listing_uses_provider_snake_case_query():
    def handle(request):
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json={"id": RID})
        assert request.url.path == "/api/shared/recipes"
        assert dict(request.url.params) == {"recipe_id": RID}
        return httpx.Response(200, json=[{"id": ID, "extra": 0}])

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.get_recipe_share_links(client, "soup") == [{"id": ID, "extra": 0}]


async def test_share_delete_preserves_null_response():
    def handle(request):
        assert request.method == "DELETE"
        assert request.url.path == f"/api/shared/recipes/{ID}"
        return httpx.Response(200, content=b"null", headers={"content-type": "application/json"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.delete_recipe_share_link(client, ID) is None


async def test_timeline_filtered_pagination_and_provider_payload_are_preserved():
    result = {"items": [{"eventMessage": None, "other": False}], "total": 1, "next": None}

    def handle(request):
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json={"id": RID})
        assert request.url.path == "/api/recipes/timeline/events"
        assert dict(request.url.params) == {
            "queryFilter": f"recipeId={RID}",
            "page": "2",
            "perPage": "5",
        }
        return httpx.Response(200, json=result)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert (
            await service.get_recipe_timeline(client, "soup", {"page": 2, "perPage": 5}) == result
        )


async def test_timeline_create_and_update_preserve_omission_null_and_empty_message():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path == "/api/recipes/soup":
            return httpx.Response(200, json={"id": RID})
        body = json.loads(request.content)
        if request.method == "POST":
            assert body == {
                "recipeId": RID,
                "subject": "Made",
                "eventType": "info",
                "eventMessage": "",
            }
        else:
            assert request.url.path == f"/api/recipes/timeline/events/{ID}"
            assert body == {"subject": "", "eventMessage": None}
        return httpx.Response(200, json={"id": ID, "unknown": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        await service.create_recipe_timeline_event(
            client, "soup", {"subject": "Made", "eventType": "info", "eventMessage": ""}
        )
        assert await service.update_recipe_timeline_event(
            client, ID, {"subject": "", "eventMessage": None}
        ) == {"id": ID, "unknown": []}
    assert len(calls) == 3


async def test_timeline_image_upload_uses_bounded_bytes_and_multipart():
    def handle(request):
        assert request.method == "PUT"
        assert request.url.path == f"/api/recipes/timeline/events/{ID}/image"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b'name="extension"\r\n\r\npng' in request.content
        assert PNG in request.content
        return httpx.Response(200, json={"image": "has image"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await service.set_recipe_timeline_event_image(
            client, ID, base64.b64encode(PNG).decode(), "png"
        ) == {"image": "has image"}


@pytest.mark.parametrize("payload", ["!invalid", "", "A" * (14 * 1024 * 1024)])
async def test_invalid_or_oversize_timeline_image_rejected_before_http(payload):
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda request: pytest.fail("HTTP"))
    ) as client:
        with pytest.raises(ValueError):
            await service.set_recipe_timeline_event_image(client, ID, payload, None)


@pytest.mark.parametrize("recipe", [{}, {"id": "../bad"}, [], {"id": 1}])
async def test_invalid_recipe_id_does_not_lead_to_writes(recipe):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=recipe)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError):
            await service.create_recipe_comment(client, "soup", "comment")
    assert len(calls) == 1


@pytest.mark.parametrize(
    "operation",
    ["create_share", "delete_share", "create_event", "update_event", "delete_event", "event_image"],
)
async def test_share_and_timeline_unknown_write_outcomes_never_retry(operation):
    writes = []

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json={"id": RID})
        writes.append(request)
        raise httpx.ReadTimeout("unknown outcome", request=request)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieTransportError, match="Write outcome may be unknown"):
            if operation == "create_share":
                await service.create_recipe_share_link(client, "soup", {})
            elif operation == "delete_share":
                await service.delete_recipe_share_link(client, ID)
            elif operation == "create_event":
                await service.create_recipe_timeline_event(
                    client, "soup", {"subject": "Made", "eventType": "info"}
                )
            elif operation == "update_event":
                await service.update_recipe_timeline_event(client, ID, {"subject": "Edit"})
            elif operation == "delete_event":
                await service.delete_recipe_timeline_event(client, ID)
            else:
                await service.set_recipe_timeline_event_image(
                    client, ID, base64.b64encode(PNG).decode(), None
                )
    assert len(writes) == 1


@pytest.mark.parametrize(
    "payload",
    [
        base64.b64encode(b"unsupported").decode(),
        base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024)).decode(),
    ],
)
async def test_decoded_image_type_and_size_rejected_before_http(payload):
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda request: pytest.fail("HTTP"))
    ) as client:
        with pytest.raises(ValueError):
            await service.set_recipe_timeline_event_image(client, ID, payload, None)


async def test_image_extension_mismatch_rejected_before_http():
    async with MealieClient(
        SETTINGS, transport=httpx.MockTransport(lambda request: pytest.fail("HTTP"))
    ) as client:
        with pytest.raises(ValueError, match="extension"):
            await service.set_recipe_timeline_event_image(
                client, ID, base64.b64encode(PNG).decode(), "jpg"
            )
