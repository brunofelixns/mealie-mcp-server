import base64

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from mealie_mcp_server.support import recipe_image
from mealie_mcp_server.tools.registry import definitions
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("recipe_images")
PNG = b"\x89PNG\r\n\x1a\n\x01\x02\x03"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_recipe_images_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:3], ids=lambda case: case.tool)
async def test_unknown_input_rejected_before_download_or_mealie(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert case.tool in {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests


async def test_native_file_tool_upload_and_metadata_with_injected_download(monkeypatch):
    """Positive Python MCP call; injected download bytes are separate from the wire oracle."""
    downloads = []

    async def download(url, max_bytes):
        downloads.append((url, max_bytes))
        return PNG

    monkeypatch.setattr(recipe_image, "download_bounded", download)
    body = {
        "fields": {"extension": "png"},
        "files": {
            "image": {
                "filename": "image.png",
                "content_type": "application/octet-stream",
                "base64": base64.b64encode(PNG).decode(),
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
        async with Client(create_server(settings)) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert tools["set_recipe_image_from_file"].meta == {"openai/fileParams": ["file"]}
            for name in ("set_recipe_image", "set_recipe_image_from_url"):
                assert not (tools[name].meta or {}).get("openai/fileParams")
            result = await client.call_tool(
                "set_recipe_image_from_file",
                {
                    "slug": "soup",
                    "file": {
                        "download_url": "https://files.example.test/a",
                        "file_id": "f1",
                        "mime_type": "image/jpeg",
                        "file_name": "wrong.gif",
                    },
                },
                raise_on_error=False,
            )
        assert not result.is_error
        assert downloads == [("https://files.example.test/a", 10 * 1024 * 1024)]


async def test_curated_metadata_is_preserved_without_framework_additions():
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            for tool in await client.list_tools():
                assert tool.meta == definitions()[tool.name].meta
