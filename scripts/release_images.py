"""Docker release helpers: immutable identities, OCI evidence, safe command logs."""

import hashlib
import json
import re
import shlex
import subprocess
import tarfile
from pathlib import Path

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class ReleaseError(RuntimeError):
    """An actionable release gate failed; raw provider errors stay in its log."""


def require_digest(value):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise ReleaseError("Invalid immutable image digest")
    return value


def runtimes(manifest):
    found = {}
    rows = manifest.get("manifests", [])
    if not rows:
        raise ReleaseError("An OCI image index is required")
    for row in rows:
        if row.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest":
            continue
        platform = row.get("platform", {})
        arch = platform.get("architecture")
        if platform.get("os") != "linux" or arch not in {"amd64", "arm64"} or arch in found:
            raise ReleaseError("Unexpected or duplicated runtime platform")
        found[arch] = require_digest(row.get("digest"))
    return found


def validate_manifest(manifest, expected, expected_attestations=None):
    if runtimes(manifest) != expected:
        raise ReleaseError("Manifest does not reference exactly the tested runtime digests")
    if expected_attestations is not None:
        actual = {}
        for row in manifest["manifests"]:
            annotations = row.get("annotations", {})
            if annotations.get("vnd.docker.reference.type") != "attestation-manifest":
                continue
            digest = require_digest(row.get("digest"))
            reference = require_digest(annotations.get("vnd.docker.reference.digest"))
            if digest in actual or reference not in expected.values():
                raise ReleaseError("Duplicated or incorrectly linked attestation")
            actual[digest] = reference
        if actual != expected_attestations:
            raise ReleaseError("Manifest lost or replaced tested attestations")
    return sorted(expected)


def archive_evidence(path: Path, digest: str, arch: str):
    """Read only referenced JSON blobs, never extract an image tar to the filesystem."""
    with tarfile.open(path) as archive:

        def blob(value):
            require_digest(value)
            try:
                member = archive.getmember("blobs/sha256/" + value.removeprefix("sha256:"))
                if not member.isfile() or member.size > 32 * 1024 * 1024:
                    raise ReleaseError("Invalid or oversized OCI JSON blob")
                with archive.extractfile(member) as stream:
                    data = stream.read()
            except KeyError:
                raise ReleaseError("Missing referenced OCI blob") from None
            if "sha256:" + hashlib.sha256(data).hexdigest() != value:
                raise ReleaseError("OCI blob checksum mismatch")
            return json.loads(data)

        index = blob(digest)
        runtime_map = runtimes(index)
        if set(runtime_map) != {arch}:
            raise ReleaseError("Exported image architecture differs from its release target")
        runtime_digest = runtime_map[arch]
        types = set()
        attestations = {}
        for descriptor in index["manifests"]:
            annotations = descriptor.get("annotations", {})
            if annotations.get("vnd.docker.reference.type") != "attestation-manifest":
                continue
            if annotations.get("vnd.docker.reference.digest") != runtime_digest:
                raise ReleaseError("Attestation refers to another runtime")
            if descriptor["digest"] in attestations:
                raise ReleaseError("Duplicated attestation in OCI archive")
            attestations[descriptor["digest"]] = runtime_digest
            for layer in blob(descriptor["digest"]).get("layers", []):
                statement = blob(layer["digest"])
                kind = statement.get("predicateType", "")
                predicate = statement.get("predicate", {})
                if (
                    kind == "https://spdx.dev/Document"
                    and predicate.get("spdxVersion")
                    and predicate.get("packages")
                ):
                    types.add("sbom")
                if kind.startswith("https://slsa.dev/provenance/") and (
                    predicate.get("buildType")
                    or predicate.get("buildDefinition", {}).get("buildType")
                ):
                    types.add("provenance")
        if types != {"sbom", "provenance"}:
            raise ReleaseError("The exported image must retain both SBOM and provenance payloads")
        return {
            "runtimeDigest": runtime_digest,
            "sbom": True,
            "provenance": True,
            "attestations": attestations,
        }


class Runner:
    def __init__(self, root, artifacts):
        self.root, self.artifacts, self.count = root, artifacts, 0

    def run(self, label, command, *, env=None, timeout=1800):
        self.count += 1
        log = self.artifacts / f"{self.count:02}-{label}.log"
        print(f"[{label}] {log}", flush=True)
        try:
            result = subprocess.run(
                command, cwd=self.root, env=env, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired as error:
            streams = (error.stdout or b"", error.stderr or b"")
            log.write_text(
                "\n".join(
                    value.decode(errors="replace") if isinstance(value, bytes) else value
                    for value in streams
                )
            )
            raise ReleaseError(f"{label} timed out; inspect {log}") from None
        log.write_text("$ " + shlex.join(command) + "\n" + result.stdout + result.stderr)
        if result.returncode:
            raise ReleaseError(f"{label} failed; inspect {log}")
        return result.stdout
