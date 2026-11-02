"""Calculate Release Please's release-as override; never edit or publish versions."""

import argparse
import json
import re
import subprocess
from pathlib import Path

SEMVER = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"


def next_version(current: str, messages: list[str]) -> str:
    if not re.fullmatch(SEMVER, current):
        raise ValueError(f"Unsupported release version: {current}")
    if not messages:
        return ""
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


def version_for_repository(root: Path) -> str:
    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()

    config = json.loads((root / "release-please-config.json").read_text())
    current = json.loads((root / ".release-please-manifest.json").read_text())["."]
    if current == config["packages"]["."]["initial-version"]:
        base = config["bootstrap-sha"]
    else:
        base = git(
            "log", "--first-parent", "-1", "--format=%H", "--", ".release-please-manifest.json"
        )
    git("merge-base", "--is-ancestor", base, "HEAD")
    commits = git("rev-list", "--reverse", f"{base}..HEAD").splitlines()
    messages = [git("show", "-s", "--format=%B", revision) for revision in commits]
    return next_version(current, messages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    print(version_for_repository(parser.parse_args().root))
