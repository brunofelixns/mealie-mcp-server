"""Build, verify and optionally publish both runtime architectures from the Dev Container."""

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path

from release_images import ReleaseError, Runner, archive_evidence, require_digest, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
ARCHES = ("amd64", "arm64")
DESTINATION = "ghcr.io/brunofelixns/mealie-mcp-server"
IMAGE_INSPECT = (
    '[{"Id":{{json .Id}},"Descriptor":{{json .Descriptor}},'
    '"Architecture":{{json .Architecture}},"Config":{"Labels":{'
    '"org.opencontainers.image.version":'
    '{{json (index .Config.Labels "org.opencontainers.image.version")}},'
    '"org.opencontainers.image.revision":'
    '{{json (index .Config.Labels "org.opencontainers.image.revision")}}}}}]'
)


def options(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=DESTINATION, help="GHCR owner/image, without tag")
    parser.add_argument("--version", help="Must equal pyproject.toml; defaults to that version")
    parser.add_argument("--builder", default="default")
    parser.add_argument(
        "--publish", action="store_true", help="Push only after every local gate passes"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the plan without running commands"
    )
    args = parser.parse_args(argv)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    args.version = args.version or version
    if args.version != version or not re.fullmatch(
        r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", args.version
    ):
        raise ReleaseError("Version must equal the package version and be a valid version tag")
    if not re.fullmatch(r"ghcr\.io/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*", args.image):
        raise ReleaseError("Image must be a lowercase ghcr.io/owner/image without tag")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.builder):
        raise ReleaseError("Invalid Buildx builder name")
    return args


def source_state(root):
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout

    revision = git("rev-parse", "HEAD").decode().strip()
    dirty = bool(git("status", "--porcelain", "--untracked-files=all"))
    digest = hashlib.sha256()
    for raw in sorted(
        set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0"))
        - {b""}
    ):
        path = root / os.fsdecode(raw)
        digest.update(raw + b"\0")
        digest.update(
            ("symlink:" + os.readlink(path)).encode() if path.is_symlink() else path.read_bytes()
        )
        digest.update(b"\0")
    return {"revision": revision, "fingerprint": digest.hexdigest(), "dirty": dirty}


