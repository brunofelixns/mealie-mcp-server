import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yaml").read_text(), Loader=yaml.BaseLoader)


def test_only_released_tag_dispatches_publish_after_all_native_checks():
    config = workflow()
    assert set(config["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert config["permissions"] == {"contents": "read"}
    checks = config["jobs"]["checks"]
    assert checks["strategy"]["fail-fast"] == "false"
    assert checks["strategy"]["matrix"]["include"] == [
        {"runner": "ubuntu-24.04", "arch": "amd64"},
        {"runner": "ubuntu-24.04-arm", "arch": "arm64"},
    ]
    publish = config["jobs"]["publish"]
    assert publish["needs"] == "checks"
    assert publish["if"] == "github.event_name == 'workflow_dispatch' && inputs.release_tag != ''"
    assert publish["permissions"] == {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
        "attestations": "write",
    }
    release = yaml.load(
        (ROOT / ".github/workflows/release-please.yaml").read_text(),
        Loader=yaml.BaseLoader,
    )
    official = next(s for s in release["jobs"]["release"]["steps"] if s.get("id") == "release")
    assert re.fullmatch(r"googleapis/release-please-action@[0-9a-f]{40}", official["uses"])
    assert not (ROOT / ".github/workflows/release.yaml").exists()


def test_runtime_checks_depend_on_workflow_and_dependency_policy():
    config = workflow()
    assert config["on"]["push"]["branches"] == ["main"]
    assert config["jobs"]["checks"]["needs"] == "quality"
    # A skipped required job is accepted by GitHub branch protection: make policy
    # failures produce FAILED native checks instead of skipping them.
    assert config["jobs"]["checks"]["if"] == "always()"
    guard = config["jobs"]["checks"]["steps"][0]
    for result, expected in (("success", 0), ("failure", 1), ("skipped", 1), ("cancelled", 1)):
        observed = subprocess.run(
            ["bash", "-c", guard["run"]],
            env={**os.environ, "POLICY_RESULT": result},
            capture_output=True,
        )
        assert observed.returncode == expected
    steps = config["jobs"]["quality"]["steps"]
    review = next(s for s in steps if s.get("name") == "Review dependency changes")
    assert review["if"] == "github.event_name == 'pull_request'"
    assert review["with"]["fail-on-severity"] == "high"
    commands = next(s["with"]["runCmd"] for s in steps if "runCmd" in s.get("with", {}))
    assert "scripts/check_workflows.py" in commands
    assert "scripts/check_pr_title.py" in commands


def test_signed_evidence_precedes_promotion_and_is_retained_with_release():
    config = workflow()
    steps = config["jobs"]["publish"]["steps"]
    stage = next(i for i, s in enumerate(steps) if s.get("id") == "stage")
    promotion = next(i for i, s in enumerate(steps) if s.get("id") == "publish")
    attestations = [
        i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/attest@")
    ]
    assert len(attestations) == 5
    assert all(stage < i < promotion for i in attestations)
    assert config["jobs"]["release-evidence"]["needs"] == "publish"
    assert config["jobs"]["release-evidence"]["permissions"] == {"contents": "write"}
    assert config["jobs"]["publish"]["permissions"]["id-token"] == "write"


FAKE_DOCKER = """#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

args = sys.argv[1:]
state = Path(os.environ["FAKE_STATE"])
with (state / "commands.jsonl").open("a") as log:
    log.write(json.dumps(args) + "\\n")
defect = os.environ.get("DEFECT", "")
digests = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}
index = "sha256:" + "c" * 64
if args[:2] == ["image", "load"]:
    (state / "arch").write_text("arm64" if "arm64" in args[-1] else "amd64")
elif args[:2] == ["image", "inspect"]:
    arch = (state / "arch").read_text()
    if args[3] == "{{.Id}}":
        print("wrong-id" if defect == "identity" and arch == "arm64" else arch + "-id")
    else:
        print("linux/s390x" if defect == "platform" else "linux/" + arch)
elif args[0] == "push":
    if defect == "push" and args[-1].endswith("-arm64"):
        sys.exit(1)
elif args[:3] == ["buildx", "imagetools", "inspect"]:
    reference = args[3]
    if "range" in args[-1]:
        print("linux/amd64 " + digests["amd64"])
        print("linux/arm64 " + (digests["amd64"] if defect == "manifest" else digests["arm64"]))
    elif reference.endswith("-amd64"):
        print(digests["amd64"])
    elif reference.endswith("-arm64"):
        print(digests["arm64"])
    elif reference.endswith(":0.2.0") and not (state / "version-published").exists():
        if defect == "version-conflict":
            print("sha256:" + "d" * 64)
        elif defect == "version-unavailable":
            print("network unavailable", file=sys.stderr)
            sys.exit(1)
        elif defect == "version-helper":
            print("credential helper executable file not found", file=sys.stderr)
            sys.exit(1)
        else:
            print("manifest unknown", file=sys.stderr)
            sys.exit(1)
    elif reference.endswith(":0.2.0") and defect == "version-verification":
        print("sha256:" + "d" * 64)
    else:
        print(index)
elif args[0] == "tag" or args[:3] == ["buildx", "imagetools", "create"]:
    if any(value.endswith(":0.2.0") for value in args):
        if defect == "version-promote":
            sys.exit(1)
        (state / "version-published").touch()
    elif (defect == "git-late-race" and not (state / "main-advanced").exists()
          and args[:3] == ["buildx", "imagetools", "create"]):
        source = os.environ["GITHUB_SHA"]
        tree = subprocess.check_output(["git", "rev-parse", source + "^{tree}"], text=True).strip()
        concurrent = subprocess.check_output(
            ["git", "commit-tree", tree, "-p", source, "-m", "docs: concurrent"], text=True,
        ).strip()
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
        subprocess.run(
            ["git", "push", "-q", "origin", concurrent + ":refs/heads/fixture-concurrent"],
            check=True,
        )
        subprocess.run(
            ["git", "--git-dir", remote, "update-ref", "refs/heads/main", concurrent], check=True,
        )
        (state / "main-advanced").touch()
else:
    raise SystemExit("Unexpected Docker operation: " + repr(args))
"""


@pytest.mark.parametrize(
    "defect",
    [
        "",
        "identity",
        "platform",
        "push",
        "manifest",
        "git-race",
        "git-tag",
        "version-conflict",
        "version-unavailable",
        "version-helper",
        "git-late-race",
        "version-promote",
        "version-verification",
        "newer-release",
        "legacy-tag",
        "attestation",
    ],
)
def test_publisher_uses_verified_artifacts_and_never_promotes_a_failed_release(tmp_path, defect):
    steps = workflow()["jobs"]["publish"]["steps"]
    stage = next((s["run"] for s in steps if s.get("id") == "stage"), "")
    script = stage + "\n" + next(step["run"] for step in steps if step.get("id") == "publish")
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    gh = binary / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\nimport base64,json,os,sys\n"
        "if sys.argv[1] == 'attestation':\n"
        "    sys.exit(1 if os.environ.get('DEFECT')=='attestation' else 0)\n"
        "version='0.3.0' if os.environ.get('DEFECT')=='newer-release' else '0.2.0'\n"
        "print(base64.b64encode(json.dumps({'.':version}).encode()).decode())\n"
    )
    gh.chmod(0o755)
    images = tmp_path / "artifacts/images"
    images.mkdir(parents=True)
    for arch in ("amd64", "arm64"):
        (images / f"runtime-{arch}.tar").touch()
        (images / f"runtime-{arch}.id").write_text(arch + "-id\n")
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "source.txt").write_text("source")
    git("add", "source.txt")
    git("commit", "-qm", "feat: source")
    source = git("rev-parse", "HEAD")
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", "HEAD:refs/heads/main")
    (tmp_path / "source.txt").write_text("release")
    git("commit", "-qam", "chore(release): 0.2.0 [skip ci]")
    revision = git("rev-parse", "HEAD")
    git("push", "-q", "origin", "HEAD:refs/heads/main")
    if defect == "git-tag":
        git("tag", "v0.2.0", source)
        git("push", "-q", "origin", "refs/tags/v0.2.0")
    else:
        git("tag", "v0.2.0", revision)
        git("push", "-q", "origin", "refs/tags/v0.2.0")
    if defect == "git-race":
        # Simulate an unrelated newer main without modifying the release checkout.
        other = tmp_path / "concurrent"
        subprocess.run(["git", "clone", "-qb", "main", str(remote), str(other)], check=True)
        subprocess.run(["git", "-C", str(other), "config", "user.name", "Other"], check=True)
        subprocess.run(
            ["git", "-C", str(other), "config", "user.email", "other@invalid"],
            check=True,
        )
        (other / "other.txt").touch()
        subprocess.run(["git", "-C", str(other), "add", "."], check=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "docs: concurrent"], check=True)
        subprocess.run(["git", "-C", str(other), "push", "-q"], check=True)
    elif defect == "newer-release":
        git("tag", "v0.3.0", source)
        git("push", "-q", "origin", "refs/tags/v0.3.0")
    elif defect == "legacy-tag":
        git("tag", "v2.1.0", source)
        git("push", "-q", "origin", "refs/tags/v2.1.0")
    # A protected main rejects every raw push, including a no-op update.
    hook = remote / "hooks/pre-receive"
    hook.write_text(
        "#!/bin/sh\nwhile read old new ref; do\n"
        '  if [ "$ref" = refs/heads/main ]; then exit 1; fi\ndone\n'
    )
    hook.chmod(0o755)
    main_before = git("ls-remote", "origin", "refs/heads/main").split()[0]
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "FAKE_STATE": str(tmp_path),
            "DEFECT": defect,
            "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
            "GITHUB_SHA": revision,
            "RELEASE_REVISION": revision,
            "RELEASE_VERSION": "0.2.0",
            "STAGED_DIGEST": "sha256:" + "c" * 64,
            "STAGED_AMD64_DIGEST": "sha256:" + "a" * 64,
            "STAGED_ARM64_DIGEST": "sha256:" + "b" * 64,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
        },
        capture_output=True,
        text=True,
    )
    log = tmp_path / "commands.jsonl"
    commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    creates = [command for command in commands if command[:3] == ["buildx", "imagetools", "create"]]
    assert not any(command[:2] == ["buildx", "build"] for command in commands)
    succeeds = defect in {"", "git-race", "git-late-race", "newer-release", "legacy-tag"}
    if not succeeds:
        assert result.returncode != 0
        assert not any(any(value.endswith(":latest") for value in command) for command in creates)
        if defect in {"identity", "platform"}:
            assert not any(command[0] == "push" for command in commands)
        if defect == "attestation":
            assert not any(
                any(value.endswith(":0.2.0") for value in command) for command in creates
            )
        if defect == "git-tag":
            assert git("ls-remote", "origin", "refs/tags/v0.2.0").split()[0] == source
        assert git("ls-remote", "origin", "refs/heads/main").split()[0] == main_before
    else:
        assert result.returncode == 0, result.stderr
        assert len([command for command in commands if command[0] == "push"]) == 2
        assert len(creates) == (2 if defect == "newer-release" else 3)
        promoted = any(any(value.endswith(":latest") for value in command) for command in creates)
        assert promoted == (defect != "newer-release")
        assert "sha-" + revision in (tmp_path / "summary.md").read_text()
        if defect != "git-late-race":
            assert git("ls-remote", "origin", "refs/heads/main").split()[0] == main_before
        assert git("ls-remote", "origin", "refs/tags/v0.2.0").split()[0] == revision
        # Repeating the publisher must not create a new source version/tag.
        rerun = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            cwd=tmp_path,
            env={
                **os.environ,
                "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                "FAKE_STATE": str(tmp_path),
                "DEFECT": defect,
                "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
                "GITHUB_SHA": revision,
                "RELEASE_REVISION": revision,
                "RELEASE_VERSION": "0.2.0",
                "STAGED_DIGEST": "sha256:" + "c" * 64,
                "STAGED_AMD64_DIGEST": "sha256:" + "a" * 64,
                "STAGED_ARM64_DIGEST": "sha256:" + "b" * 64,
                "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
                "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
            },
            capture_output=True,
            text=True,
        )
        assert rerun.returncode == 0, rerun.stderr
