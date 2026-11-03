"""Own and clean exactly one disposable Docker project from the Dev Container."""

import binascii
import json
import os
import re
import secrets
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import httpx2 as httpx

ROOT = Path(__file__).resolve().parents[2]
MEALIE_VERSION = "v3.30.0"
MEALIE_DIGEST = "sha256:90f83da6f3ab0a421efc827118a556168573930105f13fa3321768f42163d784"
PROJECT_PATTERN = r"mealie-mcp-e2e-[0-9a-f]{12}"


def docker(*args, env=None, timeout=180, check=True):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, env=env
    )
    if check and result.returncode:
        raise RuntimeError("Docker command failed: " + " ".join(args[:5]) + "\n" + result.stderr)
    return result


def inspect(kind, name):
    result = docker(kind, "inspect", name)
    return json.loads(result.stdout)[0]


def png(color=b"\xff\0\0"):
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", binascii.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0" + color))
        + chunk(b"IEND", b"")
    )


class Stack:
    def __init__(self, project, image, artifacts):
        if not re.fullmatch(PROJECT_PATTERN, project):
            raise ValueError("Refuse an arbitrary Docker project name")
        self.project, self.image, self.artifacts = project, image, artifacts
        self.network = project + "_default"
        self.controller = os.environ.get("MCP_E2E_CONTROLLER", os.environ.get("HOSTNAME", ""))
        self.connected = False
        self.started = False
        self.secrets = ()
        self.cleanup_errors = []
        self.env = dict(os.environ)
        for key in (
            "COMPOSE_FILE",
            "COMPOSE_PROJECT_NAME",
            "COMPOSE_PROFILES",
            "COMPOSE_ENV_FILES",
            "COMPOSE_COMPATIBILITY",
        ):
            self.env.pop(key, None)
        self.env.update(
            MCP_E2E_IMAGE=image,
            MCP_E2E_HTTP_HOST=project + "-mcp-http-1",
            MCP_E2E_MEALIE_HOST=project + "-mealie-1",
        )
        self.compose = [
            "compose",
            "--env-file",
            "/dev/null",
            "--project-name",
            project,
            "--file",
            str(ROOT / "compose.integration.yaml"),
        ]

    def compose_run(self, *args, log, timeout=240, check=True):
        result = docker(*self.compose, *args, env=self.env, timeout=timeout, check=False)
        (self.artifacts / log).write_text(result.stdout + result.stderr)
        if check and result.returncode:
            raise RuntimeError("Compose failed; inspect " + log)
        return result

    def resolve_image(self, *, build):
        if build:
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
            result = docker(
                "buildx",
                "build",
                "--builder",
                "default",
                "--target",
                "runtime",
                "--tag",
                self.image,
                "--build-arg",
                "VCS_REF=" + revision + ("-dirty" if dirty else ""),
                "--load",
                "--metadata-file",
                str(self.artifacts / "build.json"),
                str(ROOT),
                timeout=2400,
                check=False,
            )
            (self.artifacts / "build.log").write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError("Runtime build failed; inspect build.log")
        image = inspect("image", self.image)
        self.image = image["Id"]
        self.env["MCP_E2E_IMAGE"] = self.image
        return {
            "id": self.image,
            "architecture": image["Architecture"],
            "revision": image["Config"].get("Labels", {}).get("org.opencontainers.image.revision"),
        }

    def start_mealie(self):
        if not Path("/.dockerenv").exists() or not self.controller:
            raise RuntimeError("Run the E2E controller inside the Dev Container")
        controller = inspect("container", self.controller)
        if controller["Config"]["Hostname"] != os.environ.get("HOSTNAME"):
            raise RuntimeError("Controller identity does not match this Dev Container")
        self.controller = controller["Id"]
        if self.network in controller["NetworkSettings"]["Networks"]:
            raise RuntimeError("Unexpected pre-existing E2E network attachment")
        self.started = True
        self.compose_run(
            "up", "--detach", "--wait", "--wait-timeout", "180", "mealie", log="mealie-start.log"
        )
        network = inspect("network", self.network)
        if (
            not network["Internal"]
            or network["Labels"].get("com.docker.compose.project") != self.project
        ):
            raise RuntimeError("Refuse a network not owned by this isolated run")
        docker("network", "connect", self.network, self.controller)
        self.connected = True
        mealie = inspect("container", self.env["MCP_E2E_MEALIE_HOST"])
        self.require_owned(mealie, "mealie")
        if MEALIE_DIGEST not in mealie["Config"]["Image"]:
            raise RuntimeError("Unexpected Mealie image")

    def require_owned(self, container, service):
        labels = container["Config"].get("Labels", {})
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("com.docker.compose.service") != service
            or labels.get("io.mealie-mcp.e2e") != "disposable"
            or set(container["NetworkSettings"]["Networks"]) != {self.network}
            or any(container["NetworkSettings"].get("Ports", {}).values())
        ):
            raise RuntimeError("Refuse an unowned, externally attached or published service")

    def audit_api(self):
        """Check the actual disposable provider before credentials or recipe mutations."""
        url = "http://" + self.env["MCP_E2E_MEALIE_HOST"] + ":9000"
        schema_path = self.artifacts / "openapi.json"
        report_path = self.artifacts / "api-audit.json"
        with httpx.Client(base_url=url, timeout=30, trust_env=False) as http:
            raw = http.get("/openapi.json").raise_for_status().content
        schema_path.write_bytes(raw)
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/audit_mealie_api.py"),
                "--schema",
                str(schema_path),
                "--expected-version",
                MEALIE_VERSION,
                "--output",
                str(report_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # The report contains schema metadata only; never replay provider response bodies.
        if result.returncode or not report_path.is_file():
            raise RuntimeError("API audit failed; inspect api-audit.json and openapi.json")
        report = json.loads(report_path.read_bytes())
        if not report.get("contractChecked") or report.get("contractErrors"):
            raise RuntimeError("API audit failed; inspect api-audit.json and openapi.json")
        return {key: value for key, value in report.items() if key != "operations"}

    def bootstrap(self, directory):
        url = "http://" + self.env["MCP_E2E_MEALIE_HOST"] + ":9000"
        with httpx.Client(base_url=url, timeout=30, trust_env=False) as http:
            version = http.get("/api/app/about").raise_for_status().json()["version"]
            if version != MEALIE_VERSION:
                raise RuntimeError("Unexpected Mealie version")
            login = (
                http.post(
                    "/api/auth/token",
                    data={"username": "changeme@example.com", "password": "MyPassword"},
                )
                .raise_for_status()
                .json()["access_token"]
            )
            response = http.post(
                "/api/users/api-tokens",
                headers={"Authorization": "Bearer " + login},
                json={"name": self.project},
            ).raise_for_status()
            key = response.json()["token"]
        bearer = secrets.token_urlsafe(32)
        self.secrets = (key, bearer)
        for filename, value in (("mealie_api_key", key), ("mcp_auth_token", bearer)):
            path = directory / filename
            path.write_text(value)
            path.chmod(0o444)
        (directory / "image.png").write_bytes(png())
        (directory / "image.png").chmod(0o444)
        recipe_json = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Recipe",
                "name": "MCP Native URL Import",
                "recipeYield": "2 servings",
                "recipeIngredient": ["1 cup water"],
                "recipeInstructions": [{"@type": "HowToStep", "text": "Bring water to a boil."}],
            }
        )
        (directory / "recipe.html").write_text(
            "<!doctype html><html><head><title>Recipe</title>"
            '<script type="application/ld+json">' + recipe_json + "</script></head>"
            "<body><h1>MCP Native URL Import</h1></body></html>"
        )
        (directory / "recipe.html").chmod(0o444)
        (directory / "server.py").write_text((ROOT / "tests/e2e/fixture_server.py").read_text())
        (directory / "server.py").chmod(0o444)
        for name in ("credentials", "fixture-assets"):
            docker(
                "volume",
                "create",
                "--label",
                "com.docker.compose.project=" + self.project,
                "--label",
                "com.docker.compose.volume=" + name,
                self.project + "_" + name,
            )
        preparer = self.project + "-prepare"
        try:
            docker(
                "create",
                "--name",
                preparer,
                "--label",
                "com.docker.compose.project=" + self.project,
                "--mount",
                f"type=volume,src={self.project}_credentials,dst=/run/secrets",
                "--mount",
                f"type=volume,src={self.project}_fixture-assets,dst=/assets",
                "--entrypoint",
                "/opt/venv/bin/python",
                self.image,
                "--version",
            )
            for filename in ("mealie_api_key", "mcp_auth_token"):
                docker("cp", str(directory / filename), preparer + ":/run/secrets/" + filename)
            docker("cp", str(directory / "image.png"), preparer + ":/assets/image.png")
            docker("cp", str(directory / "recipe.html"), preparer + ":/assets/recipe.html")
            docker("cp", str(directory / "server.py"), preparer + ":/assets/server.py")
        finally:
            docker("rm", "--force", preparer, check=False)
        self.compose_run(
            "up",
            "--detach",
            "--wait",
            "--wait-timeout",
            "90",
            "assets",
            "mcp-http",
            log="mcp-start.log",
        )
        runtime = inspect("container", self.env["MCP_E2E_HTTP_HOST"])
        self.require_owned(runtime, "mcp-http")
        if runtime["Image"] != self.image or not runtime["HostConfig"]["ReadonlyRootfs"]:
            raise RuntimeError("The HTTP runtime differs from the installed read-only image")
        self.env.update(
            MCP_E2E_PROJECT=self.project,
            MCP_E2E_NETWORK=self.network,
            MCP_E2E_SECRET_DIR=str(directory),
            MCP_E2E_ARTIFACTS=str(self.artifacts),
            MCP_E2E_ALLOW_WRITES="local-disposable",
        )
        return {
            "mealieVersion": version,
            "apiTokenCreated": True,
            "internalNetwork": True,
            "portsPublished": False,
        }

    def cleanup(self):
        if not self.started:
            return True

        def attempt(name, action):
            try:
                return action()
            except Exception as error:
                self.cleanup_errors.append(name + ":" + type(error).__name__)
                return None

        attempt("logs", lambda: self.compose_run("logs", "--no-color", log="services.log"))
        if self.connected:
            disconnected = attempt(
                "disconnect", lambda: docker("network", "disconnect", self.network, self.controller)
            )
            if disconnected is not None:
                self.connected = False
        attempt(
            "down",
            lambda: self.compose_run(
                "--profile",
                "stdio",
                "down",
                "--remove-orphans",
                "--volumes",
                "--timeout",
                "45",
                log="cleanup.log",
            ),
        )
        remaining = attempt(
            "verify_containers",
            lambda: docker(
                "ps",
                "--all",
                "--quiet",
                "--filter",
                "label=com.docker.compose.project=" + self.project,
            ),
        )
        volumes = attempt(
            "verify_volumes",
            lambda: docker(
                "volume",
                "ls",
                "--quiet",
                "--filter",
                "label=com.docker.compose.project=" + self.project,
            ),
        )
        network = attempt(
            "verify_network", lambda: docker("network", "inspect", self.network, check=False)
        )
        return (
            not self.cleanup_errors
            and remaining is not None
            and not remaining.stdout.strip()
            and volumes is not None
            and not volumes.stdout.strip()
            and network is not None
            and network.returncode != 0
        )
