import json

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError
from mealie_mcp_server.models.inputs.recipe_collections import (
    CreateCookbookInput,
    UpdateCookbookInput,
)
from mealie_mcp_server.services import recipe_collections as service

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})
ID = "22222222-2222-4222-8222-222222222222"


async def test_cookbook_update_accepts_only_native_name_trimming():
    current = {"id": ID, "name": "Old", "slug": "old", "description": " exact "}

    def handle(request):
        if request.method == "GET":
            return httpx.Response(200, json=current)
        return httpx.Response(200, json={**current, "name": "New", "slug": "new-1"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await service.update_cookbook(client, ID, {"name": " New "})
    assert result["name"] == "New"
    assert result["slug"] == "new-1"


@pytest.mark.parametrize("slug", [None, "custom-slug"])
def test_provider_derived_cookbook_slug_cannot_be_supplied(slug):
    with pytest.raises(ValidationError):
        CreateCookbookInput.model_validate({"name": "Cookbook", "slug": slug})
    with pytest.raises(ValidationError):
        UpdateCookbookInput.model_validate({"cookbookId": ID, "changes": {"slug": slug}})


async def test_cookbook_update_resolves_slug_to_primary_id_and_accepts_native_name_trim():
    current = {"id": ID, "name": "Old", "slug": "old", "public": False, "future": []}
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            assert request.url.path == "/api/households/cookbooks/old"
            return httpx.Response(200, json=current)
        assert request.url.path == f"/api/households/cookbooks/{ID}"
        assert json.loads(request.content) == {**current, "name": " New cookbook "}
        return httpx.Response(200, json={**current, "name": "New cookbook", "slug": "new-cookbook"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await service.update_cookbook(client, "old", {"name": " New cookbook "})
    assert result["name"] == "New cookbook"
    assert result["slug"] == "new-cookbook"
    assert calls == [
        ("GET", "/api/households/cookbooks/old"),
        ("PUT", f"/api/households/cookbooks/{ID}"),
    ]


async def test_cookbook_delete_resolves_slug_to_primary_id():
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            assert request.url.path == "/api/households/cookbooks/old"
            return httpx.Response(200, json={"id": ID, "name": "Old", "slug": "old"})
        assert request.url.path == f"/api/households/cookbooks/{ID}"
        return httpx.Response(200, json={"id": ID, "name": "Old", "slug": "old"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert (await service.delete_cookbook(client, "old"))["id"] == ID
    assert calls == [
        ("GET", "/api/households/cookbooks/old"),
        ("DELETE", f"/api/households/cookbooks/{ID}"),
    ]


@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_resolved_cookbook_delete_failure_is_not_replayed(failure):
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"id": ID, "name": "Old", "slug": "old"})
        assert request.url.path == f"/api/households/cookbooks/{ID}"
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            await service.delete_cookbook(client, "old")
    assert [method for method, _ in calls] == ["GET", "DELETE"]


@pytest.mark.parametrize(
    "changes,result",
    [
        ({"name": " New "}, {"name": "Other"}),
        ({"name": " New ", "description": " keep "}, {"name": "New", "description": "keep"}),
        ({"public": False}, {"public": True}),
    ],
)
async def test_cookbook_normalization_does_not_hide_unrelated_mismatches(changes, result):
    calls = []

    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"id": ID, "name": "Old"})
        return httpx.Response(200, json={"id": ID, **result})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="do not replay"):
            await service.update_cookbook(client, ID, changes)
    assert calls == ["GET", "PUT"]


@pytest.mark.parametrize("operation", ["cookbook", "action"])
async def test_put_preserves_unknown_and_native_ownership(operation):
    current = {
        "id": ID,
        "name": "old",
        "title": "old",
        "groupId": ID,
        "householdId": ID,
        "public": False,
        "position": 0,
        "future": [],
    }
    key = "name" if operation == "cookbook" else "title"
    calls = []

    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json=current)
        assert json.loads(request.content) == {**current, key: "new"}
        return httpx.Response(200, json={**current, key: "new"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        fn = service.update_cookbook if operation == "cookbook" else service.update_recipe_action
        result = await fn(client, ID, {key: "new"})
    assert result["future"] == []
    assert calls == ["GET", "PUT"]


@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_explicit_trigger_native_failure_is_never_replayed(failure):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.path == f"/api/households/recipe-actions/{ID}/trigger/soup"
        assert json.loads(request.content) == {"recipe_scale": 2}
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            await service.trigger_recipe_action(client, ID, "soup", {"recipe_scale": 2})
    assert len(calls) == 1


@pytest.mark.parametrize(
    "operation",
    ["create_cookbook", "delete_cookbook", "create_recipe_action", "delete_recipe_action"],
)
@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_collection_writes_native_failures_are_not_replayed(operation, failure):
    calls = []

    def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            if operation == "create_cookbook":
                await service.create_cookbook(client, {"name": "Cookbook"})
            elif operation == "delete_cookbook":
                await service.delete_cookbook(client, ID)
            elif operation == "create_recipe_action":
                await service.create_recipe_action(
                    client, {"actionType": "link", "title": "Recipe", "url": "https://example.test"}
                )
            else:
                await service.delete_recipe_action(client, ID)
    assert len(calls) == 1


async def test_successful_write_with_unexpected_response_is_not_replayed():
    calls = []

    def handle(request):
        calls.append(request.method)
        return httpx.Response(200, json={"id": ID, "name": "Unchanged"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="do not replay"):
            await service.update_cookbook(client, ID, {"name": "Requested"})
    assert calls == ["GET", "PUT"]


@pytest.mark.parametrize("operation", ["cookbook", "action"])
@pytest.mark.parametrize("failure", ["permission", "timeout"])
async def test_put_native_permission_failure_and_timeout_are_not_replayed(operation, failure):
    calls = []

    def handle(request):
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(
                200, json={"id": ID, "name": "Old", "title": "Old", "householdId": ID}
            )
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, json={"detail": "Not owned by household"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(MealieApiError if failure == "permission" else MealieTransportError):
            if operation == "cookbook":
                await service.update_cookbook(client, ID, {"name": "New"})
            else:
                await service.update_recipe_action(client, ID, {"title": "New"})
    assert calls == ["GET", "PUT"]
