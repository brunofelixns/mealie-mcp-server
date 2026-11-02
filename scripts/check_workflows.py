"""Lint workflows using pinned disposable tools, without sharing the Docker socket."""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTIONLINT = (
    "rhysd/actionlint:1.7.12@"
    "sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667"
)
ZIZMOR = (
    "ghcr.io/zizmorcore/zizmor:1.31.1@"
    "sha256:42d409dbb851d4c5d35a058cf042b828bea1e3f2884378c526eb0974780e18d9"
)


def check_queue_scope(files: list[Path]) -> None:
    """Do not let the parser exception hide queue settings outside the publisher."""
    for path in files:
        config = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        if "queue" in config.get("concurrency", {}):
            raise ValueError("queue is only allowed in ci.yaml publisher concurrency")
        for name, job in config.get("jobs", {}).items():
            concurrency = job.get("concurrency", {})
            if "queue" in concurrency and not (
                path.name == "ci.yaml" and name == "publish" and concurrency["queue"] == "max"
            ):
                raise ValueError("queue is only allowed in ci.yaml publisher concurrency")


def run_tool(image: str, *arguments: str) -> None:
    container = subprocess.check_output(
        [
            "docker",
            "create",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--workdir",
            "/repo",
            image,
            *arguments,
        ],
        text=True,
        timeout=180,
    ).strip()
    try:
        subprocess.run(
            ["docker", "cp", str(ROOT / ".github"), container + ":/repo/.github"],
            check=True,
            timeout=60,
        )
        subprocess.run(["docker", "start", container], check=True, capture_output=True, timeout=30)
        status = subprocess.check_output(["docker", "wait", container], text=True, timeout=180)
        subprocess.run(["docker", "logs", container], check=True, timeout=30)
        if status.strip() != "0":
            raise RuntimeError(f"Workflow lint failed: {image}")
    finally:
        subprocess.run(["docker", "rm", "--force", container], check=False, capture_output=True)


if __name__ == "__main__":
    paths = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    check_queue_scope(paths)
    files = [".github/workflows/" + path.name for path in paths]
    run_tool(ACTIONLINT, "-color", "-config-file", ".github/actionlint.yaml", *files)
    run_tool(ZIZMOR, "--offline", "--no-progress", ".github/workflows")
