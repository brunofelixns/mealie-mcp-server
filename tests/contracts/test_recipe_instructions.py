import pytest
from fastmcp import Client

from mealie_mcp_server.config import load_settings
from mealie_mcp_server.server import create_server
from tests.support.contracts import assert_contract_matches, load_cases
from tests.support.fake_mealie import FakeMealie

CASES = load_cases("recipe_instructions")


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.scenario)
async def test_recipe_instructions_contract(case):
    with FakeMealie(case.scenario) as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        await assert_contract_matches(create_server(settings), case, fake)


@pytest.mark.parametrize("case", CASES[:2], ids=lambda case: case.tool)
async def test_unknown_input_rejected_before_http(case):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        async with Client(create_server(settings)) as client:
            assert case.tool in {tool.name for tool in await client.list_tools()}
            result = await client.call_tool(
                case.tool, {**case.arguments, "unexpected": True}, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests


@pytest.mark.parametrize(
    "changes",
    [
        {"expectedUpdatedAt": ""},
        {"expectedUpdatedAt": None},
        {"instructions": [{"text": "X", "id": "ephemeral"}]},
        {"updateInstructions": [{"index": True, "text": "X"}]},
        {"updateInstructions": [{"index": 0.5, "text": "X"}]},
        {"updateInstructions": [{"index": -1, "text": "X"}]},
        {"instructions": [{"text": "X", "ingredientReferenceIds": ["not-a-uuid"]}]},
        {"addInstructions": [{"text": "X", "noteReferenceIds": []}]},
    ],
)
async def test_instruction_identity_and_strict_inputs_before_http(changes):
    with FakeMealie("no_requests") as fake:
        settings = load_settings({"MEALIE_BASE_URL": fake.server_url, "MEALIE_API_KEY": "fixture"})
        arguments = {"slug": "soup", "expectedUpdatedAt": "token", "instructions": []}
        if "addInstructions" in changes or "updateInstructions" in changes:
            arguments.pop("instructions")
        arguments.update(changes)
        async with Client(create_server(settings)) as client:
            result = await client.call_tool(
                "update_recipe_instructions", arguments, raise_on_error=False
            )
        assert result.is_error and not fake.recorded_requests
