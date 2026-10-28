import asyncio

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.api.recipes import get_recipes_batch
from mealie_mcp_server.mealie.client import MealieClient

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize("count", [10, 26])
async def test_batch_bounds_concurrency_preserves_mapping_and_isolates_errors(count):
    active = peak = 0
    requests = []

    async def handle(request):
        nonlocal active, peak
        slug = request.url.path.rsplit("/", 1)[-1]
        requests.append(slug)
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02 if slug == "r0" else 0.005)
        active -= 1
        if slug == "r1":
            return httpx.Response(404, json={"detail": "private body"})
        return httpx.Response(200, json={"slug": slug, "nutrition": {"keep": True}})

    slugs = [f"r{i}" for i in range(count)] + ["r0"]
    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await get_recipes_batch(client, slugs)
    assert len(requests) == len(slugs)
    assert 1 < peak <= 4
    assert list(result) == [f"r{i}" for i in range(count)]
    assert result["r0"] == {"slug": "r0", "nutrition": {"keep": True}}
    assert result["r1"] == {"error": "Mealie API error 404."}


async def test_empty_batch_and_invalid_slug_do_not_call_http():
    def handle(request):
        pytest.fail("unexpected HTTP")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await get_recipes_batch(client, []) == {}
        assert await get_recipes_batch(client, [".."]) == {"..": {"error": "Invalid slug."}}
