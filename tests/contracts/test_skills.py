import pytest
from fastmcp import Client
from fastmcp.skills import SkillsClientExtension
from mcp.shared.exceptions import MCPError

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie
from tests.support.skills import EXTENSION, ROOT, SKILL_URI, assert_skill_bytes


def configuration(fake):
    return load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})


async def test_skills_discovery_direct_lookup_and_complete_byte_manifest():
    with FakeMealie("no_requests") as fake:
        async with Client(
            create_server(configuration(fake)), extensions=[SkillsClientExtension()]
        ) as client:
            assert client.server_capabilities.extensions[EXTENSION] == {}
            await assert_skill_bytes(client)
        assert fake.recorded_requests == []


async def test_known_uri_can_be_loaded_before_listing():
    with FakeMealie("no_requests") as fake:
        async with Client(
            create_server(configuration(fake)), extensions=[SkillsClientExtension()]
        ) as client:
            entry = await client.get_skill(SKILL_URI)
            assert entry.uri == SKILL_URI
            assert (await client.read_resource(entry.uri))[0].mime_type == "text/markdown"


@pytest.mark.parametrize(
    "uri",
    [
        "skill://missing/SKILL.md",
        "skill://mealie/references/recipes.md",
        "skill://mealie/../SKILL.md",
        "skill://mealie/%2e%2e/SKILL.md",
        "file:///etc/passwd",
    ],
)
async def test_unknown_or_invalid_skill_uri_is_invalid_params(uri):
    with FakeMealie("no_requests") as fake:
        async with Client(
            create_server(configuration(fake)), extensions=[SkillsClientExtension()]
        ) as client:
            with pytest.raises(MCPError) as error:
                await client.get_skill(uri)
            assert error.value.code == -32602


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_clients_without_extension_can_read_skill_resources(mode):
    with FakeMealie("no_requests") as fake:
        async with Client(create_server(configuration(fake)), mode=mode) as client:
            resources = await client.list_resources()
            assert SKILL_URI in {str(resource.uri) for resource in resources}
            raw = (await client.read_resource(SKILL_URI))[0].text.encode("utf-8")
            assert raw == (ROOT / "skills/mealie/SKILL.md").read_bytes()
            assert len(await client.list_tools()) == 78
            assert [prompt.name for prompt in await client.list_prompts()] == ["weekly-meal-plan"]


@pytest.mark.parametrize(
    "uri",
    [
        "skill://mealie/missing.md",
        "skill://mealie/../../pyproject.toml",
        "skill://mealie/%2e%2e/%2e%2e/pyproject.toml",
        "skill://mealie/references/%2fetc%2fpasswd",
        "file:///etc/passwd",
    ],
)
async def test_resources_do_not_expose_files_outside_the_skill(uri):
    with FakeMealie("no_requests") as fake:
        async with Client(create_server(configuration(fake))) as client:
            with pytest.raises(MCPError) as error:
                await client.read_resource(uri)
            assert error.value.code == -32602
