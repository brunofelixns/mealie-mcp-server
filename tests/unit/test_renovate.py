"""Exercise the custom Renovate extractors against the files they maintain.

The patterns deliberately use RE2-compatible syntax. Python's named group
spelling differs, so translate that spelling only for this extraction check.
"""

import ast
import json
import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "renovate.json").read_text())


def extract(manager, contents):
    result = []
    for pattern in manager["matchStrings"]:
        translated = re.sub(r"\(\?<([a-zA-Z][a-zA-Z0-9_]*)>", r"(?P<\1>", pattern)
        result.extend(match.groupdict() for match in re.finditer(translated, contents))
    return result


@pytest.mark.parametrize(
    ("source", "constant", "dependency"),
    [
        ("scripts/scan_runtime.py", "SCANNER", "aquasec/trivy"),
        ("scripts/check_workflows.py", "ACTIONLINT", "rhysd/actionlint"),
        ("scripts/check_workflows.py", "ZIZMOR", "ghcr.io/zizmorcore/zizmor"),
    ],
)
def test_docker_extraction_matches_the_ref_consumed_by_the_python_script(
    source, constant, dependency
):
    manager = next(
        item for item in CONFIG["customManagers"] if item["datasourceTemplate"] == "docker"
    )
    assert any(re.fullmatch(pattern[1:-1], source) for pattern in manager["managerFilePatterns"])
    contents = (ROOT / source).read_text()
    assignments = {
        target.id: ast.literal_eval(statement.value)
        for statement in ast.parse(contents).body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name) and target.id == constant
    }
    matches = [item for item in extract(manager, contents) if item["depName"] == dependency]
    assert len(matches) == 1
    match = matches[0]
    assert (
        f"{match['depName']}:{match['currentValue']}@{match['currentDigest']}"
        == assignments[constant]
    )


def test_cli_extraction_matches_the_npm_package_argument_consumed_by_the_workflow():
    manager = next(item for item in CONFIG["customManagers"] if item["datasourceTemplate"] == "npm")
    source = ".github/workflows/release-please.yaml"
    assert any(re.fullmatch(pattern[1:-1], source) for pattern in manager["managerFilePatterns"])
    contents = (ROOT / source).read_text()
    workflow = yaml.load(contents, Loader=yaml.BaseLoader)
    pins = [
        argument.removeprefix("--package=")
        for step in workflow["jobs"]["release"]["steps"]
        for line in step.get("run", "").splitlines()
        for argument in shlex.split(line)
        if argument.startswith("--package=release-please@")
    ]
    matches = extract(manager, contents)
    assert len(matches) == 1
    assert [f"{item['depName']}@{item['currentValue']}" for item in matches] == pins


@pytest.mark.parametrize("separator", ["", '"\n    "'])
def test_trivy_extractor_keeps_the_tag_and_digest_separately_updatable(separator):
    manager = next(
        item for item in CONFIG["customManagers"] if item["datasourceTemplate"] == "docker"
    )
    digest = "sha256:" + "a" * 64
    contents = f'SCANNER = (\n    "aquasec/trivy:1.2.3@{separator}{digest}"\n)'
    assert extract(manager, contents) == [
        {"depName": "aquasec/trivy", "currentValue": "1.2.3", "currentDigest": digest}
    ]


def test_cli_extractor_does_not_claim_other_npm_tools_or_command_arguments():
    manager = next(item for item in CONFIG["customManagers"] if item["datasourceTemplate"] == "npm")
    contents = (
        "npx --package=other-tool@1.2.3 other-tool\n"
        "release-please release-pr --release-as 2.3.4\n"
        "npx --package=release-please@2.3.4 release-please release-pr"
    )
    assert extract(manager, contents) == [{"depName": "release-please", "currentValue": "2.3.4"}]


def test_regular_updates_have_one_universal_group_without_version_type_splits():
    # Guard the grouping contract without fixing a cosmetic group name or pin.
    # Renovate itself is not reimplemented or executed by this Python check.
    groups = [rule for rule in CONFIG["packageRules"] if rule.get("groupName")]
    assert groups
    assert len({(rule["groupName"], rule.get("groupSlug")) for rule in groups}) == 1
    universal = next(rule for rule in groups if rule.get("matchPackageNames") == ["*"])
    assert universal["groupSlug"]
    assert universal["separateMajorMinor"] is False
    assert universal["separateMinorPatch"] is False
    assert universal["separateMultipleMajor"] is False
    assert universal["separateMultipleMinor"] is False
    assert CONFIG["automerge"] is False
    assert CONFIG["semanticCommitType"] == "chore"
    assert CONFIG["semanticCommitScope"] == "deps"
    # Override inherited per-dependency semantic rules as well as root defaults.
    assert universal["semanticCommitType"] == "chore"
    assert universal["semanticCommitScope"] == "deps"
