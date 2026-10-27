"""Observe real request construction at the external HTTP boundary."""

import json

import httpx2 as httpx
import pytest

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.mealie.errors import MealieApiError, MealieTransportError

SETTINGS = load_settings(
    {
        "MEALIE_BASE_URL": "http://mealie.test/proxy",
        "MEALIE_API_KEY": "fixture-mealie-key",
    }
)


async def test_base_subpath_and_repeated_query_are_preserved() -> None:
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"items": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        result = await client.request(
            "GET",
            "/api/recipes",
            params=[("tags", "a"), ("tags", "b"), ("requireAllTags", "false")],
        )
    assert result == {"items": []}
    assert str(requests[0].url) == (
        "http://mealie.test/proxy/api/recipes?tags=a&tags=b&requireAllTags=false"
    )
    assert requests[0].headers["authorization"] == "Bearer fixture-mealie-key"
    assert requests[0].headers["content-type"] == "application/json"


async def test_absent_body_null_and_explicit_values_are_different() -> None:
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json="new-recipe")

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        assert await client.request("POST", "/api/recipes") == "new-recipe"
        await client.request("POST", "/api/recipes", json=None)
        await client.request("PATCH", "/api/recipes/one", json={"n": 0, "flag": False, "v": []})
    assert bodies[0] == b""
    assert bodies[1] == b"null"
    assert json.loads(bodies[2]) == {"n": 0, "flag": False, "v": []}


async def test_204_does_not_attempt_json_decoding() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        assert await client.request("DELETE", "/api/recipes/one") is None
    assert len(requests) == 1
    assert requests[0].method == "DELETE"


async def test_provider_error_keeps_status_without_exposing_body() -> None:
    async with MealieClient(
        SETTINGS,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                422, json={"detail": "fixture-mealie-key private-recipe"}
            )
        ),
    ) as client:
        with pytest.raises(MealieApiError) as caught:
            await client.request("PUT", "/api/recipes/one", json={})
    assert caught.value.status == 422
    assert "fixture-mealie-key" not in str(caught.value)
    assert "private-recipe" not in repr(caught.value)


async def test_write_timeout_is_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ReadTimeout("private-provider-message", request=request)

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MealieTransportError) as caught:
            await client.request("POST", "/api/recipes", json={"name": "one"})
    assert len(calls) == 1
    assert "private-provider-message" not in str(caught.value)
    assert "unknown" in str(caught.value).lower()


async def test_same_origin_redirect_is_followed() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(307, headers={"location": "/proxy/api/recipes/"})
        return httpx.Response(200, json={"items": []})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        assert await client.request("GET", "/api/recipes") == {"items": []}
    assert calls == [
        "http://mealie.test/proxy/api/recipes",
        "http://mealie.test/proxy/api/recipes/",
    ]


async def test_redirect_to_another_origin_never_sends_a_request_there() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://another.example.test/api/recipes"})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(MealieApiError):
            await client.request("GET", "/api/recipes")
    assert len(calls) == 1


async def test_absolute_endpoint_is_rejected_before_network() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            await client.request("GET", "https://another.example.test/api/recipes")
    assert calls == []


async def test_multipart_uses_its_own_boundary() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    async with MealieClient(SETTINGS, transport=httpx.MockTransport(handler)) as client:
        await client.request(
            "PUT",
            "/api/recipes/one/image",
            data={"extension": "png"},
            files={"image": ("image.png", b"image-fixture", "image/png")},
        )
    assert requests[0].headers["content-type"].startswith("multipart/form-data; boundary=")
    assert b"image-fixture" in requests[0].content
    assert b'name="extension"' in requests[0].content


async def test_client_closes_its_transport_when_caller_raises() -> None:
    class Transport(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.closes = 0

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        async def aclose(self) -> None:
            self.closes += 1

    transport = Transport()
    with pytest.raises(RuntimeError, match="caller-failure"):
        async with MealieClient(SETTINGS, transport=transport) as client:
            assert await client.request("GET", "/api/recipes") == {}
            raise RuntimeError("caller-failure")
    assert transport.closes == 1


async def test_real_http_client_matches_the_reference_fixture() -> None:
    from tests.support.fake_mealie import FakeMealie

    with FakeMealie("categories.basic") as fake:
        settings = load_settings(
            {
                "MEALIE_BASE_URL": fake.server_url,
                "MEALIE_API_KEY": "reference-fixture-not-a-real-key",
            }
        )
        async with MealieClient(settings) as client:
            result = await client.request(
                "GET", "/api/organizers/categories", params=[("page", "1"), ("perPage", "20")]
            )
        assert result == {
            "items": [{"id": "category-1", "name": "Dinner", "slug": "dinner"}],
            "total": 1,
            "page": 1,
            "size": 20,
        }
        assert len(fake.recorded_requests) == 1
