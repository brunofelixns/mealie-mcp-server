import asyncio
import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.recipe_rating import set_recipe_rating

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize(
    "changes", [{"rating": None}, {"isFavorite": False}, {"rating": 0.5}, {"rating": 5}]
)
async def test_payload_presence_and_readback_preserve_user_summary(changes):
    writes = []

    def handle(request):
        path = request.url.path
        if path == "/api/users/self":
            return httpx.Response(200, json={"id": "u"})
        if request.method == "POST":
            writes.append(json.loads(request.content))
            return httpx.Response(204)
        if path.startswith("/api/recipes/"):
            return httpx.Response(200, json={"id": "r", "rating": 0})
        return httpx.Response(
            200, json={"recipeId": "r", "rating": 0, "isFavorite": False, "extra": {"keep": True}}
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await set_recipe_rating(client, "soup", changes)
    expected = {**changes}
    if "rating" in expected and expected["rating"] is None:
        expected["rating"] = 0
    assert writes == [expected]
    assert result == {
        "userRating": {
            "recipeId": "r",
            "rating": None,
            "isFavorite": False,
            "extra": {"keep": True},
        },
        "recipeRating": 0,
    }


async def test_failed_self_lookup_is_not_cached():
    reads = 0

    def handle(request):
        nonlocal reads
        if request.url.path == "/api/users/self":
            reads += 1
            return (
                httpx.Response(503, json={"detail": "private"})
                if reads == 1
                else httpx.Response(200, json={"id": "u"})
            )
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.startswith("/api/recipes/"):
            return httpx.Response(200, json={"id": "r"})
        return httpx.Response(200, json={"recipeId": "r", "rating": 4})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(Exception, match="503"):
            await set_recipe_rating(client, "soup", {"rating": 4})
        result = await set_recipe_rating(client, "soup", {"rating": 4})
    assert reads == 2 and result["userRating"]["rating"] == 4


async def test_two_clients_do_not_share_user_cache():
    user_reads = []
    writes = []

    def handle(request):
        key = request.headers["Authorization"].removeprefix("Bearer ")
        if request.url.path == "/api/users/self":
            user_reads.append(key)
            return httpx.Response(200, json={"id": key})
        if request.method == "POST":
            writes.append(request.url.path)
            return httpx.Response(204)
        if request.url.path.startswith("/api/recipes/"):
            return httpx.Response(200, json={"id": "r"})
        return httpx.Response(200, json={"recipeId": "r"})

    first = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "one"})
    second = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "two"})
    async with (
        MealieClient(first, transport=httpx.MockTransport(handle)) as a,
        MealieClient(second, transport=httpx.MockTransport(handle)) as b,
    ):
        await set_recipe_rating(a, "soup", {"isFavorite": False})
        await set_recipe_rating(b, "soup", {"isFavorite": True})
        await set_recipe_rating(a, "soup", {"rating": 4})
    assert user_reads == ["one", "two"]
    assert writes == [
        "/api/users/one/ratings/soup",
        "/api/users/two/ratings/soup",
        "/api/users/one/ratings/soup",
    ]


async def test_cancelled_waiter_does_not_cancel_shared_identity_lookup():
    entered = asyncio.Event()
    release = asyncio.Event()
    reads = 0

    async def handle(request):
        nonlocal reads
        if request.url.path == "/api/users/self":
            reads += 1
            entered.set()
            await release.wait()
            return httpx.Response(200, json={"id": "u"})
        if request.method == "POST":
            return httpx.Response(204)
        if request.url.path.startswith("/api/recipes/"):
            return httpx.Response(200, json={"id": "r"})
        return httpx.Response(200, json={"recipeId": "r", "rating": 4})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        a = asyncio.create_task(set_recipe_rating(client, "a", {"rating": 4}))
        await asyncio.wait_for(entered.wait(), 2)
        b = asyncio.create_task(set_recipe_rating(client, "b", {"rating": 4}))
        a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await a
        release.set()
        result = await asyncio.wait_for(b, 2)
    assert reads == 1 and result["userRating"]["rating"] == 4


async def test_closing_client_cancels_pending_identity_lookup():
    entered = asyncio.Event()
    active = 0

    async def handle(request):
        nonlocal active
        active += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            active -= 1

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        task = asyncio.create_task(set_recipe_rating(client, "soup", {"rating": 4}))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert active == 0


@pytest.mark.parametrize("rating", [0, -1, 5.5, 2.3])
async def test_invalid_rating_never_calls_mealie(rating):
    def handle(request):
        pytest.fail("Should reject rating before HTTP")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="rating must be between"):
            await set_recipe_rating(client, "soup", {"rating": rating})
