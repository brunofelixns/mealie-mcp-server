import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REPO = "brunofelixns/mealie-mcp-server"


def step(job, identifier):
    config = yaml.load((ROOT / ".github/workflows/ci.yaml").read_text(), Loader=yaml.BaseLoader)
    return next(s["run"] for s in config["jobs"][job]["steps"] if s.get("id") == identifier)


def fake_gh(tmp_path, content):
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "gh"
    executable.write_text("#!/usr/bin/env python3\n" + content)
    executable.chmod(0o755)
    return {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "FAKE_STATE": str(tmp_path),
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
    }


@pytest.mark.parametrize("case", ["release", "feature", "fork", "unmerged", "other-sha", "empty"])
def test_only_the_merged_owned_release_pr_can_publish(tmp_path, case):
    associated = [
        {
            "number": 12,
            "merged_at": "2026-11-02",
            "merge_commit_sha": "a" * 40,
            "base": {"ref": "main"},
            "head": {"ref": "codex/release-main", "repo": {"full_name": REPO}},
        }
    ]
    if case == "feature":
        associated[0]["head"]["ref"] = "codex/feature"
    elif case == "fork":
        associated[0]["head"]["repo"]["full_name"] = "someone/mealies"
    elif case == "unmerged":
        associated[0]["merged_at"] = None
    elif case == "other-sha":
        associated[0]["merge_commit_sha"] = "b" * 40
    elif case == "empty":
        associated = []
    (tmp_path / "associated.json").write_text(json.dumps(associated))
    env = fake_gh(
        tmp_path,
        "import os,pathlib\n"
        "print((pathlib.Path(os.environ['FAKE_STATE'])/'associated.json').read_text())\n",
    )
    env["GITHUB_SHA"] = "a" * 40
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step("release_status", "release")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "output.txt").read_text() == (
        "number=12\n" if case == "release" else "number=\n"
    )


FAKE_PR_GH = """import json, os, sys
from pathlib import Path
state = Path(os.environ['FAKE_STATE'])
args = sys.argv[1:]
with (state/'gh.jsonl').open('a') as stream:
    stream.write(json.dumps(args)+'\\n')
if args[:2] == ['pr', 'list']:
    print('12' if (state/'pr-exists').exists() else '')
elif args[:2] == ['pr', 'create']:
    (state/'pr-exists').touch()
elif args[:2] == ['pr', 'edit'] or args[:2] == ['workflow', 'run']:
    pass
else:
    raise SystemExit('Unexpected GitHub operation: '+repr(args))
"""


def test_release_pr_accumulates_updates_without_touching_main(tmp_path):
    env = fake_gh(tmp_path, FAKE_PR_GH)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("remote", "add", "origin", str(remote))
    proposal = tmp_path / "artifacts/version"
    proposal.mkdir(parents=True)
    (proposal / "release.json").write_text('{"version":"0.2.0"}')
    (proposal / "notes.md").write_text("Proposed release\n")
    script = step("release_pr", "release_pr")
    previous_source = None
    for count in range(2):
        if previous_source:
            git("checkout", "--detach", previous_source)
        (tmp_path / "code.txt").write_text(f"feature {count}")
        git("add", "code.txt")
        git("commit", "-qm", "feat: source")
        source = git("rev-parse", "HEAD")
        git("push", "-q", "origin", "HEAD:refs/heads/main")
        (tmp_path / "code.txt").write_text(f"release {count}")
        git("commit", "-qam", "chore(release): 0.2.0")
        revision = git("rev-parse", "HEAD")
        env["GITHUB_SHA"] = source
        result = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        assert git("ls-remote", "origin", "refs/heads/main").split()[0] == source
        assert git("ls-remote", "origin", "refs/heads/codex/release-main").split()[0] == revision
        previous_source = source
    calls = [json.loads(line) for line in (tmp_path / "gh.jsonl").read_text().splitlines()]
    assert len([call for call in calls if call[:2] == ["pr", "create"]]) == 1
    assert len([call for call in calls if call[:2] == ["pr", "edit"]]) == 1
    assert len([call for call in calls if call[:2] == ["workflow", "run"]]) == 2
    # A stale run cannot replace the current proposal, even if its version is identical.
    newer_main = git(
        "commit-tree",
        previous_source + "^{tree}",
        "-p",
        previous_source,
        "-m",
        "docs: another PR merged",
    )
    git("push", "-q", "origin", newer_main + ":refs/heads/main")
    env["GITHUB_SHA"] = previous_source
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert git("ls-remote", "origin", "refs/heads/codex/release-main").split()[0] == revision
    assert (tmp_path / "gh.jsonl").read_text().splitlines() == [json.dumps(c) for c in calls]


@pytest.mark.parametrize("case", ["valid", "version", "revision", "non-semver"])
def test_publisher_requires_matching_tested_versions_and_revisions(tmp_path, case):
    images = tmp_path / "artifacts/images"
    images.mkdir(parents=True)
    for arch in ("amd64", "arm64"):
        metadata = {"version": "0.2.0", "revision": "a" * 40}
        if case == "version" and arch == "arm64":
            metadata["version"] = "0.3.0"
        elif case == "revision" and arch == "arm64":
            metadata["revision"] = "b" * 40
        elif case == "non-semver":
            metadata["version"] = "not-a-version"
        (images / f"runtime-{arch}.json").write_text(json.dumps(metadata))
    output = tmp_path / "output.txt"
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step("publish", "version")],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_SHA": "a" * 40, "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (case == "valid"), result.stderr
    if case == "valid":
        assert output.read_text() == "version=0.2.0\n"
