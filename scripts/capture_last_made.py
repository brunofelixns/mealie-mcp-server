"""Capture deterministic clock/time-zone examples from the pinned original pure function."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from scripts.capture_reference import REFERENCE_IMAGE, UPSTREAM_COMMIT

ROOT = Path("tests/fixtures/compatibility")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    target = ROOT / "last-made-reference.json"
    if target.exists() and not args.overwrite:
        raise ValueError("Reference exists; compare before using --overwrite.")
    cases = json.loads((ROOT / "last-made-inputs.json").read_text())
    results = []
    for zone in ("UTC", "Europe/Madrid"):
        selected = [case for case in cases if case["zone"] == zone]
        container = subprocess.check_output(
            [
                "docker",
                "create",
                "--env",
                f"TZ={zone}",
                REFERENCE_IMAGE,
                "node",
                "/tmp/last-made-oracle.mjs",
                "/tmp/inputs.json",
            ],
            text=True,
        ).strip()
        try:
            with tempfile.TemporaryDirectory(prefix="mealie-last-made-oracle-") as folder:
                inputs = Path(folder) / "inputs.json"
                inputs.write_text(json.dumps(selected))
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        "tests/reference/last-made-oracle.mjs",
                        container + ":/tmp/last-made-oracle.mjs",
                    ],
                    check=True,
                )
                subprocess.run(
                    ["docker", "cp", str(inputs), container + ":/tmp/inputs.json"], check=True
                )
                process = subprocess.run(
                    ["docker", "start", "--attach", container],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                status = subprocess.check_output(
                    ["docker", "inspect", "--format", "{{.State.ExitCode}}", container], text=True
                ).strip()
                if status != "0" or not process.stdout:
                    raise RuntimeError(
                        f"Original date oracle failed (exit {status}): {process.stderr}"
                    )
                captured = json.loads(process.stdout)
                if len(captured) != len(selected):
                    raise ValueError("Incomplete original date corpus.")
                results.extend(captured)
        finally:
            subprocess.run(["docker", "rm", container], check=True, capture_output=True)
    target.write_text(
        json.dumps(
            {"upstreamCommit": UPSTREAM_COMMIT, "cases": results}, ensure_ascii=False, indent=2
        )
        + "\n"
    )
    print(json.dumps({"cases": len(results), "zones": ["UTC", "Europe/Madrid"]}))


if __name__ == "__main__":
    main()
