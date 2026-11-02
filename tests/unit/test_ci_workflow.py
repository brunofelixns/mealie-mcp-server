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
    assert publish["needs"] == "checks"
    assert publish["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert publish["permissions"] == {"contents": "read", "packages": "write"}
    assert not (ROOT / ".github/workflows/release.yaml").exists()


FAKE_DOCKER = """#!/usr/bin/env python3
import json
import os
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
    else:
        print(index)
elif args[0] == "tag" or args[:3] == ["buildx", "imagetools", "create"]:
    pass
else:
    raise SystemExit("Unexpected Docker operation: " + repr(args))
"""


@pytest.mark.parametrize("defect", ["", "identity", "platform", "push", "manifest"])
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
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "FAKE_STATE": str(tmp_path),
            "DEFECT": defect,
            "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
            "GITHUB_SHA": "1" * 40,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        },
        capture_output=True,
        text=True,
    )
    commands = [json.loads(line) for line in (tmp_path / "commands.jsonl").read_text().splitlines()]
    creates = [command for command in commands if command[:3] == ["buildx", "imagetools", "create"]]
    assert not any(command[:2] == ["buildx", "build"] for command in commands)
    if defect:
        assert result.returncode != 0
        assert not any(any(value.endswith(":latest") for value in command) for command in creates)
        if defect in {"identity", "platform"}:
            assert not any(command[0] == "push" for command in commands)
    else:
        assert result.returncode == 0, result.stderr
        assert len([command for command in commands if command[0] == "push"]) == 2
        assert len(creates) == 2
        assert any(value.endswith(":latest") for value in creates[-1])
        assert "sha-" + "1" * 40 in (tmp_path / "summary.md").read_text()
