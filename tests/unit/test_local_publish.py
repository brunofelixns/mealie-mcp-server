import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from tests.support.version import PROJECT_VERSION

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


images = load_script("release_images")
release = load_script("publish_local")
ReleaseError = images.ReleaseError
archive_evidence = images.archive_evidence
validate_manifest = images.validate_manifest


def descriptor(arch="amd64", digest="sha256:" + "1" * 64):
    return {"digest": digest, "platform": {"os": "linux", "architecture": arch}}


def make_archive(path, predicates, arch="amd64"):
    blobs = {}

    def blob(value):
        data = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        blobs["blobs/sha256/" + digest.removeprefix("sha256:")] = data
        return {"digest": digest}

    runtime = {**blob({"layers": []}), "platform": {"os": "linux", "architecture": arch}}
    layers = [
        blob(
            {
                "predicateType": value,
                "predicate": {"spdxVersion": "SPDX-2.3", "packages": [{"name": "fixture"}]}
                if "spdx" in value
                else {"buildType": "fixture-build"},
            }
        )
        for value in predicates
    ]
    attestation = {
        **blob({"layers": layers}),
        "platform": {"os": "unknown", "architecture": "unknown"},
        "annotations": {
            "vnd.docker.reference.type": "attestation-manifest",
            "vnd.docker.reference.digest": runtime["digest"],
        },
    }
    index = blob({"manifests": [runtime, attestation]})
    with tarfile.open(path, "w") as archive:
        for name, data in blobs.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return index["digest"], runtime["digest"]


def test_oci_archive_requires_real_sbom_and_provenance_payloads(tmp_path):
    path = tmp_path / "runtime.tar"
    digest, runtime = make_archive(
        path, ["https://spdx.dev/Document", "https://slsa.dev/provenance/v0.2"]
    )
    evidence = archive_evidence(path, digest, "amd64")
    assert evidence["runtimeDigest"] == runtime
    assert evidence["sbom"] is True and evidence["provenance"] is True


@pytest.mark.parametrize("defect", ["no_sbom", "no_provenance", "wrong_arch", "wrong_digest"])
def test_incomplete_or_mismatched_oci_is_rejected(tmp_path, defect):
    path = tmp_path / "runtime.tar"
    predicates = ["https://spdx.dev/Document", "https://slsa.dev/provenance/v0.2"]
    if defect == "no_sbom":
        predicates.pop(0)
    if defect == "no_provenance":
        predicates.pop()
    digest, _ = make_archive(path, predicates, "arm64" if defect == "wrong_arch" else "amd64")
    if defect == "wrong_digest":
        digest = "sha256:" + "f" * 64
    with pytest.raises(ReleaseError):
        archive_evidence(path, digest, "amd64")


@pytest.mark.parametrize("defect", ["missing", "duplicate", "wrong_digest", "unexpected_platform"])
def test_remote_manifest_must_reference_both_tested_runtime_digests(defect):
    expected = {"amd64": "sha256:" + "1" * 64, "arm64": "sha256:" + "2" * 64}
    rows = [descriptor(arch, digest) for arch, digest in expected.items()]
    if defect == "missing":
        rows.pop()
    if defect == "duplicate":
        rows.append(rows[0])
    if defect == "wrong_digest":
        rows[1]["digest"] = "sha256:" + "3" * 64
    if defect == "unexpected_platform":
        rows[1]["platform"]["architecture"] = "s390x"
    with pytest.raises(ReleaseError):
        validate_manifest({"manifests": rows}, expected)


