import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yaml").read_text(), Loader=yaml.BaseLoader)


def test_only_main_pushes_publish_after_all_native_checks():
    config = workflow()
    assert set(config["on"]) == {"push", "pull_request"}
    assert config["permissions"] == {"contents": "read"}
    checks = config["jobs"]["checks"]
    assert checks["strategy"]["fail-fast"] == "false"
    assert checks["strategy"]["matrix"]["include"] == [
        {"runner": "ubuntu-24.04", "arch": "amd64"},
        {"runner": "ubuntu-24.04-arm", "arch": "arm64"},
    ]
    publish = config["jobs"]["publish"]
    assert publish["needs"] == ["prepare", "checks"]
    assert publish["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert publish["permissions"] == {"contents": "write", "packages": "write"}
    assert checks["needs"] == "prepare"
    prepare = config["jobs"]["prepare"]
    assert "permissions" not in prepare
    assert prepare["outputs"]["revision"] == "${{ steps.version.outputs.revision }}"
    assert not (ROOT / ".github/workflows/release.yaml").exists()


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
    elif defect == "git-late-race" and args[:3] == ["buildx", "imagetools", "create"]:
        source = os.environ["GITHUB_SHA"]
        tree = subprocess.check_output(["git", "rev-parse", source + "^{tree}"], text=True).strip()
        concurrent = subprocess.check_output(
            ["git", "commit-tree", tree, "-p", source, "-m", "docs: concurrent"], text=True,
        ).strip()
        subprocess.run(["git", "push", "-q", "origin", concurrent + ":refs/heads/main"], check=True)
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
    ],
)
def test_publisher_uses_verified_artifacts_and_never_promotes_a_failed_release(tmp_path, defect):
    steps = workflow()["jobs"]["publish"]["steps"]
    script = next(step["run"] for step in steps if step.get("id") == "publish")
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
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
    if defect == "git-tag":
        git("tag", "v0.2.0", source)
        git("push", "-q", "origin", "refs/tags/v0.2.0")
    elif defect == "git-race":
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
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "FAKE_STATE": str(tmp_path),
            "DEFECT": defect,
            "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
            "GITHUB_SHA": source,
            "RELEASE_REVISION": revision,
            "RELEASE_VERSION": "0.2.0",
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        },
        capture_output=True,
        text=True,
    )
    log = tmp_path / "commands.jsonl"
    commands = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    creates = [command for command in commands if command[:3] == ["buildx", "imagetools", "create"]]
    assert not any(command[:2] == ["buildx", "build"] for command in commands)
    if defect:
        assert result.returncode != 0
        assert not any(any(value.endswith(":latest") for value in command) for command in creates)
        if defect in {"identity", "platform"}:
            assert not any(command[0] == "push" for command in commands)
        if defect == "git-tag":
            assert git("ls-remote", "origin", "refs/tags/v0.2.0").split()[0] == source
        persisted = git("ls-remote", "origin", "refs/heads/main").split()[0] == revision
        assert persisted == (defect in {"version-promote", "version-verification"})
    else:
        assert result.returncode == 0, result.stderr
        assert len([command for command in commands if command[0] == "push"]) == 2
        assert len(creates) == 3
        assert any(value.endswith(":latest") for value in creates[-1])
        assert "sha-" + revision in (tmp_path / "summary.md").read_text()
        assert git("ls-remote", "origin", "refs/heads/main").split()[0] == revision
        assert git("ls-remote", "origin", "refs/tags/v0.2.0").split()[0] == revision
        # Repeating the publisher must not create a new source version/tag.
        rerun = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            cwd=tmp_path,
            env={
                **os.environ,
                "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                "FAKE_STATE": str(tmp_path),
                "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
                "GITHUB_SHA": source,
                "RELEASE_REVISION": revision,
                "RELEASE_VERSION": "0.2.0",
                "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
            },
            capture_output=True,
            text=True,
        )
        assert rerun.returncode == 0, rerun.stderr
