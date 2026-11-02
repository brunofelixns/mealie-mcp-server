import copy
import json
from pathlib import Path

import pytest
from fastmcp import Client

from mealie_mcp_server import version
from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie
from tests.support.version import PROJECT_VERSION

FIXTURES = Path(__file__).parents[1] / "fixtures/compatibility"
SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills/mealie"
ORIGINAL = json.loads((FIXTURES / "catalog.json").read_text())["tools"]
DIFFERENCES = json.loads((FIXTURES / "catalog-differences.json").read_text())


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_full_catalog_preserves_all_fields_and_order(mode):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings), mode=mode) as client:
            tools = await client.list_tools()
    assert len(tools) == 78
    assert [tool.name for tool in tools] == [tool["name"] for tool in ORIGINAL]
    expected = copy.deepcopy(ORIGINAL)
    if mode == "auto":
        assert DIFFERENCES["D01"]["modernToolExecution"] == "omitted_by_protocol"
        for tool in expected:
            assert tool.pop("execution") == DIFFERENCES["D01"]["legacyToolExecution"]
    assert [
        tool.model_dump(mode="json", by_alias=True, exclude_unset=True) for tool in tools
    ] == expected
    assert [tool.name for tool in tools if (tool.meta or {}).get("openai/fileParams")] == [
        "set_recipe_image_from_file"
    ]


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_identity_and_native_protocol_capabilities_are_declared(mode):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings), mode=mode) as client:
            assert client.server_info.name == "mealie-mcp-server"
            assert client.server_info.version == version() == PROJECT_VERSION
            assert DIFFERENCES["D04"]["originalServerVersion"] == "1.0.0"
            capability_key = (
                "pythonLegacyCapabilities" if mode == "legacy" else "pythonModernCapabilities"
            )
            # D12 adds Skills without changing the immutable migration baseline.
            expected_capabilities = copy.deepcopy(DIFFERENCES["D01"][capability_key])
            if mode == "auto":
                expected_capabilities["extensions"]["io.modelcontextprotocol/skills"] = {}
            assert (
                client.server_capabilities.model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                )
                == expected_capabilities
            )
            assert DIFFERENCES["D01"]["pythonResources"] == []
            expected_resources = {
                "skill://mealie/" + path.relative_to(SKILL_ROOT).as_posix()
                for path in SKILL_ROOT.rglob("*")
                if path.is_file()
            } | {"skill://mealie/_manifest"}
            assert {str(resource.uri) for resource in await client.list_resources()} == (
                expected_resources
            )
    original = json.loads((FIXTURES / "upstream-manifest.json").read_text())
    assert original["capabilities"] == DIFFERENCES["D01"]["originalLegacyCapabilities"]
    assert original["resources"] == DIFFERENCES["D01"]["originalResources"]
