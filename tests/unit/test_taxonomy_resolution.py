import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.services.taxonomy_resolution import (
    UnresolvedTaxonomyFilterError,
    resolve_taxonomy_filter,
)

SETTINGS = load_settings({"MEALIE_BASE_URL": "http://mealie.test", "MEALIE_API_KEY": "fixture"})


@pytest.mark.parametrize("values", [None, []])
async def test_absent_and_empty_filter_do_not_fetch(values):
    def handle(request):
        pytest.fail("unexpected catalog fetch")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        assert await resolve_taxonomy_filter(client, "category", values) == values


async def test_filter_priority_is_id_then_name_then_slug_and_deduplicates():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": "a", "name": "Dinner", "slug": "supper"},
                    {"id": "b", "name": "Other", "slug": "dinner"},
                    {"id": "c", "name": "Third", "slug": "dessert"},
                ]
            },
        )

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        result = await resolve_taxonomy_filter(
            client, "category", [" A ", "DINNER", "dessert", "b", " "]
        )
    assert result == ["a", "c", "b"]
    assert len(calls) == 1
    assert calls[0].url.path == "/api/organizers/categories"
    assert calls[0].url.params["perPage"] == "-1"


@pytest.mark.parametrize("values", [[" missing "], ["missing", "other"]])
async def test_unresolved_filter_has_context_and_never_fetches_recipes(values):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"items": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(UnresolvedTaxonomyFilterError) as raised:
            await resolve_taxonomy_filter(client, "tag", values)
    assert raised.value.kind == "tag"
    assert raised.value.values == values
    assert ("remove it" if len(values) == 1 else "remove them") in str(raised.value)
    assert [request.url.path for request in calls] == ["/api/organizers/tags"]