def test_dry_run_never_executes_commands(capsys, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run executed a subprocess")

    monkeypatch.setattr(release.subprocess, "run", forbidden)
    assert release.main(["--dry-run", "--publish"]) == 0
    output = capsys.readouterr().out
    assert "linux/amd64" in output and "linux/arm64" in output
    assert "docker push" in output and "imagetools create" in output
    assert "docker login" not in output


@pytest.mark.parametrize(
    "args",
    [
        ["--version", "9.9.9"],
        ["--image", "docker.io/other/project"],
        ["--image", "ghcr.io/User/Project"],
        ["--builder", "--push"],
    ],
)
def test_invalid_release_arguments_fail_before_commands(args, monkeypatch):
    monkeypatch.setattr(
        release.subprocess, "run", lambda *a, **kw: pytest.fail("subprocess called")
    )
    assert release.main(["--dry-run", *args]) != 0


class PreparedRelease(release.Release):
    def preflight(self):
        self.original = {"revision": "a" * 40, "fingerprint": "b" * 64, "dirty": False}

    def checks(self):
        pass

    def build_images(self):
        return {"amd64": {"id": "first"}, "arm64": {"id": "second"}}

    def verify_images(self):
        pass

    def source_unchanged(self):
        pass

    def publish_images(self):
        self.did_publish = True


@pytest.mark.parametrize(
    "stage", ["preflight", "checks", "build_images", "verify_images", "source_unchanged"]
)
def test_any_local_gate_failure_prevents_all_publication(tmp_path, monkeypatch, stage):
    def fail(self):
        raise ReleaseError("test gate failed")

    monkeypatch.setattr(PreparedRelease, stage, fail)
    task = PreparedRelease(release.options([]), tmp_path, publish=True)
    assert task.execute() == 1
    assert not getattr(task, "did_publish", False)
    assert json.loads((tmp_path / "summary.json").read_text())["status"] == "failed"


def test_default_execution_only_verifies_locally(tmp_path):
    task = PreparedRelease(release.options([]), tmp_path, publish=False)
    assert task.execute() == 0
    assert not getattr(task, "did_publish", False)
    assert json.loads((tmp_path / "summary.json").read_text())["status"] == "verified_local"


class PublicationRunner:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def run(self, label, command, **kwargs):
        self.calls.append((label, command))
        if label == self.fail:
            raise ReleaseError("simulated registry failure")
        if label.startswith("remote-"):
            arch = label.removeprefix("remote-")
            return json.dumps(
                {"manifests": [descriptor(arch, DIGESTS[arch]), attestation_row(arch)]}
            )
        if label == "published-digest":
            return "sha256:" + "f" * 64
        if label == "published-manifest":
            return json.dumps(
                {
                    "manifests": [descriptor(arch, digest) for arch, digest in DIGESTS.items()]
                    + [attestation_row(arch) for arch in DIGESTS]
                }
            )
        return ""


DIGESTS = {"amd64": "sha256:" + "1" * 64, "arm64": "sha256:" + "2" * 64}
ATTESTATIONS = {"amd64": "sha256:" + "a" * 64, "arm64": "sha256:" + "b" * 64}


def attestation_row(arch):
    return {
        "digest": ATTESTATIONS[arch],
        "platform": {"os": "unknown", "architecture": "unknown"},
        "annotations": {
            "vnd.docker.reference.type": "attestation-manifest",
            "vnd.docker.reference.digest": DIGESTS[arch],
        },
    }


def publication(tmp_path, fail=None):
    task = release.Release(release.options([]), tmp_path, publish=True)
    task.images = {
        arch: {
            "id": "sha256:" + str(i) * 64,
            "digest": "sha256:" + str(i + 2) * 64,
            "runtimeDigest": digest,
            "attestations": {ATTESTATIONS[arch]: digest},
        }
        for i, (arch, digest) in enumerate(DIGESTS.items(), 1)
    }
    task.runner = PublicationRunner(fail)
    task.source_unchanged = lambda: None
    return task


def test_publication_pushes_tested_ids_then_composes_by_immutable_digest(tmp_path):
    task = publication(tmp_path)
    task.publish_images()
    labels = [label for label, _ in task.runner.calls]
    assert labels.index("push-arm64") < labels.index("manifest")
    manifest = next(command for label, command in task.runner.calls if label == "manifest")
    assert manifest[-2:] == [
        task.args.image + "@" + task.images[arch]["digest"] for arch in release.ARCHES
    ]
    for arch in release.ARCHES:
        command = next(command for label, command in task.runner.calls if label == "tag-" + arch)
        assert command[2] == task.images[arch]["id"]
    assert task.report["publishedDigest"] == "sha256:" + "f" * 64
    assert not any("build" in command or "login" in command for _, command in task.runner.calls)


@pytest.mark.parametrize("failure", ["push-amd64", "remote-amd64", "push-arm64", "remote-arm64"])
def test_partial_publication_never_advances_main_tag_or_retries(tmp_path, failure):
    task = publication(tmp_path, failure)
    with pytest.raises(ReleaseError):
        task.publish_images()
    labels = [label for label, _ in task.runner.calls]
    assert labels.count(failure) == 1
    assert "manifest" not in labels
    assert len(task.report["pushedTags"]) <= 2
    assert task.report["attemptedTags"]


def test_dirty_publish_checkout_is_refused_before_docker(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "source_state", lambda root: {"dirty": True})
    task = release.Release(release.options([]), tmp_path, publish=True)
    task.command = lambda *a, **kw: pytest.fail("Docker called for dirty publish")
    with pytest.raises(ReleaseError, match="clean committed"):
        task.preflight()


def test_source_snapshot_detects_edits_even_if_git_dirty_status_stays_the_same(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git(
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=fixture@example.test",
        "commit",
        "--allow-empty",
        "-m",
        "fixture",
    )
    path = tmp_path / "source.py"
    path.write_text("first untracked version")
    first = release.source_state(tmp_path)
    path.write_text("second untracked version")
    second = release.source_state(tmp_path)
    assert first["dirty"] is second["dirty"] is True
    assert first["revision"] == second["revision"]
    assert first["fingerprint"] != second["fingerprint"]


def test_controller_logs_never_capture_container_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_TEST_NETWORK", raising=False)
    secret = "fixture-container-environment-token-must-not-be-logged"
    networks = {"test-dev": {"Aliases": ["dev"]}}
    monkeypatch.setattr(
        release, "source_state", lambda root: {"revision": "a" * 40, "dirty": False}
    )

    def run(command, **kwargs):
        if command[:2] == ["docker", "info"]:
            value = [["driver-type", "io.containerd.snapshotter.v1"]]
        elif command[:3] == ["docker", "buildx", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "linux/amd64,linux/arm64", "")
        elif command[:2] == ["docker", "inspect"]:
            value = (
                networks
                if "--format" in command
                else [
                    {
                        "Config": {"Env": ["TOKEN=" + secret]},
                        "NetworkSettings": {"Networks": networks},
                    }
                ]
            )
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, json.dumps(value), "")

    monkeypatch.setattr(release.subprocess, "run", run)
    task = release.Release(release.options([]), tmp_path)
    task.preflight()
    assert all(secret not in path.read_text() for path in tmp_path.glob("*.log"))


@pytest.mark.parametrize("defect", ["missing", "replacement", "wrong_reference"])
def test_final_manifest_requires_all_tested_attestations(defect):
    runtime = "sha256:" + "1" * 64
    attestation = "sha256:" + "2" * 64
    rows = [{"digest": runtime, "platform": {"os": "linux", "architecture": "amd64"}}]
    if defect != "missing":
        rows.append(
            {
                "digest": "sha256:" + "3" * 64 if defect == "replacement" else attestation,
                "annotations": {
                    "vnd.docker.reference.type": "attestation-manifest",
                    "vnd.docker.reference.digest": runtime
                    if defect != "wrong_reference"
                    else "sha256:" + "4" * 64,
                },
            }
        )
    with pytest.raises(images.ReleaseError):
        images.validate_manifest({"manifests": rows}, {"amd64": runtime}, {attestation: runtime})


def test_command_timeout_keeps_both_diagnostic_streams(tmp_path, monkeypatch):
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            ["docker"], 1, output=b"partial-stdout", stderr=b"partial-stderr"
        )

    monkeypatch.setattr(images.subprocess, "run", run)
    with pytest.raises(images.ReleaseError):
        images.Runner(Path.cwd(), tmp_path).run("build", ["docker"], timeout=1)
    content = next(tmp_path.glob("*.log")).read_text()
    assert "partial-stdout" in content and "partial-stderr" in content


