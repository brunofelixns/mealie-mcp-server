import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_pr_title.py"


def check_title(tmp_path, title, config=None):
    assert SCRIPT.exists(), "PR title validator is not implemented"
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"title": title}}))
    command = [sys.executable, str(SCRIPT), "--event", str(event)]
    if config is not None:
        config_path = tmp_path / "release-please-config.json"
        config_path.write_text(json.dumps(config))
        command.extend(["--config", str(config_path)])
    return subprocess.run(command, text=True, capture_output=True, check=False)


@pytest.mark.parametrize(
    "title",
    [
        "feat: add recipes",
        "fix(api): preserve null",
        "refactor(api)!: remove the legacy field",
        "perf!: reduce memory use",
        "style: format handlers",
        "test: cover empty arrays",
        "docs: document instalación",
        "build: update Python",
        "ops: update deployment",
        "chore(main): release 0.2.0",
        "ci(deps): update actions",
        "revert: restore recipe ordering",
    ],
)
def test_accepts_configured_release_types_and_scoped_breaking_titles(tmp_path, title):
    result = check_title(tmp_path, title)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "title",
    [
        "",
        "add recipes",
        "feature: add recipes",
        "Feat: add recipes",
        "feat: Add recipes",
        "feat: add recipes.",
        "feat: ",
        "feat:  add recipes",
        " feat: add recipes",
        "feat: add recipes ",
        "feat(): add recipes",
        "feat( api): add recipes",
        "feat(api ): add recipes",
        "feat(api)(client): add recipes",
        "feat: add\nrecipes",
        "feat: add\rrecipes",
        "feat: add\trecipes",
        "feat: add\u2028recipes",
        "feat: add\x1brecipes",
        None,
        42,
    ],
)
def test_rejects_invalid_titles_with_a_controlled_error(tmp_path, title):
    result = check_title(tmp_path, title)
    assert result.returncode == 1
    assert "Invalid PR title:" in result.stderr
    assert "Traceback" not in result.stderr


def test_uses_the_release_configuration_instead_of_a_duplicate_type_list(tmp_path):
    config = {"packages": {".": {"changelog-sections": [{"type": "maintenance"}]}}}
    assert check_title(tmp_path, "maintenance: update policies", config).returncode == 0
    assert check_title(tmp_path, "feat: add recipes", config).returncode == 1


def test_untrusted_title_is_data_and_is_not_echoed_into_action_logs(tmp_path):
    marker = tmp_path / "executed"
    title = f"fix: handle $(touch {marker}) `touch {marker}` ${{{{ secrets.TOKEN }}}}"
    result = check_title(tmp_path, title)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert "touch" not in result.stdout + result.stderr


def test_reads_the_github_event_file_environment_variable(tmp_path):
    assert SCRIPT.exists(), "PR title validator is not implemented"
    event = tmp_path / "github-event.json"
    event.write_text(json.dumps({"pull_request": {"title": "fix: preserve false"}}))
    environment = dict(os.environ, GITHUB_EVENT_PATH=str(event))
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("contents", ["{", "{}", '{"pull_request": {}}', "[]"])
def test_rejects_missing_or_malformed_event_payloads(tmp_path, contents):
    assert SCRIPT.exists(), "PR title validator is not implemented"
    event = tmp_path / "event.json"
    event.write_text(contents)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--event", str(event)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Invalid PR title:" in result.stderr
    assert "Traceback" not in result.stderr


def test_fails_closed_when_release_types_are_missing(tmp_path):
    result = check_title(tmp_path, "feat: add recipes", {"packages": {".": {}}})
    assert result.returncode == 1
    assert "release types" in result.stderr
