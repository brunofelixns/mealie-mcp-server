"""Mealie 3.29 PUT requires identifiers and a preserved full shopping record."""

import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.api import shopping_lists as api
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError


@pytest.mark.parametrize("kind", ["list", "item"])
async def test_partial_shopping_updates_preserve_required_and_unknown_fields(kind):
    current = {
        "id": "record",
        "name": "before",
        "groupId": "group",
        "userId": "user",
        "shoppingListId": "list",
        "quantity": 2,
        "checked": False,
        "listItems": [{"id": "existing-item", "note": "keep"}],
        "extras": {"unknown-provider-field": "keep"},
    }
    changes = {"name": "renamed"} if kind == "list" else {"quantity": 0, "checked": True}
    writes = []

    def provider(request):
        if request.method == "GET":
            return httpx.Response(200, json=current)
        submitted = json.loads(request.content)
        required = ["groupId", "userId", "id"] if kind == "list" else ["shoppingListId"]
        if any(key not in submitted for key in required):
            return httpx.Response(422, json={"detail": "required shopping identifiers missing"})
        writes.append(submitted)
        return httpx.Response(200, json=submitted)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(provider)) as client:
        function = api.update_shopping_list if kind == "list" else api.update_shopping_list_item
        result = await function(client, "record", changes)
    assert len(writes) == 1
    assert result == {**current, **changes}
    assert writes[0]["extras"] == current["extras"]
    assert writes[0]["listItems"] == current["listItems"]


@pytest.mark.parametrize("kind", ["list", "item"])
@pytest.mark.parametrize("status,body", [(404, {"detail": "missing"}), (200, [])])
async def test_failed_shopping_read_never_writes(kind, status, body):
    requests = []

    def provider(request):
        requests.append(request.method)
        return httpx.Response(status, json=body)

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(provider)) as client:
        function = api.update_shopping_list if kind == "list" else api.update_shopping_list_item
        with pytest.raises(MealieApiError if status == 404 else ValueError):
            await function(client, "record", {})
    assert requests == ["GET"]


@pytest.mark.parametrize("kind", ["list", "item"])
async def test_failed_shopping_write_is_not_retried(kind):
    requests = []

    def provider(request):
        requests.append(request.method)
        return (
            httpx.Response(200, json={"id": "record"})
            if request.method == "GET"
            else httpx.Response(500)
        )

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(provider)) as client:
        function = api.update_shopping_list if kind == "list" else api.update_shopping_list_item
        with pytest.raises(MealieApiError):
            await function(client, "record", {})
    assert requests == ["GET", "PUT"]


@pytest.mark.parametrize("ids", [["first", "second"], ["only"], []])
async def test_bulk_delete_uses_repeated_uuid_query_parameters(ids):
    requests = []

    def provider(request):
        requests.append(request)
        assert request.method == "DELETE"
        assert request.url.params.get_list("ids") == ids
        return httpx.Response(200, json={"message": "deleted"})

    settings = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
    async with MealieClient(settings, transport=httpx.MockTransport(provider)) as client:
        await api.delete_shopping_list_items_bulk(client, ids)
    assert len(requests) == 1
