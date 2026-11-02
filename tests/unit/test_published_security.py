"""Exercise published scanning through its CLI and the real runtime scanner."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEX = "sha256:" + "a" * 64
AMD64 = "sha256:" + "b" * 64
ARM64 = "sha256:" + "c" * 64
IMAGE = "ghcr.io/example/runtime"

FAKE_DOCKER = r"""#!/usr/bin/env -S python3 -S
import json
import os
import sys
from pathlib import Path

state = Path(os.environ["FAKE_DOCKER_STATE"])
args = sys.argv[1:]
with (state / "commands.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\n")
config = json.loads((state / "config.json").read_text())
if args[:3] == ["buildx", "imagetools", "inspect"]:
    if "--raw" in args:
        print(json.dumps(config["index"]))
    else:
        print(config["index_digest"])
elif args[0] == "pull":
    if config.get("pull_failure"):
        sys.exit(1)
elif args[:2] == ["image", "save"]:
    if config.get("digest_export_failure") and "@sha256:" in args[-1]:
        raise SystemExit("no suitable export target found for immutable child")
    arch = args[args.index("--platform") + 1].split("/")[1]
    (state / "arch").write_text(arch)
    Path(args[args.index("--output") + 1]).write_bytes(b"archive")
elif args[0] == "create":
    if "--image-src remote" in args[args.index("-c") + 1]:
        (state / "arch").write_text(args[-2].split("/")[1])
    print("scanner-container")
elif args[0] == "cp":
    if args[1].endswith(":/tmp/report.json"):
        arch = (state / "arch").read_text()
        Path(args[2]).write_text(json.dumps(config["reports"][arch]))
        if config.get("read_only_report"):
            Path(args[2]).chmod(0o444)
    elif args[1].endswith(":/tmp/sbom.cdx.json"):
        Path(args[2]).write_text(json.dumps({"bomFormat": "CycloneDX", "components": [{}]}))
    elif args[1].endswith(":/tmp/scanner-version.txt"):
        Path(args[2]).write_text("Version: test\n")
elif args[0] == "wait":
    failed = config.get("registry_failure") or (
        config.get("scan_failure") == (state / "arch").read_text()
    )
    print("1" if failed else "0")
elif args[0] == "logs":
    print(config.get("scanner_log", "Scanner log"))
elif args[0] == "start" and "--attach" in args and config.get("registry_failure"):
    sys.exit(1)
elif args[0] not in {"rm", "start"}:
    raise SystemExit("Unexpected Docker operation: " + repr(args))
