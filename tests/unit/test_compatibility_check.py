import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_compatibility.py"


@pytest.mark.parametrize("lines,branches,valid", [(90, 85, True), (89, 85, False), (90, 84, False)])
def test_compatibility_checker_enforces_separate_line_and_branch_thresholds(
    tmp_path, lines, branches, valid
):
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "totals": {
                    "num_statements": 100,
                    "covered_lines": lines,
                    "num_branches": 100,
                    "covered_branches": branches,
                }
            }
        )
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--require-all", "--coverage-json", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == (0 if valid else 1), result.stderr
    if valid:
        report = json.loads(result.stdout)
        catalog = json.loads(
            (ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text()
        )
        assert (
            report["tools"]
            == report["positiveTools"]
            == report["negativeTools"]
            == len(catalog["tools"])
        )
        assert report["baselineTools"] == 78
        assert report["coverage"]["lines"] == 90
        assert report["coverage"]["branches"] == 85
    else:
        assert "coverage" in result.stderr.lower()


def test_compatibility_checker_rejects_missing_executed_mcp_evidence(tmp_path):
    junit = tmp_path / "pytest.xml"
    junit.write_text('<testsuites><testsuite tests="0" /></testsuites>')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--require-all", "--junit-xml", str(junit)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Missing executed MCP evidence" in result.stderr
