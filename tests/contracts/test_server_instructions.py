import json
from importlib.resources import files
from pathlib import Path

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie


@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_agent_instructions_preserve_baseline_with_explicit_recipe_additions(mode):
    expected = (Path(__file__).parents[1] / "fixtures/compatibility/instructions.txt").read_text()
    changes = json.loads(
        (
            Path(__file__).parents[1] / "fixtures/recipe-extensions/instruction-changes.json"
        ).read_text()
    )
    for change in changes["replacements"]:
        assert expected.count(change["from"]) == 1
        expected = expected.replace(change["from"], change["to"])
    expected = expected.rstrip() + changes["append"]
    expected += (
        Path(__file__).parents[1] / "fixtures/mealie330/instructions-addendum.md"
    ).read_text()
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings), mode=mode) as client:
            assert client.instructions == expected
    assert (
        files("mealie_mcp_server").joinpath("resources/server-instructions.md").read_text()
        == expected
    )
