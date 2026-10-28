import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/release_gate.py"


@pytest.mark.parametrize("problem", [None, "pending", "missing", "duplicate", "version"])
def test_release_gate_requires_complete_unique_tasks_and_package_version(tmp_path, problem):
    tasks = [{"id": f"P{number:02}", "status": "verified"} for number in range(1, 25)]
    if problem == "pending":
        tasks[-1]["status"] = "in_progress"
    if problem == "missing":
        tasks.pop()
    if problem == "duplicate":
        tasks[-1]["id"] = "P23"
    state = tmp_path / "state.json"
    project = tmp_path / "pyproject.toml"
    state.write_text(json.dumps({"tasks": tasks}))
    project.write_text('[project]\nversion = "2.1.0"\n')
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--state",
            str(state),
            "--project",
            str(project),
            "--release-version",
            "2.2.0" if problem == "version" else "2.1.0",
        ],
        capture_output=True,
        text=True,
    )
    if problem is None:
        assert result.returncode == 0, result.stderr
        assert "verified" in result.stdout
    else:
        assert result.returncode != 0 and "Release gate:" in result.stderr
