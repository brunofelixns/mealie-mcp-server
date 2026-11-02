import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def step(workflow, job, name):
    config = yaml.load((ROOT / ".github/workflows" / workflow).read_text(), Loader=yaml.BaseLoader)
    return next(s["run"] for s in config["jobs"][job]["steps"] if s.get("name") == name)


def fake_gh(tmp_path, response):
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "gh"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json,os,sys,pathlib\n"
        "root=pathlib.Path(os.environ['FAKE_STATE'])\n"
        "with (root/'calls.jsonl').open('a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:])+'\\n')\n" + response
    )
    executable.chmod(0o755)
    return {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "FAKE_STATE": str(tmp_path),
        "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
    }


@pytest.mark.parametrize("case", ["valid", "version", "revision", "non-semver", "draft"])
def test_publisher_requires_matching_tested_version_revision_and_existing_release(tmp_path, case):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "source.txt").touch()
    git("add", ".")
    git("commit", "-qm", "chore(main): release 0.2.0")
    revision = git("rev-parse", "HEAD")
    git("tag", "v0.2.0")
    images = tmp_path / "artifacts/images"
    images.mkdir(parents=True)
    for arch in ("amd64", "arm64"):
        metadata = {"version": "0.2.0", "revision": revision}
        if case == "version" and arch == "arm64":
            metadata["version"] = "0.3.0"
        elif case == "revision" and arch == "arm64":
            metadata["revision"] = "b" * 40
        elif case == "non-semver":
            metadata["version"] = "not-a-version"
        (images / f"runtime-{arch}.json").write_text(json.dumps(metadata))
    env = fake_gh(tmp_path, "print('true')\n" if case == "draft" else "print('false')\n")
    env.update(GITHUB_SHA=revision, RELEASE_TAG="v0.2.0")
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step("ci.yaml", "publish", "Read the tested version")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (case == "valid"), result.stderr
    if case == "valid":
        assert (tmp_path / "output.txt").read_text() == "version=0.2.0\n"


def test_only_owned_release_please_proposals_are_dispatched(tmp_path):
    response = (
        "if sys.argv[1:3] == ['pr','list']: print(json.dumps(["
        "{'headRefName':'release-please--branches--main','isCrossRepository':False},"
        "{'headRefName':'fork-proposal','isCrossRepository':True}]))\n"
    )
    env = fake_gh(tmp_path, response)
    script = step("release-please.yaml", "release", "Check the Release Please proposal explicitly")
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    dispatches = [call for call in calls if call[:2] == ["workflow", "run"]]
    assert len(dispatches) == 1
    assert dispatches[0][-1] == "release-please--branches--main"


@pytest.mark.parametrize("stale", [False, True])
def test_official_cli_receives_policy_override_only_for_current_main(tmp_path, stale):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git("init", "-qb", "main")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    (tmp_path / "source.txt").touch()
    git("add", "source.txt")
    git("commit", "-qm", "feat: source")
    source = git("rev-parse", "HEAD")
    git("remote", "add", "origin", str(remote))
    git("push", "-q", "origin", "HEAD:refs/heads/main")
    if stale:
        (tmp_path / "source.txt").write_text("new main")
        git("commit", "-qam", "feat: later change")
        git("push", "-q", "origin", "HEAD:refs/heads/main")
        git("checkout", "--detach", source)
    binary = tmp_path / "bin"
    binary.mkdir()
    npx = binary / "npx"
    npx.write_text(
        "#!/usr/bin/env python3\nimport json,pathlib,sys\n"
        "pathlib.Path('npx.json').write_text(json.dumps(sys.argv[1:]))\n"
    )
    npx.chmod(0o755)
    result = subprocess.run(
        [
            "bash",
            "-euo",
            "pipefail",
            "-c",
            step(
                "release-please.yaml",
                "release",
                "Maintain the accumulated Release Please PR",
            ),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "GH_TOKEN": "fixture-only",
            "GITHUB_REPOSITORY": "owner/repo",
            "RELEASE_VERSION": "0.3.0",
        },
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (not stale), result.stderr
    if stale:
        assert not (tmp_path / "npx.json").exists()
    else:
        arguments = json.loads((tmp_path / "npx.json").read_text())
        assert "--package=release-please@17.11.2" in arguments
        assert arguments[arguments.index("--release-as") + 1] == "0.3.0"
        assert arguments[arguments.index("--config-file") + 1] == "release-please-config.json"
