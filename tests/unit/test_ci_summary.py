import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/ci_summary.py"


def test_summary_exposes_independent_coverage_and_test_results(tmp_path):
    (tmp_path / "coverage.json").write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": 91,
                    "num_statements": 100,
                    "covered_branches": 87,
                    "num_branches": 100,
                }
            }
        )
    )
    (tmp_path / "pytest.xml").write_text(
        '<testsuites><testsuite tests="8" failures="1" errors="0" skipped="2" '
        'time="3.2"/></testsuites>'
    )
    (tmp_path / "runtime-security.summary.json").write_text(
        json.dumps({"fixableHighCritical": 0, "secretFindings": 0, "sbomComponents": 120})
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--artifacts", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = (tmp_path / "verification-summary.md").read_text()
    assert "91.00%" in report and "90%" in report
    assert "87.00%" in report and "85%" in report
    assert "8" in report and "1 failures" in report and "2 skipped" in report
    assert "120" in report


def test_missing_evidence_is_visible_without_claiming_a_pass(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--artifacts", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = (tmp_path / "verification-summary.md").read_text()
    assert "not available" in report
    assert "PASS" not in report
