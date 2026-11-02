"""Prepare a reproducible version commit for CI; never publish or push from here."""

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

SEMVER = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
RELEASE_SUBJECT = re.compile(rf"chore\(release\): {SEMVER}(?: \[skip ci\])?")
VERSION_FILES = ("pyproject.toml", "uv.lock", "Dockerfile", "README.md", "docs/README.es.md")


def next_version(current: str, messages: list[str]) -> str:
    if not re.fullmatch(SEMVER, current):
        raise ValueError(f"Unsupported release version: {current}")
    if not messages:
        raise ValueError("No unreleased commits")
    major, minor, patch = map(int, current.split("."))
    if any(
        re.match(r"^[a-z]+(?:\([^\n)]+\))?!:", message)
        or re.search(r"^BREAKING[ -]CHANGE:", message, re.MULTILINE)
        for message in messages
    ):
        return f"{major + 1}.0.0"
    if any(re.match(r"^(feat|fix)(?:\([^\n)]+\))?:", message) for message in messages):
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def git(root: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True, env=env).strip()


def replace_once(content: str, pattern: str, replacement: str) -> str:
    changed, count = re.subn(pattern, lambda _: replacement, content, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Expected one version field for {pattern}, got {count}")
    return changed


def prepare(root: Path, output: Path) -> dict[str, str]:
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Version preparation requires a clean checkout")
    source = git(root, "rev-parse", "HEAD")
    state_path = root / ".release.json"
    state = json.loads(state_path.read_text())
    base = state["base_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise ValueError("Invalid release anchor")
    git(root, "merge-base", "--is-ancestor", base, source)
    if "version" in state:
        # The merged release PR is the anchor, including squash/merge metadata.
        base = git(root, "log", "--first-parent", "-1", "--format=%H", "--", ".release.json")
    commits = git(root, "rev-list", "--reverse", f"{base}..{source}").splitlines()
    messages = [git(root, "show", "-s", "--format=%B", revision) for revision in commits]
    changes = [
        (revision, message)
        for revision, message in zip(commits, messages, strict=True)
        if not RELEASE_SUBJECT.fullmatch(message.splitlines()[0])
    ]
    project_path = root / "pyproject.toml"
    current = tomllib.loads(project_path.read_text())["project"]["version"]
    version = next_version(current, [message for _, message in changes])
    tag = "v" + version
    existing = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", f"refs/tags/{tag}"],
        check=False,
    )
    if existing.returncode != 1:
        raise ValueError(f"Release tag already exists or cannot be checked: {tag}")

    # Validate every replacement before changing any file. Dependency pins are untouched.
    contents = {
        project_path: replace_once(
            project_path.read_text(),
            rf'^version = "{re.escape(current)}"$',
            f'version = "{version}"',
        ),
        root / "uv.lock": replace_once(
            (root / "uv.lock").read_text(),
            rf'(?<=name = "mealie-mcp-server"\n)version = "{re.escape(current)}"$',
            f'version = "{version}"',
        ),
        root / "Dockerfile": replace_once(
            (root / "Dockerfile").read_text(),
            rf'org\.opencontainers\.image\.version="{re.escape(current)}"',
            f'org.opencontainers.image.version="{version}"',
        ),
    }
    for path, content in contents.items():
        path.write_text(content)
    subprocess.run([sys.executable, str(root / "scripts/generate_docs.py")], check=True)
    state_path.write_text(
        json.dumps({"base_revision": source, "version": version}, indent=2) + "\n"
    )
    git(root, "add", "--", *VERSION_FILES, ".release.json")
    timestamp = git(root, "show", "-s", "--format=%ct", source)
    environment = dict(os.environ)
    for role in ("AUTHOR", "COMMITTER"):
        environment[f"GIT_{role}_NAME"] = "github-actions[bot]"
        environment[f"GIT_{role}_EMAIL"] = "41898282+github-actions[bot]@users.noreply.github.com"
        environment[f"GIT_{role}_DATE"] = f"@{timestamp} +0000"
    git(
        root,
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-qm",
        f"chore(release): {version}",
        env=environment,
    )
    revision = git(root, "rev-parse", "HEAD")
    output.mkdir(parents=True, exist_ok=True)
    git(root, "bundle", "create", str(output / "release.bundle"), "HEAD", "^" + source)
    metadata = {"source": source, "revision": revision, "version": version, "tag": tag}
    (output / "release.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (output / "notes.md").write_text(
        f"# {tag}\n\n"
        + "\n".join(f"- {message.splitlines()[0]} ({sha[:12]})" for sha, message in changes)
        + f"\n\nSource: `{source}`\n\nRelease PR commit: `{revision}`\n"
        + "\nMerge this PR to release after the required checks pass.\n"
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve(), args.output.resolve())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
