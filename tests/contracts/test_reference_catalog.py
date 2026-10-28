"""Compare the capture command with an actual pinned upstream process."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.reference


def test_reference_catalog(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/capture_reference.py", "--output", str(tmp_path)],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    catalog = json.loads((tmp_path / "catalog.json").read_text())
    tools = {tool["name"]: tool for tool in catalog["tools"]}
    assert len(tools) == 78
    assert tools["get_recipes"]["inputSchema"]["additionalProperties"] is False
    assert tools["set_recipe_image_from_file"]["_meta"] == {"openai/fileParams": ["file"]}
    assert "openai/fileParams" not in tools["set_recipe_image"].get("_meta", {})
    prompts = json.loads((tmp_path / "prompts.json").read_text())
    assert [prompt["name"] for prompt in prompts["prompts"]] == ["weekly-meal-plan"]
    assert [m["role"] for m in prompts["expanded"]["messages"]] == ["assistant", "user"]
    assert "referenceId" in (tmp_path / "instructions.txt").read_text()
    manifest = json.loads((tmp_path / "upstream-manifest.json").read_text())
    assert manifest["commit"] == "d027e1b4a314d781a322f1f91e37840f01464d77"
    assert manifest["testsExecuted"] is False


async def test_oracle_reads_fake_mealie() -> None:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from tests.support.fake_mealie import FakeMealie

    with FakeMealie("categories.basic") as fake:
        parameters = StdioServerParameters(
            command="docker",
            args=[
                "run",
                "--rm",
                "-i",
                "--network",
                "mealie-mcp-development_default",
                "--env",
                f"MEALIE_BASE_URL={fake.docker_url}",
                "--env",
                "MEALIE_API_KEY=reference-fixture-not-a-real-key",
                "mealie-mcp-reference:upstream-d027e1b",
                "node",
                "dist/index.js",
            ],
        )
        async with Client(parameters, mode="legacy", read_timeout_seconds=30) as client:
            result = await client.call_tool("get_categories", {"page": 1, "perPage": 20})
        assert not result.is_error
        assert json.loads(result.content[0].text) == {
            "items": [{"id": "category-1", "name": "Dinner", "slug": "dinner"}],
            "total": 1,
            "page": 1,
            "size": 20,
        }
        assert fake.recorded_requests == [
            {
                "method": "GET",
                "path": "/api/organizers/categories",
                "query": {"page": ["1"], "perPage": ["20"]},
                "body": None,
            }
        ]
        assert fake.errors == []
