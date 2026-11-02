"""Scan immutable published images and compare actionable findings with trusted evidence.

Run only inside the Dev Container. A complete scan writes state even when it has
new findings; the workflow uploads that state before applying its notification
gate. Operational failures write no state. No registry writes or image builds.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scan_runtime import SCANNER

PLATFORMS = ("linux/amd64", "linux/arm64")
WORKFLOW = ".github/workflows/published-security.yaml"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class SecurityError(ValueError):
    """An operational validation message safe to retain in workflow evidence."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise SecurityError(message)


def digest(value: Any) -> str:
    require(isinstance(value, str) and DIGEST.fullmatch(value), "Invalid immutable digest")
    return value


def text_field(value: Any) -> str:
    require(isinstance(value, str) and value.strip(), "Missing finding identity")
    return value


def fingerprint(kind: str, platform: str, identity: dict[str, str]) -> str:
    content = json.dumps([kind, platform, identity], sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


def select_manifests(index: Any) -> dict[str, str]:
    require(isinstance(index, dict), "Invalid image index")
    descriptors = index.get("manifests")
    require(isinstance(descriptors, list), "Published image must be a multi-platform index")
    selected = {}
    for descriptor in descriptors:
        require(isinstance(descriptor, dict), "Invalid image descriptor")
        annotations = descriptor.get("annotations", {})
        require(isinstance(annotations, dict), "Invalid image descriptor annotations")
        if annotations.get("vnd.docker.reference.type") == "attestation-manifest":
            continue
        platform = descriptor.get("platform", {})
        require(isinstance(platform, dict), "Invalid descriptor platform")
        name = f"{platform.get('os')}/{platform.get('architecture')}"
        if name not in PLATFORMS:
            continue
        require(name not in selected, "Duplicate image platform")
        selected[name] = digest(descriptor.get("digest"))
    require(set(selected) == set(PLATFORMS), "Both published Linux architectures are required")
    return selected


def actionable(report: Any, platform: str) -> list[dict[str, Any]]:
    require(isinstance(report, dict) and report.get("SchemaVersion") == 2, "Invalid scan report")
    metadata = report.get("Metadata", {})
    require(isinstance(metadata, dict), "Invalid image metadata")
    config = metadata.get("ImageConfig", {})
    require(
        isinstance(config, dict)
        and config.get("os") == "linux"
        and config.get("architecture") == platform.split("/")[1],
        "Scan architecture does not match the selected image",
    )
    results = report.get("Results")
    require(isinstance(results, list), "Incomplete image scan")
    findings = {}
    for result in results:
        require(isinstance(result, dict), "Invalid scan result")
        for field, kind in (("Vulnerabilities", "vulnerability"), ("Secrets", "secret")):
            records = result.get(field, [])
            require(isinstance(records, list), "Invalid finding list")
            for record in records:
                require(isinstance(record, dict), "Invalid finding")
                if kind == "vulnerability":
                    require(
                        record.get("Severity") in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"},
                        "Invalid vulnerability severity",
                    )
                    if record["Severity"] not in {"HIGH", "CRITICAL"} or not record.get(
                        "FixedVersion"
                    ):
                        continue
                    identity = {
                        "type": text_field(result.get("Type")),
                        "package": text_field(record.get("PkgName")),
                        "installed_version": text_field(record.get("InstalledVersion")),
                        "vulnerability": text_field(record.get("VulnerabilityID")),
                        "path": record.get("PkgPath")
                        or (
                            ""
                            if result.get("Class") == "os-pkgs"
                            else text_field(result.get("Target"))
                        ),
                    }
                    require(isinstance(identity["path"], str), "Invalid package path")
                else:
                    match = text_field(record.get("Match"))
                    identity = {
                        "target": text_field(result.get("Target")),
                        "rule": text_field(record.get("RuleID")),
                        "match_digest": "sha256:" + hashlib.sha256(match.encode()).hexdigest(),
                    }
                key = fingerprint(kind, platform, identity)
                findings[key] = {
                    "fingerprint": key,
                    "kind": kind,
                    "platform": platform,
                    "identity": identity,
                }
    return [findings[key] for key in sorted(findings)]


def redact_report(path: Path, destination: Path) -> None:
    """Keep diagnostic finding identities, never raw matches or image environment."""
    if not path.exists():
        return
    try:
        report = json.loads(path.read_text())
        safe: dict[str, Any] = {"SchemaVersion": report.get("SchemaVersion"), "Results": []}
        for result in report.get("Results", []):
            entry = {key: result[key] for key in ("Target", "Class", "Type") if key in result}
            entry["Vulnerabilities"] = [
                {
                    key: record[key]
                    for key in (
                        "VulnerabilityID",
                        "PkgName",
                        "InstalledVersion",
                        "FixedVersion",
                        "Severity",
                        "PkgPath",
                    )
                    if key in record
                }
                for record in result.get("Vulnerabilities", [])
            ]
            entry["Secrets"] = [
                {
                    key: record[key]
                    for key in ("RuleID", "Category", "Severity", "StartLine", "EndLine")
                    if key in record
                }
                for record in result.get("Secrets", [])
            ]
            safe["Results"].append(entry)
        destination.write_text(json.dumps(safe, indent=2) + "\n")
    except ValueError, TypeError, AttributeError:
        destination.unlink(missing_ok=True)


def load_baseline(
    path: Path, provenance: Path, image: str, run_id: str
) -> tuple[list[dict[str, Any]], str]:
    if not path.exists() and not provenance.exists():
        return [], "missing"
    require(path.is_file() and provenance.is_file(), "Baseline provenance is incomplete")
    previous = json.loads(path.read_text())
    source_run = provenance.read_text().strip()
    require(isinstance(previous, dict), "Invalid baseline")
    require(
        set(previous)
        == {
            "schema",
            "complete",
            "workflow",
            "branch",
            "run_id",
            "image",
            "index_digest",
            "manifests",
            "scanned_at",
            "scanner",
            "findings",
        },
        "Invalid baseline fields",
    )
    require(
        type(previous.get("schema")) is int
        and previous["schema"] == 1
        and previous.get("complete") is True
        and previous.get("workflow") == WORKFLOW
        and previous.get("branch") == "main"
        and previous.get("image") == image
        and source_run.isdecimal()
        and previous.get("run_id") == source_run
        and int(source_run) < int(run_id),
        "Baseline must come from a prior completed main workflow run",
    )
    digest(previous.get("index_digest"))
    require(
        isinstance(previous["scanner"], str)
        and re.fullmatch(r"aquasec/trivy:[^@\s]+@sha256:[0-9a-f]{64}", previous["scanner"]),
        "Invalid baseline scanner identity",
    )
    manifests = previous.get("manifests")
    require(isinstance(manifests, dict) and set(manifests) == set(PLATFORMS), "Incomplete baseline")
    for value in manifests.values():
        digest(value)
    findings = previous.get("findings")
    require(isinstance(findings, list), "Invalid baseline findings")
    seen = set()
    for finding in findings:
        require(isinstance(finding, dict), "Invalid baseline finding")
        require(
            set(finding) == {"fingerprint", "kind", "platform", "identity"},
            "Invalid baseline finding fields",
        )
        kind, platform, identity = (
            finding.get("kind"),
            finding.get("platform"),
            finding.get("identity"),
        )
        require(
            kind in {"vulnerability", "secret"} and platform in PLATFORMS, "Invalid finding type"
        )
        fields = (
            {"type", "package", "installed_version", "vulnerability", "path"}
            if kind == "vulnerability"
            else {"target", "rule", "match_digest"}
        )
        require(isinstance(identity, dict) and set(identity) == fields, "Invalid baseline identity")
        for key, value in identity.items():
            if key != "path":
                text_field(value)
            require(isinstance(value, str), "Invalid baseline identity value")
        if kind == "secret":
            digest(identity["match_digest"])
        key = fingerprint(kind, platform, identity)
        require(
            finding.get("fingerprint") == key and key not in seen, "Invalid baseline fingerprint"
        )
        seen.add(key)
    scanned_at = datetime.fromisoformat(previous["scanned_at"])
    require(scanned_at.tzinfo is not None, "Baseline timestamp must include its timezone")
    age = datetime.now(UTC) - scanned_at
    require(age >= -timedelta(minutes=5), "Baseline timestamp is in the future")
    if age > timedelta(days=90):
        return [], "expired"
    return findings, "available"


def command(*arguments: str) -> str:
    return subprocess.run(
        arguments, capture_output=True, text=True, check=True, timeout=900
    ).stdout.strip()


def scan_image(image: str, manifest: str, platform: str, output: Path) -> list[dict[str, Any]]:
    reference = image + "@" + manifest
    arch = platform.split("/")[1]
    for path in output.glob(f"security-{arch}.*"):
        path.unlink()
    # Raw matches, image environment and archive never enter an upload path.
    with tempfile.TemporaryDirectory(prefix="published-security-") as directory:
        report = Path(directory) / f"security-{arch}.json"
        try:
            with (output / f"security-{arch}.execution.log").open("w") as log:
                subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).with_name("scan_runtime.py")),
                        reference,
                        "--registry",
                        "--platform",
                        platform,
                        "--output",
                        str(report),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=1800,
                )
            findings = actionable(json.loads(report.read_text()), platform)
        finally:
            redact_report(report, output / report.name)
            for suffix in (".summary.json", ".sbom.cdx.json", ".version.txt", ".log"):
                evidence = report.with_suffix(suffix)
                if evidence.exists():
                    shutil.copyfile(evidence, output / evidence.name)
        require((output / report.name).is_file(), "Unable to retain a sanitized image report")
        return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="GHCR repository, without tag or digest")
    parser.add_argument("--output", type=Path, default=Path("artifacts/published-security"))
    parser.add_argument(
        "--baseline", type=Path, default=Path("artifacts/published-baseline/state.json")
    )
    parser.add_argument(
        "--baseline-run-id-file",
        type=Path,
        default=Path("artifacts/published-baseline/source-run-id"),
    )
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("state.json", "comparison.json", "summary.md", "failure.txt"):
        (args.output / name).unlink(missing_ok=True)
    try:
        require(
            re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9._/-]*", args.image), "Invalid GHCR repository"
        )
        require(args.run_id.isdecimal() and int(args.run_id) > 0, "Invalid workflow run ID")
        prior, baseline = load_baseline(
            args.baseline, args.baseline_run_id_file, args.image, args.run_id
        )
        index = digest(
            command(
                "docker",
                "buildx",
                "imagetools",
                "inspect",
                args.image + ":latest",
                "--format",
                "{{.Manifest.Digest}}",
            )
        )
        manifests = select_manifests(
            json.loads(
                command(
                    "docker", "buildx", "imagetools", "inspect", args.image + "@" + index, "--raw"
                )
            )
        )
        findings = []
        for platform in PLATFORMS:
            findings.extend(scan_image(args.image, manifests[platform], platform, args.output))
        current = {item["fingerprint"]: item for item in findings}
        previous = {item["fingerprint"]: item for item in prior}
        change = {
            "baseline": baseline,
            "new": [current[key] for key in sorted(current.keys() - previous.keys())],
            "unchanged": [current[key] for key in sorted(current.keys() & previous.keys())],
            "resolved": [previous[key] for key in sorted(previous.keys() - current.keys())],
        }
        state = {
            "schema": 1,
            "complete": True,
            "workflow": WORKFLOW,
            "branch": "main",
            "run_id": args.run_id,
            "image": args.image,
            "index_digest": index,
            "manifests": manifests,
            "scanned_at": datetime.now(UTC).isoformat(),
            "scanner": SCANNER,
            "findings": findings,
        }
        (args.output / "comparison.json").write_text(json.dumps(change, indent=2) + "\n")
        summary = (
            "### Published image security\n\n"
            f"Image: `{args.image}@{index}`\n\n"
            f"Baseline: {baseline}\n\n"
            f"New actionable findings: {len(change['new'])}\n\n"
            f"Unchanged actionable findings: {len(change['unchanged'])}\n\n"
            f"Resolved actionable findings: {len(change['resolved'])}\n\n"
            "Policy: secrets and fixable HIGH/CRITICAL vulnerabilities, "
            "across both architectures.\n"
        )
        (args.output / "summary.md").write_text(summary)
        # Written last: neither partial scans nor invalid prior evidence can become a baseline.
        (args.output / "state.json").write_text(json.dumps(state, indent=2) + "\n")
        print(summary)
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        message = (
            f"Published image scan failed operationally ({type(error).__name__}); "
            "no new baseline was saved.\n"
        )
        if isinstance(error, SecurityError):
            message += str(error) + "\n"
        (args.output / "failure.txt").write_text(message)
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
