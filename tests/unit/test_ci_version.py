import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci_version.py"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def commit(root, message):
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for relative in (
        "pyproject.toml",
        "uv.lock",
        "Dockerfile",
        "README.md",
        "docs/README.es.md",
        "API_COVERAGE.md",
        "docs/api-coverage.md",
        "docs/tools.md",
        "docs/migration/compatibility-inventory.json",
        "src/mealie_mcp_server/resources/tool-catalog.json",
        "scripts/generate_docs.py",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mealie-mcp-server"\nversion = "0.1.0"\n'
    )
    (root / "uv.lock").write_text(
        '[[package]]\nname = "mealie-mcp-server"\nversion = "0.1.0"\n'
        '\n[[package]]\nname = "other-library"\nversion = "7.8.9"\n'
    )
    (root / "Dockerfile").write_text('LABEL org.opencontainers.image.version="0.1.0"\n')
    git(root, "init", "-qb", "main")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    baseline = commit(root, "chore: init")
    git(root, "tag", "v2.1.0")
    (root / ".release.json").write_text(json.dumps({"base_revision": baseline}) + "\n")
    (root / "feature.txt").write_text("new feature\n")
    source = commit(root, "feat(ci): automate versions")
    return root, source


def prepare(root, output):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "prepare", "--root", str(root), "--output", str(output)],
        capture_output=True,
        text=True,
    )


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
    ],
)
def test_increment_uses_repository_commit_policy(messages, expected):
    import importlib.util

    assert SCRIPT.exists(), "The CI version preparer has not been implemented"
    spec = importlib.util.spec_from_file_location("ci_version", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.next_version("0.2.3", messages) == expected


def test_preparation_keeps_versions_aligned_and_bundle_is_reproducible(repository, tmp_path):
    root, source = repository
    first = tmp_path / "first"
    result = prepare(root, first)
    assert result.returncode == 0, result.stderr
    metadata = json.loads((first / "release.json").read_text())
    assert metadata["version"] == "0.2.0"
    assert metadata["source"] == source
    assert metadata["tag"] == "v0.2.0"
    revision = git(root, "rev-parse", "HEAD")
    assert "[skip ci]" not in git(root, "show", "-s", "--format=%B", revision)
    assert metadata["revision"] == revision != source
    project = tomllib.loads((root / "pyproject.toml").read_text())
    assert project["project"]["version"] == "0.2.0"
    packages = tomllib.loads((root / "uv.lock").read_text())["package"]
    assert next(p for p in packages if p["name"] == "mealie-mcp-server")["version"] == "0.2.0"
    assert next(p for p in packages if p["name"] == "other-library")["version"] == "7.8.9"
    assert 'org.opencontainers.image.version="0.2.0"' in (root / "Dockerfile").read_text()
    assert "Catalog for version 0.2.0." in (root / "README.md").read_text()
    assert "Catálogo de la versión 0.2.0." in (root / "docs/README.es.md").read_text()
    assert "automate versions" in (first / "notes.md").read_text()
    assert json.loads((root / ".release.json").read_text())["base_revision"] == source
    assert not git(root, "status", "--porcelain")
    git(root, "checkout", "--detach", source)
    second = tmp_path / "second"
    assert prepare(root, second).returncode == 0
    assert git(root, "rev-parse", "HEAD") == revision
    git(root, "checkout", "--detach", source)
    git(root, "fetch", str(first / "release.bundle"), "HEAD")
    git(root, "checkout", "--detach", "FETCH_HEAD")
    assert git(root, "rev-parse", "HEAD") == revision
    git(root, "branch", "fixture-source", source)
    isolated = tmp_path / "isolated"
    subprocess.run(
        [
            "git",
            "clone",
            "--no-local",
            "--depth",
            "1",
            "--branch",
            "fixture-source",
            str(root),
            str(isolated),
        ],
        check=True,
        capture_output=True,
    )
    missing = subprocess.run(
        ["git", "-C", str(isolated), "cat-file", "-e", revision],
        capture_output=True,
    )
    assert missing.returncode != 0
    git(isolated, "fetch", str(first / "release.bundle"), "HEAD")
    git(isolated, "checkout", "--detach", "FETCH_HEAD")
    assert git(isolated, "rev-parse", "HEAD") == revision
    (root / "feature.txt").write_text("new feature and docs\n")
    commit(root, "docs: describe feature")
    third = tmp_path / "third"
    assert prepare(root, third).returncode == 0
    assert json.loads((third / "release.json").read_text())["version"] == "0.2.1"


def test_preparation_rejects_dirty_or_nonancestor_anchor_without_changing_version(
    repository,
    tmp_path,
):
    root, _ = repository
    before = (root / "pyproject.toml").read_bytes()
    (root / "feature.txt").write_text("uncommitted change")
    result = prepare(root, tmp_path / "dirty")
    assert result.returncode != 0
    assert "clean checkout" in result.stderr
    assert (root / "pyproject.toml").read_bytes() == before
    git(root, "checkout", "--", "feature.txt")
    (root / ".release.json").write_text(json.dumps({"base_revision": "f" * 40}))
    commit(root, "ops: invalid anchor")
    result = prepare(root, tmp_path / "invalid")
    assert result.returncode != 0
    assert (root / "pyproject.toml").read_bytes() == before


def test_preparation_refuses_an_existing_version_tag(repository, tmp_path):
    root, _ = repository
    git(root, "tag", "v0.2.0")
    before = (root / "pyproject.toml").read_bytes()
    result = prepare(root, tmp_path / "conflict")
    assert result.returncode != 0
    assert "Release tag already exists" in result.stderr
    assert (root / "pyproject.toml").read_bytes() == before


def test_squash_release_is_the_next_anchor_instead_of_a_new_patch(repository, tmp_path):
    root, source = repository
    proposal = tmp_path / "proposal"
    result = prepare(root, proposal)
    assert result.returncode == 0, result.stderr
    revision = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "--detach", source)
    git(root, "merge", "--squash", revision)
    commit(root, "chore(release): 0.2.0 (#12)")
    empty = prepare(root, tmp_path / "empty")
    assert empty.returncode != 0
    assert "No unreleased commits" in empty.stderr
    (root / "feature.txt").write_text("documented\n")
    commit(root, "docs: explain feature")
    next_release = tmp_path / "next"
    result = prepare(root, next_release)
    assert result.returncode == 0, result.stderr
    assert json.loads((next_release / "release.json").read_text())["version"] == "0.2.1"
    assert "docs: explain feature" in (next_release / "notes.md").read_text()
    assert "(#12)" not in (next_release / "notes.md").read_text()