"""


def vulnerability(**changes):
    return {
        "VulnerabilityID": "CVE-2026-1234",
        "PkgName": "example",
        "InstalledVersion": "1.0",
        "FixedVersion": "1.1",
        "Severity": "HIGH",
        **changes,
    }


def report(arch, vulnerabilities=(), secrets=()):
    return {
        "SchemaVersion": 2,
        "Metadata": {"ImageConfig": {"architecture": arch, "os": "linux"}},
        "Results": [
            {
                "Target": "/image.tar (debian 12)",
                "Class": "os-pkgs",
                "Type": "debian",
                "Vulnerabilities": list(vulnerabilities),
            },
            {"Target": "/app/config", "Class": "secret", "Secrets": list(secrets)},
        ],
    }


@pytest.fixture
def scan(tmp_path):
    config = {
        "index_digest": INDEX,
        "index": {
            "manifests": [
                {"digest": AMD64, "platform": {"os": "linux", "architecture": "amd64"}},
                {"digest": ARM64, "platform": {"os": "linux", "architecture": "arm64"}},
            ]
        },
        "reports": {arch: report(arch) for arch in ("amd64", "arm64")},
    }
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(FAKE_DOCKER)
    docker.chmod(0o755)
    output = tmp_path / "output"
    baseline = tmp_path / "baseline.json"
    baseline_run = tmp_path / "source-run-id"

    def execute(scanner_image=None, enforce=False, registry=True):
        (tmp_path / "config.json").write_text(json.dumps(config))
        arguments = [
            sys.executable,
            str(ROOT / "scripts/published_security.py"),
            "--image",
            IMAGE,
            "--output",
            str(output),
            "--baseline",
            str(baseline),
            "--baseline-run-id-file",
            str(baseline_run),
            "--run-id",
            "200",
        ]
        if scanner_image is not None:
            arguments = [
                sys.executable,
                str(ROOT / "scripts/scan_runtime.py"),
                scanner_image,
                "--platform",
                "linux/amd64",
                "--output",
                str(output / "security-amd64.json"),
            ]
            if registry:
                arguments.append("--registry")
            if enforce:
                arguments.append("--enforce")
        return subprocess.run(
            arguments,
            env={
                **os.environ,
                "PATH": f"{binary}:{os.environ['PATH']}",
                "FAKE_DOCKER_STATE": str(tmp_path),
            },
            capture_output=True,
            text=True,
            timeout=30,
        )

    def remember():
        state = json.loads((output / "state.json").read_text())
        state["run_id"] = "100"
        baseline.write_text(json.dumps(state))
        baseline_run.write_text("100")
        return state

    return config, execute, remember, output, baseline, baseline_run, tmp_path


def comparison(output):
    return json.loads((output / "comparison.json").read_text())


def test_scans_both_immutable_children_and_ignores_attestations(scan):
    config, execute, _, output, _, _, directory = scan
    config["index"]["manifests"].append(
        {
            "digest": "sha256:" + "d" * 64,
            "platform": {"os": "unknown", "architecture": "unknown"},
            "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
        }
    )
    result = execute()
    assert result.returncode == 0, result.stderr
    state = json.loads((output / "state.json").read_text())
    assert state["index_digest"] == INDEX
    assert state["manifests"] == {"linux/amd64": AMD64, "linux/arm64": ARM64}
    commands = [
        json.loads(line) for line in (directory / "commands.jsonl").read_text().splitlines()
    ]
    scanners = [args for args in commands if args[0] == "create"]
    assert [args[-2:] for args in scanners] == [
        ["linux/amd64", IMAGE + "@" + AMD64],
        ["linux/arm64", IMAGE + "@" + ARM64],
    ]
    assert ["buildx", "imagetools", "inspect", IMAGE + "@" + INDEX, "--raw"] in commands
    assert not list(output.glob("*.tar"))
    assert comparison(output)["baseline"] == "missing"


def test_registry_scanning_bypasses_incomplete_daemon_exports_without_socket_or_archive(scan):
    config, execute, _, output, _, _, directory = scan
    config["digest_export_failure"] = True
    result = execute()
    assert result.returncode == 0, result.stderr
    assert (output / "state.json").exists()
    commands = [
        json.loads(line) for line in (directory / "commands.jsonl").read_text().splitlines()
    ]
    assert not any(args[0] == "pull" or args[:2] == ["image", "save"] for args in commands)
    assert not any(args[0] == "cp" and args[2].endswith(":/tmp/runtime.tar") for args in commands)
    for args in (args for args in commands if args[0] == "create"):
        script = args[args.index("-c") + 1]
        assert "--image-src remote" in script
        assert '"$1"' in script and '"$2"' in script
        assert IMAGE not in script
        assert not any("docker.sock" in argument for argument in args)


@pytest.mark.parametrize(
    "image", [IMAGE + ":latest", IMAGE + "@sha256:invalid", IMAGE + "; touch /tmp/injected"]
)
def test_registry_scanner_rejects_mutable_or_invalid_references_before_docker(scan, image):
    _, execute, _, _, _, _, directory = scan
    result = execute(scanner_image=image)
    assert result.returncode != 0
    assert "immutable" in result.stderr
    assert not (directory / "commands.jsonl").exists()


@pytest.mark.parametrize("finding", ["clean", "unfixed", "fixable", "secret"])
def test_registry_scanner_preserves_runtime_enforcement_policy(scan, finding):
    config, execute, _, output, _, _, _ = scan
    if finding == "unfixed":
        config["reports"]["amd64"] = report("amd64", [vulnerability(FixedVersion="")])
    elif finding == "fixable":
        config["reports"]["amd64"] = report("amd64", [vulnerability()])
    elif finding == "secret":
        config["reports"]["amd64"] = report(
            "amd64", secrets=[{"RuleID": "example", "Match": "private"}]
        )
    result = execute(scanner_image=IMAGE + "@" + AMD64, enforce=True)
    assert (result.returncode != 0) == (finding in {"fixable", "secret"}), result.stderr
    assert (output / "security-amd64.summary.json").is_file()


def test_runtime_scanner_default_still_exports_and_copies_the_local_archive(scan):
    _, execute, _, output, _, _, directory = scan
    result = execute(scanner_image="mealie-mcp-server:local", registry=False)
    assert result.returncode == 0, result.stderr
    commands = [
        json.loads(line) for line in (directory / "commands.jsonl").read_text().splitlines()
    ]
    assert [
        "image",
        "save",
        "--platform",
        "linux/amd64",
        "--output",
        str(output / "security-amd64.tar"),
        "mealie-mcp-server:local",
    ] in commands
    assert [
        "cp",
        str(output / "security-amd64.tar"),
        "scanner-container:/tmp/runtime.tar",
    ] in commands


def test_registry_failure_retains_redacted_logs_after_a_nonzero_scanner_exit(scan):
    config, execute, _, output, _, _, _ = scan
    config["registry_failure"] = True
    config["scanner_log"] = "Download failed https://blob.example/image?signature=private-signature"
    result = execute(scanner_image=IMAGE + "@" + AMD64)
    assert result.returncode != 0
    log = output / "security-amd64.log"
    assert log.is_file()
    assert "Download failed [URL redacted]" in log.read_text()
    assert "private-signature" not in log.read_text() + result.stdout + result.stderr


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "bad-child", "bad-index", "attestation", "bad-annotations"]
)
def test_invalid_or_incomplete_platform_selection_never_creates_state(scan, defect):
    config, execute, _, output, _, _, _ = scan
    if defect == "missing":
        config["index"]["manifests"].pop()
    elif defect == "duplicate":
        config["index"]["manifests"].append(config["index"]["manifests"][0])
    elif defect == "bad-child":
        config["index"]["manifests"][0]["digest"] = "latest"
    elif defect == "bad-index":
        config["index_digest"] = "sha256:invalid"
    elif defect == "attestation":
        config["index"]["manifests"][0]["annotations"] = {
            "vnd.docker.reference.type": "attestation-manifest"
        }
    else:
        config["index"]["manifests"][0]["annotations"] = []
    result = execute()
    assert result.returncode != 0
    assert not (output / "state.json").exists()
    assert (output / "failure.txt").exists()
    if defect == "missing":
        assert (
            "Both published Linux architectures are required"
            in (output / "failure.txt").read_text()
        )


def test_only_actionable_policy_findings_become_new_without_a_baseline(scan):
    config, execute, _, output, _, _, _ = scan
    config["reports"]["amd64"] = report(
        "amd64",
        [
            vulnerability(),
            vulnerability(Severity="CRITICAL", FixedVersion=""),
            vulnerability(Severity="LOW"),
        ],
    )
    result = execute()
    assert result.returncode == 0, result.stderr
    change = comparison(output)
    assert len(change["new"]) == 1
    assert change["new"][0]["identity"]["package"] == "example"
    assert change["unchanged"] == []
    assert "New actionable findings: 1" in (output / "summary.md").read_text()


def test_digest_and_fix_release_changes_do_not_repeat_the_same_package_condition(scan):
    config, execute, remember, output, _, _, _ = scan
    config["reports"]["amd64"] = report("amd64", [vulnerability()])
    assert execute().returncode == 0
    remember()
    config["index_digest"] = "sha256:" + "e" * 64
    config["index"]["manifests"][0]["digest"] = "sha256:" + "f" * 64
    config["reports"]["amd64"] = report(
        "amd64", [vulnerability(FixedVersion="1.2", Severity="CRITICAL")]
    )
    config["reports"]["amd64"]["Results"][0]["Target"] = "/new-image.tar (debian 12)"
    result = execute()
    assert result.returncode == 0, result.stderr
    assert comparison(output)["new"] == []
    assert len(comparison(output)["unchanged"]) == 1


def test_changed_installed_version_is_new_and_previous_condition_is_resolved(scan):
    config, execute, remember, output, _, _, _ = scan
    config["reports"]["amd64"] = report("amd64", [vulnerability()])
    assert execute().returncode == 0
    remember()
    config["reports"]["amd64"] = report("amd64", [vulnerability(InstalledVersion="1.0.1")])
    assert execute().returncode == 0
    assert len(comparison(output)["new"]) == 1
    assert len(comparison(output)["resolved"]) == 1


def test_resolved_findings_do_not_fail_or_remain_in_the_next_baseline(scan):
    config, execute, remember, output, _, _, _ = scan
    config["reports"]["arm64"] = report("arm64", [vulnerability()])
    assert execute().returncode == 0
    remember()
    config["reports"]["arm64"] = report("arm64")
    assert execute().returncode == 0
    assert comparison(output)["new"] == []
    assert len(comparison(output)["resolved"]) == 1
    assert json.loads((output / "state.json").read_text())["findings"] == []


def test_secret_findings_are_actionable_without_exposing_matched_values(scan):
    config, execute, remember, output, _, _, _ = scan
    secret = "EXAMPLE-SECRET-VALUE-1234"
    config["reports"]["arm64"] = report(
        "arm64",
        secrets=[
            {
                "RuleID": "example-rule",
                "Category": "General",
                "Severity": "LOW",
                "Match": secret,
                "Code": {"Lines": [{"Content": secret}]},
            }
        ],
    )
    result = execute()
    assert result.returncode == 0, result.stderr
    assert len(comparison(output)["new"]) == 1
    for path in output.iterdir():
        assert secret not in path.read_text(), path
    assert secret not in result.stdout + result.stderr
    remember()
    assert execute().returncode == 0
    assert comparison(output)["new"] == []


def test_read_only_raw_report_never_leaves_a_secret_in_artifact_paths(scan):
    config, execute, _, output, _, _, _ = scan
    config["read_only_report"] = True
    secret = "EXAMPLE-PRIVATE-RAW-REPORT-1234"
    config["reports"]["amd64"] = report("amd64", secrets=[{"RuleID": "example", "Match": secret}])
    result = execute()
    for path in output.iterdir():
        assert secret not in path.read_text(), path
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "defect", ["scanner", "registry", "results", "metadata", "architecture", "record"]
)
def test_operational_or_invalid_scan_cannot_replace_a_valid_baseline(scan, defect):
    config, execute, remember, output, baseline, _, _ = scan
    assert execute().returncode == 0
    remember()
    previous = baseline.read_bytes()
    if defect == "scanner":
        config["scan_failure"] = "arm64"
    elif defect == "registry":
        config["registry_failure"] = True
    elif defect == "results":
        del config["reports"]["arm64"]["Results"]
    elif defect == "metadata":
        config["reports"]["arm64"]["Metadata"] = {}
    elif defect == "architecture":
        config["reports"]["arm64"]["Metadata"]["ImageConfig"]["architecture"] = "amd64"
    else:
        config["reports"]["arm64"] = report("arm64", [vulnerability(PkgName="")])
    assert execute().returncode != 0
    assert not (output / "state.json").exists()
    assert not (output / "comparison.json").exists()
    assert baseline.read_bytes() == previous


@pytest.mark.parametrize(
    "defect",
    [
        "incomplete",
        "malformed",
        "wrong-run",
        "wrong-branch",
        "wrong-workflow",
        "current-run",
        "wrong-image",
        "future",
        "fingerprint",
        "missing-provenance",
        "schema-boolean",
        "missing-scanner",
        "extra-finding-field",
    ],
)
def test_untrusted_or_malformed_prior_state_fails_visibly(scan, defect):
    config, execute, remember, output, baseline, baseline_run, _ = scan
    config["reports"]["amd64"] = report("amd64", [vulnerability()])
    assert execute().returncode == 0
    prior = remember()
    if defect == "incomplete":
        prior["complete"] = False
    elif defect == "wrong-run":
        prior["run_id"] = "99"
    elif defect == "wrong-branch":
        prior["branch"] = "untrusted"
    elif defect == "wrong-workflow":
        prior["workflow"] = "ci.yaml"
    elif defect == "current-run":
        prior["run_id"] = "200"
        baseline_run.write_text("200")
    elif defect == "wrong-image":
        prior["image"] = "ghcr.io/other/runtime"
    elif defect == "future":
        prior["scanned_at"] = "2999-01-01T00:00:00+00:00"
    elif defect == "fingerprint":
        prior["findings"][0]["fingerprint"] = "sha256:" + "0" * 64
    elif defect == "missing-provenance":
        baseline_run.unlink()
    elif defect == "schema-boolean":
        prior["schema"] = True
    elif defect == "missing-scanner":
        del prior["scanner"]
    elif defect == "extra-finding-field":
        prior["findings"][0]["Match"] = "untrusted raw secret"
    baseline.write_text("{invalid" if defect == "malformed" else json.dumps(prior))
    assert execute().returncode != 0
    assert not (output / "state.json").exists()


def test_expired_baseline_surfaces_all_current_actionable_findings(scan):
    config, execute, remember, output, baseline, _, _ = scan
    config["reports"]["amd64"] = report("amd64", [vulnerability()])
    assert execute().returncode == 0
    prior = remember()
    prior["scanned_at"] = "2000-01-01T00:00:00+00:00"
    baseline.write_text(json.dumps(prior))
    assert execute().returncode == 0
    assert comparison(output)["baseline"] == "expired"
    assert len(comparison(output)["new"]) == 1
