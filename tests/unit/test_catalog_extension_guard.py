import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "compatibility_script", ROOT / "scripts/check_compatibility.py"
)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def test_compatibility_guard_keeps_exact_original_definitions_and_allows_declared_additions(
    tmp_path, monkeypatch
):
    catalog_path = ROOT / "src/mealie_mcp_server/resources/tool-catalog.json"
    baseline = json.loads((ROOT / "tests/fixtures/compatibility/catalog.json").read_text())["tools"]
    original_catalog = json.loads(catalog_path.read_text())
    extension = copy.deepcopy(baseline[0])
    extension["name"] = "future_recipe_tool"
    catalog = {**original_catalog, "tools": [*baseline, extension]}
    for relative in (
        "docs/migration/compatibility-inventory.json",
        "docs/migration/implementation-state.json",
        "tests/fixtures/compatibility/catalog.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative).read_text())
    destination = tmp_path / "src/mealie_mcp_server/resources/tool-catalog.json"
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(catalog))
    inventory_path = tmp_path / "docs/migration/compatibility-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["tools"] = [
        tool for tool in inventory["tools"] if tool["name"] in {item["name"] for item in baseline}
    ]
    for item in inventory["tools"]:
        item.pop("runtimeExamples", None)
    inventory["tools"].append(
        {
            "name": "future_recipe_tool",
            "group": "recipes",
            "migrationStatus": "implemented_contract_verified",
        }
    )
    inventory_path.write_text(json.dumps(inventory))
    state_path = tmp_path / "docs/migration/implementation-state.json"
    state = json.loads(state_path.read_text())
    state["tasks"] = [task for task in state["tasks"] if not str(task["id"]).startswith("R")]
    state["tasks"].append({"id": "RTEST", "tools": ["future_recipe_tool"]})
    state_path.write_text(json.dumps(state))
    rejection = tmp_path / "tests/contracts/test_complete_rejections.py"
    rejection.parent.mkdir(parents=True)
    rejection.write_text("definitions()")
    (tmp_path / "tests/fixtures/compatibility/cases").mkdir(parents=True)
    monkeypatch.setattr(CHECKER, "ROOT", tmp_path)
    report = CHECKER.check(inventory_path, False, None)
    assert report["tools"] == 79 and report["baselineTools"] == 78
    catalog["tools"][0]["description"] += " changed"
    destination.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="baseline"):
        CHECKER.check(inventory_path, False, None)
