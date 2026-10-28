import base64

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.mealie.client import MealieClient
from tests.support.fake_mealie import FakeMealie


async def test_fixture_compares_multipart_bytes_and_metadata_without_boundary_noise():
    data = b"\x89PNG\r\n\x1a\n\0\xff"
    body = {
        "fields": {"extension": "png"},
        "files": {
            "image": {
                "filename": "image.png",
                "content_type": "application/octet-stream",
                "base64": base64.b64encode(data).decode(),
            }
        },
    }
    spec = {
        "method": "PUT",
        "path": "/api/recipes/soup/image",
        "query": {},
        "body": body,
        "response": {"image": "v1"},
    }
    with FakeMealie([spec]) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with MealieClient(settings) as client:
            result = await client.request(
                "PUT",
                spec["path"],
                data={"extension": "png"},
                files={"image": ("image.png", data, "application/octet-stream")},
            )
        assert result == {"image": "v1"}
        assert fake.recorded_requests[0]["body"] == body
