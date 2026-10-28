"""Scan an exported image without granting a scanner access to the Docker socket.

Run inside the Dev Container. The scanner owns only its disposable container and
an image archive copied through the Docker API; no host filesystem bind mounts.
"""

import argparse
import json
import platform
import subprocess
from pathlib import Path

SCANNER = (
    "aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c"
)


def docker(*arguments: str, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, check=True, timeout=timeout
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--platform", choices=["linux/amd64", "linux/arm64"], default="linux/amd64")
    parser.add_argument("--output", type=Path, default=Path("artifacts/runtime-security.json"))
    parser.add_argument(
        "--enforce", action="store_true", help="fail on secrets or fixable HIGH/CRITICAL findings"
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    archive = args.output.with_suffix(".tar")
    scanner_platform = (
        "linux/arm64" if platform.machine() in {"aarch64", "arm64"} else "linux/amd64"
    )
    docker("image", "save", "--platform", args.platform, "--output", str(archive), args.image)
    container = docker(
        "create",
        "--platform",
        scanner_platform,
        "--entrypoint",
        "/bin/sh",
        SCANNER,
        "-c",
        "trivy image --input /tmp/runtime.tar --scanners vuln,secret --list-all-pkgs "
        "--format json --output /tmp/report.json --timeout 10m && "
        "trivy convert --format cyclonedx --output /tmp/sbom.cdx.json /tmp/report.json && "
        "trivy --version > /tmp/scanner-version.txt",
    ).stdout.strip()
    try:
        docker("cp", str(archive), container + ":/tmp/runtime.tar")
        docker("start", "--attach", container)
        exit_code = docker("wait", container).stdout.strip()
        logs = docker("logs", container)
        args.output.with_suffix(".log").write_text(logs.stdout + logs.stderr)
        if exit_code != "0":
            raise RuntimeError("Image scan failed; inspect its log.")
        docker("cp", container + ":/tmp/report.json", str(args.output))
        sbom_path = args.output.with_suffix(".sbom.cdx.json")
        docker("cp", container + ":/tmp/sbom.cdx.json", str(sbom_path))
        docker(
            "cp",
            container + ":/tmp/scanner-version.txt",
            str(args.output.with_suffix(".version.txt")),
        )
        sbom = json.loads(sbom_path.read_text())
        if sbom.get("bomFormat") != "CycloneDX" or not sbom.get("components"):
            raise RuntimeError("Scanner did not produce a complete CycloneDX SBOM.")
        report = json.loads(args.output.read_text())
        if not report.get("Metadata") or "Results" not in report:
            raise RuntimeError("Scanner did not produce a complete image report.")
        vulnerabilities = [
            item for result in report["Results"] for item in result.get("Vulnerabilities", [])
        ]
        secrets = [item for result in report["Results"] for item in result.get("Secrets", [])]
        summary = {
            "scanner": SCANNER,
            "image": args.image,
            "platform": args.platform,
            "report": str(args.output),
            "sbom": str(sbom_path),
            "sbomComponents": len(sbom["components"]),
            "vulnerabilities": len(vulnerabilities),
            "critical": sum(item["Severity"] == "CRITICAL" for item in vulnerabilities),
            "high": sum(item["Severity"] == "HIGH" for item in vulnerabilities),
            "secretFindings": len(secrets),
            "fixableHighCritical": sum(
                item["Severity"] in {"HIGH", "CRITICAL"} and bool(item.get("FixedVersion"))
                for item in vulnerabilities
            ),
        }
        args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))
        if args.enforce and (secrets or summary["fixableHighCritical"]):
            raise RuntimeError(
                "Image has secret findings or fixable HIGH/CRITICAL vulnerabilities."
            )
    finally:
        subprocess.run(["docker", "rm", "--force", container], check=False, capture_output=True)


if __name__ == "__main__":
    main()
