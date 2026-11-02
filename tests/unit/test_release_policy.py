import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/release_policy.py"


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        (["docs: clarify installation"], "0.2.4"),
        (["fix(api): preserve null"], "0.3.0"),
        (["feat: skills", "chore: format"], "0.3.0"),
        (["refactor(docker)!: split compose"], "1.0.0"),
        (["fix: adjust\n\nBREAKING CHANGE: remove endpoint"], "1.0.0"),
        (["ops: change\n\nBREAKING-CHANGE: remove endpoint", "feat: add"], "1.0.0"),
        (["docs: mention BREAKING CHANGE: as inline prose"], "0.2.4"),
        ([], ""),
    ],
)
def test_release_please_override_follows_repository_version_policy(messages, expected):
    assert SCRIPT.exists(), "Release policy helper is not implemented"
    spec = importlib.util.spec_from_file_location("release_policy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.next_version("0.2.3", messages) == expected


def test_policy_uses_bootstrap_then_the_merged_manifest_change(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    def commit(message):
        git("add", ".")
        git("commit", "-qm", message)
        return git("rev-parse", "HEAD")

    def calculate():
        return subprocess.check_output(
            [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
            text=True,
        ).strip()

    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "code.txt").write_text("baseline")
    base = commit("chore: init")
    git("tag", "v2.1.0")
    (tmp_path / "release-please-config.json").write_text(
        json.dumps(
            {
                "bootstrap-sha": base,
                "packages": {".": {"initial-version": "0.1.0"}},
            }
        )
    )
    manifest = tmp_path / ".release-please-manifest.json"
    manifest.write_text('{".":"0.1.0"}')
    commit("feat(ci): configure official Release Please")
    assert calculate() == "0.2.0"
    manifest.write_text('{".":"0.2.0"}')
    commit("chore(main): release 0.2.0 (#2)")
    assert calculate() == ""
    (tmp_path / "code.txt").write_text("docs updated")
    commit("docs: explain feature")
    assert calculate() == "0.2.1"
    (tmp_path / "code.txt").write_text("fix null")
    commit("fix: preserve null")
    assert calculate() == "0.3.0"
