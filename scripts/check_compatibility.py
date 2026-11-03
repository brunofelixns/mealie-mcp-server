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


def _passed_junit_cases(path: Path) -> set[tuple[str, str]]:
    """Only a clean report with unique case identities can prove execution."""
    document = ET.parse(path).getroot()
    passed: set[tuple[str, str]] = set()
    seen: set[tuple[str, str]] = set()
    for node in document.iter():
        if node.tag in {"testsuite", "testsuites"}:
            for attribute in ("failures", "errors"):
                try:
                    count = int(node.get(attribute, "0"))
                except ValueError:
                    raise ValueError("Invalid JUnit failure/error count.") from None
                if count < 0:
                    raise ValueError("Invalid JUnit failure/error count.")
                if count:
                    raise ValueError("JUnit contains failed or errored tests.")
        if node.tag != "testcase":
            continue
        identity = (node.get("classname", ""), node.get("name", ""))
        if not identity[1]:
            raise ValueError("JUnit testcase requires a name.")
        if identity in seen:
            raise ValueError("Duplicate JUnit testcase identity.")
        seen.add(identity)
        if any(node.find(tag) is not None for tag in ("failure", "error")):
            raise ValueError("JUnit contains failed or errored tests.")
        if node.find("skipped") is None:
            passed.add(identity)
    return passed


def _test_module(file: str) -> str:
    return file.removesuffix(".py").replace("/", ".")


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
    baseline = json.loads((ROOT / "tests/fixtures/compatibility/catalog.json").read_text())["tools"]
    original = [
        {key: value for key, value in tool.items() if key != "endpoints"}
        for tool in catalog["tools"][: len(baseline)]
    ]
    if len(baseline) != 78 or original != baseline:
        raise ValueError("The immutable 78-tool baseline definitions and order must be preserved")
    if len(names) != len(catalog["tools"]) or names != {
        tool["name"] for tool in inventory["tools"]
    }:
        raise ValueError("Inventory and public catalog must contain the same unique tools")
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
                # The categories.json sample exercises the comparator itself; the
                # get_categories contract is separately captured in categories_tags.
                function = (
                    "test_core_recipe_contract"
                    if path.stem == "recipes_core"
                    else f"test_{path.stem}_contract"
                )
                positive_sources.append(
                    (
                        case["tool"],
                        f"tests.contracts.test_{path.stem}",
                        f"{function}[{case['scenario']}]",
                    )
                )
    captured_positive = len(positive)
    additional = []
    for tool in inventory["tools"]:
        if tool["name"] in positive:
            continue
        for example in tool.get("runtimeExamples", []):
            if example.get("provenance") in {
                "python_native_mcp_with_injected_download",
                "python_native_mcp_recipe_extension",
            }:
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
    negative = (names & represented) | {
        tool["name"] for tool in inventory["tools"] if "extensionArguments" in tool
    }
    if junit_path:
        passed = _passed_junit_cases(junit_path)
        positive = {name for name, module, test in positive_sources if (module, test) in passed}
        positive.update(
            example["tool"]
            for example in additional
            if any(
                module == _test_module(example["file"])
                and (
                    test == example["test"] or test == example["test"] + "[" + example["tool"] + "]"
                )
                for module, test in passed
            )
        )
        prefix = "test_all_tools_reject_unknown_field_without_provider_side_effects["
        negative = {
            test[len(prefix) : -1]
            for module, test in passed
            if module == "tests.contracts.test_complete_rejections"
            and test.startswith(prefix)
            and test.endswith("]")
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
        "baselineTools": len(baseline),
        "extensionTools": len(names) - len(baseline),
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