def test_image_logs_do_not_capture_embedded_environment_or_unneeded_labels(tmp_path, monkeypatch):
    secret = "fixture-image-env-and-extra-label-must-not-be-logged"
    monkeypatch.setattr(
        release, "archive_evidence", lambda *args: {"runtimeDigest": "sha256:" + "1" * 64}
    )

    def run(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            arch = "arm64" if command[-1].endswith("arm64") else "amd64"
            # The selected template is before the image reference in the fixed command.
            value = {
                "Id": "sha256:" + "2" * 64,
                "Descriptor": {"digest": "sha256:" + "3" * 64},
                "Architecture": arch,
                "Config": {
                    "Labels": {
                        "org.opencontainers.image.version": PROJECT_VERSION,
                        "org.opencontainers.image.revision": "a" * 40,
                    }
                },
            }
            if "--format" not in command:
                value["Config"]["Env"] = ["TOKEN=" + secret]
                value["Config"]["Labels"]["private-label"] = secret
            return subprocess.CompletedProcess(command, 0, json.dumps([value]), "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release.subprocess, "run", run)
    task = release.Release(release.options([]), tmp_path)
    task.original = {"revision": "a" * 40, "dirty": False}
    task.build_images()
    assert all(secret not in path.read_text() for path in tmp_path.glob("*.log"))
