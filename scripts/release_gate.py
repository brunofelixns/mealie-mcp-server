"""Prevent publishing an incomplete migration or a mismatched package version."""

import argparse
import json
import sys
import tomllib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state", type=Path, default=Path("docs/migration/implementation-state.json")
    )
    parser.add_argument("--project", type=Path, default=Path("pyproject.toml"))
    parser.add_argument("--release-version", required=True)
    args = parser.parse_args()
    try:
        tasks = json.loads(args.state.read_text())["tasks"]
        if len(tasks) != 24 or {task["id"] for task in tasks} != {
            f"P{number:02}" for number in range(1, 25)
        }:
            raise ValueError("all 24 unique migration tasks are required")
        if any(task["status"] != "verified" for task in tasks):
            raise ValueError("migration has pending tasks")
        version = tomllib.loads(args.project.read_text())["project"]["version"]
        if args.release_version != version:
            raise ValueError("release version must equal the package version")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Release gate: {error}", file=sys.stderr)
        return 1
    print("Release gate: 24 tasks verified; package version matches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
