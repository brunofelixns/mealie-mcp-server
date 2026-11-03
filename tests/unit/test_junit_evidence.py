"""Execution evidence must be clean, unique and attributed to the real contract tests."""

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "junit_compatibility", ROOT / "scripts/check_compatibility.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
INVENTORY = ROOT / "docs/migration/compatibility-inventory.json"


@pytest.fixture
def evidence(tmp_path):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", {"name": "contract evidence"})
    identities = set()

    def add(classname, name):
        if (classname, name) not in identities:
            ET.SubElement(suite, "testcase", {"classname": classname, "name": name})
            identities.add((classname, name))

    for path in (ROOT / "tests/fixtures/compatibility/cases").glob("*.json"):
        if path.stem == "categories":
            continue  # comparator sample; get_categories has its own contract below
        function = (
            "test_core_recipe_contract"
            if path.stem == "recipes_core"
            else f"test_{path.stem}_contract"
        )
        for case in json.loads(path.read_text()):
            result = case.get("expected_python_result", case["expected_result"])
            if "content" in result and not result.get("isError") and case["expected_requests"]:
                add(f"tests.contracts.test_{path.stem}", f"{function}[{case['scenario']}]")
    report = CHECKER.check(INVENTORY, True, None)
    for example in report["additionalPythonPositiveTests"]:
        classname = example["file"].removesuffix(".py").replace("/", ".")
        name = example["test"]
        if example["provenance"] == "python_native_mcp_recipe_extension":
            name += f"[{example['tool']}]"
        add(classname, name)
    catalog = json.loads((ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text())
    for tool in catalog["tools"]:
        add(
            "tests.contracts.test_complete_rejections",
            "test_all_tools_reject_unknown_field_without_provider_side_effects["
            + tool["name"]
            + "]",
        )
    return root, suite, tmp_path / "junit.xml"


def check(evidence):
    root, _, path = evidence
    ET.ElementTree(root).write(path, encoding="utf-8")
    return CHECKER.check(INVENTORY, True, None, path)


def test_clean_complete_junit_passes(evidence):
    result = check(evidence)
    assert result["positiveTools"] == result["negativeTools"] == result["tools"]


@pytest.mark.parametrize("tag", ["failure", "error"])
def test_any_unrelated_failed_or_errored_case_invalidates_evidence(evidence, tag):
    _, suite, _ = evidence
    case = ET.SubElement(
        suite, "testcase", {"classname": "tests.unit.unrelated", "name": "regression"}
    )
    ET.SubElement(case, tag, {"message": "private detail must not appear"})
    with pytest.raises(ValueError, match="JUnit") as caught:
        check(evidence)
    assert "private detail" not in str(caught.value)


@pytest.mark.parametrize("attribute", ["failures", "errors"])
def test_declared_suite_failure_or_error_is_not_ignored(evidence, attribute):
    evidence[1].set(attribute, "1")
    with pytest.raises(ValueError, match="JUnit"):
        check(evidence)


def test_duplicate_case_identity_is_ambiguous_even_if_both_pass(evidence):
    _, suite, _ = evidence
    original = next(suite.iter("testcase"))
    ET.SubElement(suite, "testcase", dict(original.attrib))
    with pytest.raises(ValueError, match="[Dd]uplicate.*JUnit|JUnit.*[Dd]uplicate"):
        check(evidence)


def test_same_test_name_in_different_modules_remains_unambiguous(evidence):
    _, suite, _ = evidence
    for classname in ("tests.unit.first", "tests.unit.second"):
        ET.SubElement(suite, "testcase", {"classname": classname, "name": "test_common"})
    assert check(evidence)["positiveTools"] > 0


@pytest.mark.parametrize("kind", ["extension_positive", "captured_positive", "rejection"])
def test_wrong_test_module_cannot_supply_contract_evidence(evidence, kind):
    for case in evidence[1].iter("testcase"):
        name, classname = case.get("name", ""), case.get("classname", "")
        selected = (
            kind == "extension_positive"
            and name.startswith("test_recipe_jobs_mcp_positive[")
            or kind == "captured_positive"
            and classname == "tests.contracts.test_recipes_core"
            or kind == "rejection"
            and classname == "tests.contracts.test_complete_rejections"
        )
        if selected:
            case.set("classname", "tests.unit.wrong_module")
    with pytest.raises(ValueError, match="Missing executed MCP evidence"):
        check(evidence)


def test_wrong_function_cannot_supply_captured_scenario_evidence(evidence):
    for case in evidence[1].iter("testcase"):
        if case.get("classname") == "tests.contracts.test_recipes_core":
            case.set(
                "name", case.get("name").replace("test_core_recipe_contract", "test_not_a_contract")
            )
    with pytest.raises(ValueError, match="Missing executed MCP evidence"):
        check(evidence)
