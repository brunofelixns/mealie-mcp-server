import sys

import httpx2 as httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.skills import SkillsClientExtension

from mealie_mcp_server.http import create_http_app
from mealie_mcp_server.server import create_server
from tests.integration.test_http import AUTH, settings_for
from tests.integration.test_stdio import environment
from tests.support.fake_mealie import FakeMealie
from tests.support.http_server import serve_http
from tests.support.skills import ROOT, SKILL_URI, assert_skill_bytes


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_skill_resources_over_real_stdio(mode):
    with FakeMealie("no_requests") as fake:
        transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mealie_mcp_server"],
            env=environment(fake),
        )
        async with Client(
            transport, mode=mode, extensions=[SkillsClientExtension()], timeout=25
        ) as client:
            raw = (await client.read_resource(SKILL_URI))[0].text.encode("utf-8")
            assert raw == (ROOT / "skills/mealie/SKILL.md").read_bytes()
            if mode == "auto":
                await assert_skill_bytes(client)
        assert fake.recorded_requests == []


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_skills_over_authenticated_http_and_no_public_skill_reads(mode):
    with FakeMealie("no_requests") as fake:
        settings = settings_for(fake)
        async with serve_http(create_http_app(create_server(settings), settings)) as url:
            async with httpx.AsyncClient() as http:
                for method, params in (
                    ("skills/list", {}),
                    ("skills/get", {"uri": SKILL_URI}),
                    ("resources/read", {"uri": SKILL_URI}),
                ):
                    for headers in ({}, {"Authorization": "Bearer wrong"}):
                        response = await http.post(
                            url + "/mcp",
                            headers=headers,
                            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                        )
                        assert response.status_code == 401
            async with Client(
                url + "/mcp",
                auth=AUTH["Authorization"].removeprefix("Bearer "),
                mode=mode,
                extensions=[SkillsClientExtension()],
                timeout=25,
            ) as client:
                assert (await client.read_resource(SKILL_URI))[0].text.encode("utf-8") == (
                    ROOT / "skills/mealie/SKILL.md"
                ).read_bytes()
                if mode == "auto":
                    await assert_skill_bytes(client)
        assert fake.recorded_requests == []
