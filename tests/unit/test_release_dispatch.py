import json
import os
import re
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
    sleeper = binary / "sleep"
    sleeper.write_text("#!/bin/sh\nexit 0\n")
    sleeper.chmod(0o755)
    return {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "FAKE_STATE": str(tmp_path),
        "GITHUB_REPOSITORY": "brunofelixns/mealie-mcp-server",
        "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
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


@pytest.mark.parametrize("delayed", [False, True])
def test_only_owned_release_please_proposals_are_reported_for_native_checks(tmp_path, delayed):
    response = (
        "if sys.argv[1] == 'api':\n"
        "    counter=root/'poll-count'\n"
        "    count=int(counter.read_text()) if counter.exists() else 0\n"
        "    counter.write_text(str(count+1))\n"
        f"    delayed={delayed!r} and count==0\n"
        "    print(json.dumps([] if delayed else ["
        "{'head':{'ref':'release-please--branches--main','repo':{'full_name':'brunofelixns/mealie-mcp-server'}},"
        "'html_url':'https://github.com/brunofelixns/mealie-mcp-server/pull/2',"
        "'labels':[{'name':'autorelease: pending'}]},"
        "{'head':{'ref':'fork-proposal','repo':{'full_name':'someone/fork'}},"
        "'html_url':'https://github.com/someone/fork/pull/3',"
        "'labels':[{'name':'autorelease: pending'}]}]))\n"
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
    assert not any(call[:2] == ["workflow", "run"] for call in calls)
    summary = (tmp_path / "summary.md").read_text()
    assert "https://github.com/brunofelixns/mealie-mcp-server/pull/2" in summary
    assert "checks start automatically" in summary
    assert "Approve workflows to run" not in summary
    assert "someone/fork" not in summary
    assert len([call for call in calls if call[0] == "api"]) == (2 if delayed else 1)


def test_missing_proposal_cannot_silently_skip_its_checks(tmp_path):
    env = fake_gh(tmp_path, "print('[]')\n")
    script = step("release-please.yaml", "release", "Check the Release Please proposal explicitly")
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert not any(call[:2] == ["workflow", "run"] for call in calls)
    assert len([call for call in calls if call[0] == "api"]) == 5


@pytest.mark.parametrize(
    ("repositories", "api_status"),
    [
        ("brunofelixns/mealie-mcp-server", 0),
        ("", 0),
        ("someone/fork", 0),
        ("brunofelixns/mealie-mcp-server\nother/repo", 0),
        ("brunofelixns/mealie-mcp-server", 1),
    ],
)
def test_app_token_scope_must_be_exactly_the_current_repository(tmp_path, repositories, api_status):
    env = fake_gh(tmp_path, f"print({repositories!r})\nsys.exit({api_status})\n")
    result = subprocess.run(
        [
            "bash",
            "-euo",
            "pipefail",
            "-c",
            step("release-please.yaml", "release", "Verify the App token repository scope"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    valid = repositories == env["GITHUB_REPOSITORY"] and api_status == 0
    assert (result.returncode == 0) == valid, result.stderr
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert calls == [
        ["api", "--paginate", "installation/repositories", "--jq", ".repositories[].full_name"]
    ]


def test_only_proposal_steps_receive_a_restricted_revoked_app_token():
    config = yaml.load(
        (ROOT / ".github/workflows/release-please.yaml").read_text(), Loader=yaml.BaseLoader
    )
    job = config["jobs"]["release"]
    assert job["env"]["GH_TOKEN"] == "${{ github.token }}"
    token_step = next(s for s in job["steps"] if s.get("id") == "app-token")
    assert re.fullmatch(r"actions/create-github-app-token@[0-9a-f]{40}", token_step["uses"])
    assert token_step["if"] == "steps.version.outputs.version != ''"
    assert token_step["with"] == {
        "client-id": "${{ vars.RELEASE_PLEASE_APP_CLIENT_ID }}",
        "private-key": "${{ secrets.RELEASE_PLEASE_APP_PRIVATE_KEY }}",
        "owner": "${{ github.repository_owner }}",
        "repositories": "${{ github.event.repository.name }}",
        "permission-contents": "write",
        "permission-pull-requests": "write",
        "skip-token-revoke": "false",
    }
    app_token_consumers = [
        s
        for s in job["steps"]
        if s.get("env", {}).get("GH_TOKEN") == "${{ steps.app-token.outputs.token }}"
    ]
    assert [s["name"] for s in app_token_consumers] == [
        "Verify the App token repository scope",
        "Maintain the accumulated Release Please PR",
    ]
    assert all(s["if"] == token_step["if"] for s in app_token_consumers)
    official = next(s for s in job["steps"] if s.get("id") == "release")
    assert official["with"]["token"] == "${{ github.token }}"


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
        packages = [argument for argument in arguments if argument.startswith("--package=")]
        assert len(packages) == 1
        assert re.fullmatch(r"--package=release-please@[0-9]+\.[0-9]+\.[0-9]+", packages[0])
        assert arguments[arguments.index("--release-as") + 1] == "0.3.0"
        assert arguments[arguments.index("--config-file") + 1] == "release-please-config.json"
