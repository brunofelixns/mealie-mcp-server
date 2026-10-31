import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/generate_docs.py"


@pytest.mark.parametrize("relative", ["README.md", "docs/README.es.md"])
def test_generated_readme_includes_each_tool_once_and_family_counts_sum_to_78(relative):
    catalog = json.loads((ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    section = (
        (ROOT / relative)
        .read_text()
        .split("<!-- BEGIN GENERATED TOOLS -->", 1)[1]
        .split("<!-- END GENERATED TOOLS -->", 1)[0]
    )
    for tool in catalog["tools"]:
        assert section.count("`" + tool["name"] + "`") == 1, tool["name"]
    coverage = (ROOT / "docs/api-coverage.md").read_text()
    counts = [int(count) for count in re.findall(r"^\| [^|]+ \| (\d+) \|$", coverage, re.M)]
    assert len(counts) == 8 and all(count > 0 for count in counts)
    assert sum(counts) == len(catalog["tools"]) == 78


def test_generator_rejects_unknown_family_without_replacing_readme(tmp_path):
    for relative in (
        "pyproject.toml",
        "src/mealie_mcp_server/resources/tool-catalog.json",
        "docs/migration/compatibility-inventory.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    original = "Manual\n<!-- BEGIN GENERATED TOOLS -->\nold\n<!-- END GENERATED TOOLS -->\n"
    (tmp_path / "README.md").write_text(original)
    inventory_path = tmp_path / "docs/migration/compatibility-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["tools"][0]["group"] = "unknown-family"
    inventory_path.write_text(json.dumps(inventory))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode != 0 and "Unsupported documentation groups" in result.stderr
    assert (tmp_path / "README.md").read_text() == original


def test_generated_docs_are_current_and_describe_all_public_inputs():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    catalog = json.loads((ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    reference = (ROOT / "docs/tools.md").read_text()
    coverage = (ROOT / "docs/api-coverage.md").read_text()
    for tool in catalog["tools"]:
        assert "## " + tool["name"] + "\n" in reference
        assert "`" + tool["name"] + "`" in coverage
        assert json.dumps(tool["inputSchema"], ensure_ascii=False, indent=2) in reference
        assert all(endpoint in coverage for endpoint in tool["endpoints"])


def test_generator_preserves_manual_readme_and_detects_schema_drift(tmp_path):
    for relative in (
        "pyproject.toml",
        "src/mealie_mcp_server/resources/tool-catalog.json",
        "docs/migration/compatibility-inventory.json",
        "docs/README.es.md",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    (tmp_path / "README.md").write_text(
        "Manual introduction\n<!-- BEGIN GENERATED TOOLS -->\nold\n"
        "<!-- END GENERATED TOOLS -->\nManual ending\n"
    )
    (tmp_path / "README.md").chmod(0o444)
    base = [sys.executable, str(SCRIPT), "--root", str(tmp_path)]
    written = subprocess.run(base, capture_output=True, text=True)
    assert written.returncode == 0, written.stderr
    readme = (tmp_path / "README.md").read_text()
    assert readme.startswith("Manual introduction\n") and readme.endswith("Manual ending\n")
    assert subprocess.run([*base, "--check"], capture_output=True).returncode == 0
    path = tmp_path / "src/mealie_mcp_server/resources/tool-catalog.json"
    catalog = json.loads(path.read_text())
    catalog["tools"][0]["inputSchema"]["properties"]["addedDocParam"] = {"type": "string"}
    path.write_text(json.dumps(catalog))
    stale = subprocess.run([*base, "--check"], capture_output=True, text=True)
    assert stale.returncode != 0 and "stale" in stale.stderr.lower()


def test_generator_localizes_both_readmes_and_detects_spanish_catalog_drift(tmp_path):
    for relative in (
        "pyproject.toml",
        "src/mealie_mcp_server/resources/tool-catalog.json",
        "docs/migration/compatibility-inventory.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    for relative in ("README.md", "docs/README.es.md"):
        (tmp_path / relative).write_text(
            "Manual introduction\n<!-- BEGIN GENERATED TOOLS -->\nold\n"
            "<!-- END GENERATED TOOLS -->\nManual ending\n"
        )
    base = [sys.executable, str(SCRIPT), "--root", str(tmp_path)]
    written = subprocess.run(base, capture_output=True, text=True)
    assert written.returncode == 0, written.stderr
    english = (tmp_path / "README.md").read_text()
    spanish_path = tmp_path / "docs/README.es.md"
    spanish = spanish_path.read_text()
    assert "## Available tools (78)" in english
    assert "| Recipes | 26 |" in english and "| Shopping lists | 13 |" in english
    assert "[full schemas](docs/tools.md)" in english
    assert "## Herramientas disponibles (78)" in spanish
    assert "| Recetas | 26 |" in spanish and "| Compras | 13 |" in spanish
    assert "[esquemas completos](tools.md)" in spanish
    assert spanish.startswith("Manual introduction\n") and spanish.endswith("Manual ending\n")
    assert subprocess.run([*base, "--check"], capture_output=True).returncode == 0
    spanish_path.write_text(spanish.replace("`get_recipes`", "`missing_tool`"))
    stale = subprocess.run([*base, "--check"], capture_output=True, text=True)
    assert stale.returncode != 0 and "docs/README.es.md" in stale.stderr
    assert (tmp_path / "README.md").read_text() == english
