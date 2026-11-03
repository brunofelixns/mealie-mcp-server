"""Every public tool rejects an extra root field before any Mealie request."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from mealie_mcp_server.tools.registry import definitions
from tests.support.contracts import FIXTURES, load_cases
from tests.support.fake_mealie import FakeMealie

BASE = {}
for path in sorted((FIXTURES / "cases").glob("*.json")):
    for case in load_cases(path.stem):
        BASE.setdefault(case.tool, case.arguments)

for entry in json.loads(
    (
        Path(__file__).resolve().parents[2] / "docs/migration/compatibility-inventory.json"
    ).read_text()
)["tools"]:
    if "extensionArguments" in entry:
        BASE[entry["name"]] = entry["extensionArguments"]


@pytest.mark.parametrize("name", definitions())
async def test_all_tools_reject_unknown_field_without_provider_side_effects(name):
    assert set(BASE) == set(definitions()) and name in BASE
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                name,
                {**BASE[name], "migrationUnexpectedField": "private-sentinel-must-not-echo"},
                raise_on_error=False,
            )
        assert result.is_error
        assert "migrationUnexpectedField" in result.content[0].text
        assert "private-sentinel-must-not-echo" not in result.content[0].text
        assert not fake.recorded_requests
