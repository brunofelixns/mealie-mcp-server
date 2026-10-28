from importlib.resources import files
from pathlib import Path

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_agent_instructions_are_preserved_and_packaged(mode):
    expected = (Path(__file__).parents[1] / "fixtures/compatibility/instructions.txt").read_text()
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings), mode=mode) as client:
            assert client.instructions == expected
    assert (
        files("mealie_mcp_server").joinpath("resources/server-instructions.md").read_text()
        == expected
    )
