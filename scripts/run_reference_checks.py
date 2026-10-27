"""Verify the pinned upstream suite with a machine-readable report."""

import argparse
import json
import subprocess
from pathlib import Path
from uuid import uuid4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mealie-mcp-reference:upstream-d027e1b")
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    name = f"mealie-mcp-upstream-{uuid4().hex}"
    base = [
        "docker",
        "run",
        "--name",
        name,
        "--entrypoint",
        "/usr/local/bin/node",
        "--env",
        "MEALIE_BASE_URL=http://mealie-unconfigured.invalid",
        "--env",
        "MEALIE_API_KEY=reference-fixture-not-a-real-key",
        args.image,
    ]
    try:
        result = subprocess.run(
            base
            + [
                "node_modules/vitest/vitest.mjs",
                "run",
                "--reporter=json",
                "--outputFile=/tmp/vitest-report.json",
            ],
            capture_output=True,
            text=True,
            timeout=240,
        )
        (args.output / "upstream-vitest.log").write_text(result.stdout + result.stderr)
        report = args.output / "upstream-vitest.json"
        subprocess.run(["docker", "cp", f"{name}:/tmp/vitest-report.json", str(report)], check=True)
        data = json.loads(report.read_text())
        if result.returncode != 0 or not data["success"] or data["numFailedTests"] != 0:
            raise SystemExit("Upstream suite failed; inspect upstream-vitest.json.")
        summary = {
            "success": True,
            "passed": data["numPassedTests"],
            "failed": data["numFailedTests"],
            "files": len(data["testResults"]),
        }
        (args.output / "upstream-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))
        return 0
    finally:
        subprocess.run(["docker", "rm", name], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
