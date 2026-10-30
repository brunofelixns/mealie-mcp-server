import copy
import json
from pathlib import Path

import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.fake_mealie import FakeMealie
from tests.support.version import PROJECT_VERSION

FIXTURES = Path(__file__).parents[1] / "fixtures/compatibility"
ORIGINAL = json.loads((FIXTURES / "prompts.json").read_text())
DIFFERENCES = json.loads((FIXTURES / "catalog-differences.json").read_text())
DIFFERENCE = DIFFERENCES["D05"]


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("preferences", [None, "vegetarian", "", " "])
async def test_weekly_prompt_preserves_messages_roles_and_confirmation(mode, preferences):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings), mode=mode) as client:
            prompts = await client.list_prompts()
            assert [
                prompt.model_dump(mode="json", by_alias=True, exclude_unset=True)
                for prompt in prompts
            ] == ORIGINAL["prompts"]
            result = await client.get_prompt(
                "weekly-meal-plan", {} if preferences is None else {"preferences": preferences}
            )
    expected = copy.deepcopy(ORIGINAL["expanded"])
    expected["messages"][0]["content"]["text"] = expected["messages"][0]["content"]["text"].replace(
        DIFFERENCE["promptOriginal"], DIFFERENCE["promptPython"]
    )
    if preferences:
        expected["messages"][1]["content"]["text"] += " My preferences are: " + preferences
    if mode == "auto":
        expected.update(copy.deepcopy(DIFFERENCES["D01"]["modernResultEnvelope"]))
        # D04: release metadata changes; the immutable capture and all other fields remain.
        expected["_meta"]["io.modelcontextprotocol/serverInfo"]["version"] = PROJECT_VERSION
    assert result.model_dump(mode="json", by_alias=True, exclude_unset=True) == expected
    assert [message.role for message in result.messages] == ["assistant", "user"]
    assert (
        "Before saving to Mealie, display the complete meal plan for confirmation"
        in result.messages[0].content.text
    )
