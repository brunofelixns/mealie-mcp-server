import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/generate_docs.py"


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