class Release:
    def __init__(self, args, artifacts, *, publish=False):
        self.args, self.artifacts, self.publish = args, artifacts, publish
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.runner = Runner(ROOT, artifacts)
        self.report = {
            "status": "running",
            "destination": args.image,
            "version": args.version,
            "publishRequested": publish,
            "images": {},
            "pushedTags": [],
            "attemptedTags": [],
        }
        self.images = {}

    def command(self, label, args, **kwargs):
        return self.runner.run(label, args, **kwargs)

    def record(self):
        (self.artifacts / "summary.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def preflight(self):
        if sys.platform != "linux" or not Path("/.dockerenv").exists():
            raise ReleaseError("Run inside this repository's Linux Dev Container")
        self.original = source_state(ROOT)
        self.report["source"] = self.original
        if self.publish and self.original["dirty"]:
            raise ReleaseError("Publishing requires a clean committed checkout")
        driver = json.loads(
            self.command("docker-store", ["docker", "info", "--format", "{{json .DriverStatus}}"])
        )
        if ["driver-type", "io.containerd.snapshotter.v1"] not in driver:
            raise ReleaseError(
                "Enable the containerd image store in Docker Desktop to retain attestations"
            )
        builder = self.command(
            "builder", ["docker", "buildx", "inspect", self.args.builder, "--bootstrap"]
        )
        if any("linux/" + arch not in builder for arch in ARCHES):
            raise ReleaseError(
                "The Buildx builder must support linux/amd64 and linux/arm64 (native or QEMU)"
            )
        controller = os.environ.get("MCP_E2E_CONTROLLER", os.environ.get("HOSTNAME", ""))
        networks = json.loads(
            self.command(
                "controller",
                ["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", controller],
            )
        )
        candidates = [
            name for name, value in networks.items() if "dev" in (value.get("Aliases") or [])
        ]
        self.network = os.environ.get("MCP_TEST_NETWORK") or (
            candidates[0] if len(candidates) == 1 else None
        )
        if not self.network or self.network not in networks:
            raise ReleaseError(
                "Dev Container network is ambiguous; set MCP_TEST_NETWORK "
                "to its network with alias dev"
            )
        self.report["testNetwork"] = self.network
        self.report["controllerArchitecture"] = platform.machine()

    def checks(self):
        commands = [
            ("sync", ["uv", "sync", "--frozen", "--group", "dev"]),
            (
                "release-gate",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/release_gate.py",
                    "--release-version",
                    self.args.version,
                ],
            ),
            ("ruff", ["uv", "run", "ruff", "check", "."]),
            ("format", ["uv", "run", "ruff", "format", "--check", "."]),
            ("mypy", ["uv", "run", "mypy", "src"]),
            ("docs", ["uv", "run", "python", "scripts/generate_docs.py", "--check"]),
            (
                "pytest",
                [
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "--ignore=tests/containers",
                    "--cov=mealie_mcp_server",
                    "--cov-branch",
                    "--cov-report=json:" + str(self.artifacts / "coverage.json"),
                    "--junitxml=" + str(self.artifacts / "pytest.xml"),
                ],
            ),
            (
                "compatibility",
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/check_compatibility.py",
                    "--require-all",
                    "--coverage-json",
                    str(self.artifacts / "coverage.json"),
                    "--junit-xml",
                    str(self.artifacts / "pytest.xml"),
                ],
            ),
        ]
        for label, command in commands:
            self.command(label, command)

    def build_images(self):
        revision = self.original["revision"] + ("-dirty" if self.original["dirty"] else "")
        run_id = self.artifacts.name
        images = {}
        for arch in ARCHES:
            directory = self.artifacts / arch
            directory.mkdir()
            tag = "mealie-mcp-server:release-" + run_id + "-" + arch
            self.command(
                "build-" + arch,
                [
                    "docker",
                    "buildx",
                    "build",
                    "--builder",
                    self.args.builder,
                    "--platform",
                    "linux/" + arch,
                    "--target",
                    "runtime",
                    "--tag",
                    tag,
                    "--build-arg",
                    "VCS_REF=" + revision,
                    "--sbom=true",
                    "--provenance=mode=max",
                    "--load",
                    "--metadata-file",
                    str(directory / "build.json"),
                    str(ROOT),
                ],
                timeout=7200,
            )
            inspected = json.loads(
                self.command(
                    "image-" + arch, ["docker", "image", "inspect", "--format", IMAGE_INSPECT, tag]
                )
            )[0]
            labels = inspected["Config"].get("Labels", {})
            if (
                inspected["Architecture"] != arch
                or labels.get("org.opencontainers.image.version") != self.args.version
                or labels.get("org.opencontainers.image.revision") != revision
            ):
                raise ReleaseError(
                    "Built image platform/version/revision does not match this release"
                )
            digest = require_digest(inspected.get("Descriptor", {}).get("digest"))
            image_id = require_digest(inspected["Id"])
            archive = directory / "runtime.tar"
            self.command(
                "export-" + arch, ["docker", "image", "save", "--output", str(archive), image_id]
            )
            evidence = archive_evidence(archive, digest, arch)
            images[arch] = {"id": image_id, "digest": digest, "localTag": tag, **evidence}
            self.report["images"][arch] = images[arch]
            self.record()
        return images

    def verify_images(self):
        for arch, image in self.images.items():
            directory = self.artifacts / arch
            env = {
                **os.environ,
                "MCP_TEST_IMAGE": image["id"],
                "MCP_TEST_ARCH": arch,
                "MCP_TEST_NETWORK": self.network,
            }
            self.command(
                "containers-" + arch,
                [
                    "uv",
                    "run",
                    "pytest",
                    "tests/containers",
                    "-q",
                    "--junitxml=" + str(directory / "containers.xml"),
                ],
                env=env,
            )
            summary_path = directory / "e2e-summary.json"
            self.command(
                "e2e-" + arch,
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "tests.e2e.runner",
                    "--image",
                    image["id"],
                    "--no-build",
                    "--summary",
                    str(summary_path),
                ],
            )
            summary = json.loads(summary_path.read_text())
            if (
                summary.get("status") != "passed"
                or summary.get("runtime", {}).get("id") != image["id"]
                or not summary.get("cleanupPassed")
            ):
                raise ReleaseError("E2E summary does not confirm this runtime and cleanup")
            self.command(
                "scan-" + arch,
                [
                    "uv",
                    "run",
                    "python",
                    "scripts/scan_runtime.py",
                    image["id"],
                    "--platform",
                    "linux/" + arch,
                    "--output",
                    str(directory / "security.json"),
                    "--enforce",
                ],
            )

    def source_unchanged(self):
        if source_state(ROOT) != self.original:
            raise ReleaseError("Checkout changed during verification; rebuild before publishing")

    def publish_images(self):
        refs = []
        for arch, image in self.images.items():
            tag = self.args.image + ":" + self.args.version + "-" + arch
            self.command("tag-" + arch, ["docker", "tag", image["id"], tag])
            self.report["attemptedTags"].append(tag)
            self.record()
            self.command("push-" + arch, ["docker", "push", tag])
            self.report["pushedTags"].append(tag)
            self.record()
            ref = self.args.image + "@" + image["digest"]
            remote = json.loads(
                self.command(
                    "remote-" + arch, ["docker", "buildx", "imagetools", "inspect", ref, "--raw"]
                )
            )
            validate_manifest(remote, {arch: image["runtimeDigest"]}, image["attestations"])
            refs.append(ref)
        self.source_unchanged()
        tag = self.args.image + ":" + self.args.version
        self.report["attemptedTags"].append(tag)
        self.record()
        self.command("manifest", ["docker", "buildx", "imagetools", "create", "--tag", tag, *refs])
        self.report["pushedTags"].append(tag)
        self.record()
        digest = require_digest(
            self.command(
                "published-digest",
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    tag,
                    "--format",
                    "{{.Manifest.Digest}}",
                ],
            ).strip()
        )
        remote = json.loads(
            self.command(
                "published-manifest",
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    self.args.image + "@" + digest,
                    "--raw",
                ],
            )
        )
        validate_manifest(
            remote,
            {arch: image["runtimeDigest"] for arch, image in self.images.items()},
            {
                digest: reference
                for image in self.images.values()
                for digest, reference in image["attestations"].items()
            },
        )
        self.report["publishedDigest"] = digest

    def execute(self):
        stage = "preflight"
        try:
            for stage in (
                "preflight",
                "checks",
                "build_images",
                "verify_images",
                "source_unchanged",
            ):
                self.report["phase"] = stage
                self.record()
                result = getattr(self, stage)()
                if stage == "build_images":
                    self.images = result
                    if set(self.images) != set(ARCHES):
                        raise ReleaseError("Both runtime architectures are required")
            if self.publish:
                stage = "publish"
                self.report["phase"] = stage
                self.record()
                self.publish_images()
            self.report["status"] = "published" if self.publish else "verified_local"
            return 0
        except Exception as error:
            self.report.update(status="failed", failedPhase=stage, failureType=type(error).__name__)
            print(
                str(error)
                if isinstance(error, ReleaseError)
                else f"{stage} failed ({type(error).__name__}); inspect logs",
                file=sys.stderr,
            )
            return 1
        finally:
            self.record()
            print("Release summary: " + str(self.artifacts / "summary.json"), flush=True)


