import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_workflows.py"


@pytest.mark.parametrize("location", ["workflow", "other-job", "other-file"])
def test_actionlint_queue_exception_cannot_hide_other_queue_locations(tmp_path, location):
    spec = importlib.util.spec_from_file_location("workflow_lint", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if location == "workflow":
        data = "concurrency: {group: x, queue: max}\njobs: {}\n"
    else:
        job = "checks" if location == "other-job" else "publish"
        data = f"jobs:\n  {job}:\n    concurrency: {{group: x, queue: max}}\n"
    name = "other.yaml" if location == "other-file" else "ci.yaml"
    path = tmp_path / name
    path.write_text(data)
    assert hasattr(module, "check_queue_scope"), "Narrow queue exception guard is missing"
    with pytest.raises(ValueError, match="queue"):
        module.check_queue_scope([path])
