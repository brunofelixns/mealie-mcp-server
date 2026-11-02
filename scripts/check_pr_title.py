"""Validate a PR event title against the repository's Release Please types.

The event file is data, never shell input. Do not print the untrusted title into
Actions logs, where embedded workflow commands could acquire another meaning.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = re.compile(r"(?P<type>[a-z]+)(?:\((?P<scope>[^()]+)\))?!?: (?P<description>\S(?:.*\S)?)")


def configured_types(config_path: Path) -> set[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    try:
        sections = config["packages"]["."]["changelog-sections"]
        types = {section["type"] for section in sections}
    except (KeyError, TypeError) as error:
        raise ValueError("Release Please configuration must define release types") from error
    if not types or any(
        not isinstance(kind, str) or not re.fullmatch("[a-z]+", kind) for kind in types
    ):
        raise ValueError("Release Please configuration must define valid release types")
    return types


def validate_title(title: object, allowed_types: set[str]) -> None:
    if not isinstance(title, str) or not title or not title.isprintable():
        raise ValueError("use a nonempty, printable single line")
    match = TITLE.fullmatch(title)
    if not match or title != title.strip():
        raise ValueError("use type(scope)!: description with an optional scope and breaking marker")
    if match["type"] not in allowed_types:
        raise ValueError(
            "type must be configured in Release Please: " + ", ".join(sorted(allowed_types))
        )
    scope = match["scope"]
    if scope is not None and scope != scope.strip():
        raise ValueError("scope must not start or end with whitespace")
    description = match["description"]
    if description[0].isupper() or description.endswith("."):
        raise ValueError("start the description in lowercase and omit a final period")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=Path, default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--config", type=Path, default=ROOT / "release-please-config.json")
    args = parser.parse_args()
    try:
        if args.event is None:
            raise ValueError("provide --event or GITHUB_EVENT_PATH")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        if not isinstance(event, dict) or not isinstance(event.get("pull_request"), dict):
            raise ValueError("event must contain a pull_request object")
        validate_title(event["pull_request"].get("title"), configured_types(args.config))
    except (OSError, ValueError) as error:
        # The errors above never contain the PR title or event contents.
        print(f"Invalid PR title: {error}", file=sys.stderr)
        return 1
    print("PR title follows the configured release convention.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
