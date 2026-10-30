"""Check the Windows launcher in isolated PowerShell, from the Linux Dev Container."""

import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = (
    "mcr.microsoft.com/powershell:7.4-debian-12"
    "@sha256:206a748b34deec1b64553fcfa92294fc871c2df5855e9f340df172756bef201f"
)


def main():
    if sys.platform != "linux" or not Path("/.dockerenv").exists():
        raise RuntimeError("Run this check inside the Linux Dev Container")
    name = "mealie-mcp-launcher-check-" + uuid.uuid4().hex[:10]

    def docker(*args, check=True):
        return subprocess.run(
            ["docker", *args], cwd=ROOT, check=check, capture_output=True, text=True, timeout=300
        )

    docker("pull", POWERSHELL)
    try:
        docker(
            "create",
            "--name",
            name,
            "--network",
            "none",
            "--entrypoint",
            "pwsh",
            POWERSHELL,
            "-NoProfile",
            "-File",
            "/tmp/test_publish_local.ps1",
            "-Launcher",
            "/tmp/publish-local.ps1",
        )
        docker("cp", "tests/windows/test_publish_local.ps1", name + ":/tmp/test_publish_local.ps1")
        docker("cp", "scripts/publish-local.ps1", name + ":/tmp/publish-local.ps1")
        docker("start", "--attach", name, check=False)
        logs = docker("logs", name)
        print(logs.stdout + logs.stderr, end="", flush=True)
        return int(docker("inspect", "--format", "{{.State.ExitCode}}", name).stdout)
    finally:
        docker("rm", "--force", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
