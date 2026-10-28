"""Check declarative compatibility evidence and independent coverage thresholds.

This validates the index; execution evidence comes from pytest and phase reports.
It never recaptures or rewrites upstream fixtures to make a check pass.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(
    inventory_path: Path,
    require_all: bool,
    coverage_path: Path | None,
    junit_path: Path | None = None,
) -> dict:
    inventory = json.loads(inventory_path.read_text())
    catalog = json.loads((ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    state = json.loads((ROOT / "docs/migration/implementation-state.json").read_text())
    names = {tool["name"] for tool in catalog["tools"]}
    if len(names) != 78 or names != {tool["name"] for tool in inventory["tools"]}:
        raise ValueError("Inventory and public catalog must contain exactly the same 78 tools")
    if any(
        tool["inputSchema"].get("additionalProperties") is not False for tool in catalog["tools"]
    ):
        raise ValueError("All public root inputs must be strict")
    owners = [name for task in state["tasks"] for name in task["tools"]]
    if len(owners) != len(set(owners)) or set(owners) != names:
        raise ValueError("Every tool must have exactly one implementation owner")
    if len(state["upstreamLibraries"]) != 21 or len(state["upstreamTests"]) != 42:
        raise ValueError("Upstream library/test ownership is incomplete")
    if require_all and any(
        tool["migrationStatus"] != "implemented_contract_verified" for tool in inventory["tools"]
    ):
        raise ValueError("Some tools remain unverified")
    positive = set()
    represented = set()
    positive_sources = []
    cases = 0
    for path in (ROOT / "tests/fixtures/compatibility/cases").glob("*.json"):
        for case in json.loads(path.read_text()):
            cases += 1
            represented.add(case["tool"])
            result = case.get("expected_python_result", case["expected_result"])
            if "content" in result and not result.get("isError") and case["expected_requests"]:
                positive.add(case["tool"])
                positive_sources.append((case["tool"], case["scenario"]))
    captured_positive = len(positive)
    additional = []
    for tool in inventory["tools"]:
        if tool["name"] in positive:
            continue
        for example in tool.get("runtimeExamples", []):
            if example.get("provenance") == "python_native_mcp_with_injected_download":
                path = ROOT / example["file"]
                if "async def " + example["test"] + "(" not in path.read_text():
                    raise ValueError("Missing declared Python positive test")
                positive.add(tool["name"])
                additional.append({**example, "tool": tool["name"]})
    rejection = ROOT / "tests/contracts/test_complete_rejections.py"
    if not rejection.exists() or "definitions()" not in rejection.read_text():
        raise ValueError("Missing full-catalog rejection test")
    if require_all and positive != names:
        raise ValueError("Missing positive MCP evidence: " + ", ".join(sorted(names - positive)))
    negative = names & represented
    if junit_path:
        passed = [
            case.get("name", "")
            for case in ET.parse(junit_path).getroot().iter("testcase")
            if not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
        ]
        positive = {
            name
            for name, scenario in positive_sources
            if any("[" + scenario + "]" in test for test in passed)
        }
        positive.update(example["tool"] for example in additional if example["test"] in passed)
        prefix = "test_all_78_tools_reject_unknown_field_without_provider_side_effects["
        negative = {
            test[len(prefix) : -1]
            for test in passed
            if test.startswith(prefix) and test.endswith("]")
        }
        if require_all and (positive != names or negative != names):
            raise ValueError(
                "Missing executed MCP evidence: positive="
                + ",".join(sorted(names - positive))
                + "; negative="
                + ",".join(sorted(names - negative))
            )
    report = {
        "tools": len(names),
        "positiveTools": len(positive),
        "negativeTools": len(negative),
        "executionEvidence": str(junit_path)
        if junit_path
        else "declared test index; run pytest for execution evidence",
        "capturedCases": cases,
        "positiveCapturedTools": captured_positive,
        "additionalPythonPositiveTests": additional,
        "upstreamLibraries": 21,
        "upstreamTestFiles": 42,
    }
    if coverage_path:
        totals = json.loads(coverage_path.read_text())["totals"]
        lines = 100 * totals["covered_lines"] / totals["num_statements"]
        branches = 100 * totals["covered_branches"] / totals["num_branches"]
        report["coverage"] = {"lines": lines, "branches": branches}
        if lines < 90 or branches < 85:
            raise ValueError(
                "Coverage requires lines >=90 and branches >=85; "
                f"observed {lines:.2f}/{branches:.2f}"
            )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=ROOT / "docs/migration/compatibility-inventory.json"
    )
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--junit-xml", type=Path)
    args = parser.parse_args()
    try:
        report = check(args.inventory, args.require_all, args.coverage_json, args.junit_xml)
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, ET.ParseError) as error:
        print("Compatibility check: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
