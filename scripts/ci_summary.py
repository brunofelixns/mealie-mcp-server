"""Render available CI evidence; the existing compatibility check owns pass/fail gates."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def render(artifacts: Path) -> str:
    rows = ["### Runtime verification", "", "| Evidence | Result |", "|---|---|"]
    coverage = artifacts / "coverage.json"
    if coverage.exists():
        totals = json.loads(coverage.read_text())["totals"]
        for name, covered, total, minimum in (
            ("Line coverage", "covered_lines", "num_statements", 90),
            ("Branch coverage", "covered_branches", "num_branches", 85),
        ):
            percent = 100 * totals[covered] / totals[total] if totals[total] else 0
            rows.append(f"| {name} | {percent:.2f}% (required >={minimum}%) |")
    else:
        rows.append("| Coverage | not available; verification may have stopped early |")
    junit = artifacts / "pytest.xml"
    if junit.exists():
        suites = list(ET.parse(junit).getroot().iter("testsuite"))
        counts = {
            key: sum(int(suite.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        rows.append(
            f"| Tests | {counts['tests']} tests, {counts['failures']} failures, "
            f"{counts['errors']} errors, {counts['skipped']} skipped |"
        )
    else:
        rows.append("| Tests | not available; no JUnit report |")
    security = artifacts / "runtime-security.summary.json"
    if security.exists():
        report = json.loads(security.read_text())
        rows.append(
            f"| Image security | {report['fixableHighCritical']} fixable HIGH/CRITICAL, "
            f"{report['secretFindings']} secret findings, "
            f"{report['sbomComponents']} SBOM components |"
        )
    else:
        rows.append("| Image security | not available; no completed scan |")
    rows.extend(["", "See retained reports. Each command's exit status remains authoritative."])
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    (args.artifacts / "verification-summary.md").write_text(render(args.artifacts))