def dry_run(args):
    print("DRY RUN: no commands executed; login is managed separately by Docker")
    print(
        "Gates: Linux Dev Container, containerd, Buildx platforms, source snapshot; "
        "uv frozen, release_gate, Ruff, mypy, docs, pytest/coverage/compatibility"
    )
    for arch in ARCHES:
        print(
            shlex.join(
                [
                    "docker",
                    "buildx",
                    "build",
                    "--builder",
                    args.builder,
                    "--platform",
                    "linux/" + arch,
                    "--target",
                    "runtime",
                    "--sbom=true",
                    "--provenance=mode=max",
                    "--load",
                    ".",
                ]
            )
        )
        print(
            f"{arch}: export OCI; verify SBOM/provenance; pytest tests/containers; "
            "E2E stdio/HTTP; scan_runtime --enforce"
        )
    if args.publish:
        for arch in ARCHES:
            print(f"docker tag <tested-{arch}-image-id> {args.image}:{args.version}-{arch}")
            print(f"docker push {args.image}:{args.version}-{arch}")
        print(
            f"docker buildx imagetools create --tag {args.image}:{args.version} "
            "<verified-amd64-digest> <verified-arm64-digest>"
        )
        print("Verify the remote manifest and both tested runtime digests")


def main(argv=None):
    try:
        args = options(argv)
        if args.dry_run:
            dry_run(args)
            return 0
        directory = ROOT / "artifacts/local-release" / uuid.uuid4().hex[:12]
        return Release(args, directory, publish=args.publish).execute()
    except ReleaseError as error:
        print("Local release: " + str(error), file=sys.stderr)
        return 1
    except SystemExit as error:
        return int(error.code or 0)


if __name__ == "__main__":
    sys.exit(main())
