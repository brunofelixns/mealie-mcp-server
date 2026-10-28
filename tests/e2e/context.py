"""Resolve only services owned by this run; keep secrets out of pytest repr."""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx2 as httpx

from tests.e2e.stack import MEALIE_DIGEST, PROJECT_PATTERN, ROOT, Stack, inspect


@dataclass(frozen=True)
class Context:
    project: str
    network: str
    image: str
    artifacts: Path
    mealie_url: str
    http_url: str
    compose: list[str]
    environment: dict[str, str] = field(repr=False)
    api_key: str = field(repr=False)
    bearer: str = field(repr=False)

    @classmethod
    def load(cls):
        if os.environ.get("MCP_E2E_ALLOW_WRITES") != "local-disposable":
            raise RuntimeError("Use the disposable E2E controller")
        project = os.environ["MCP_E2E_PROJECT"]
        if not re.fullmatch(PROJECT_PATTERN, project):
            raise RuntimeError("Unexpected E2E project")
        artifacts = Path(os.environ["MCP_E2E_ARTIFACTS"])
        image = os.environ["MCP_E2E_IMAGE"]
        stack = Stack(project, image, artifacts)
        network = inspect("network", stack.network)
        if (
            not network["Internal"]
            or network["Labels"].get("com.docker.compose.project") != project
        ):
            raise RuntimeError("This is not an isolated E2E network")
        mealie = inspect("container", stack.env["MCP_E2E_MEALIE_HOST"])
        runtime = inspect("container", stack.env["MCP_E2E_HTTP_HOST"])
        stack.require_owned(mealie, "mealie")
        stack.require_owned(runtime, "mcp-http")
        if MEALIE_DIGEST not in mealie["Config"]["Image"] or runtime["Image"] != image:
            raise RuntimeError("Unexpected image identity")
        env = dict(item.split("=", 1) for item in runtime["Config"]["Env"] if "=" in item)
        if env.get("MEALIE_BASE_URL") != "http://mealie:9000":
            raise RuntimeError("Refuse an MCP pointing outside this Mealie stack")
        if not runtime["HostConfig"]["ReadonlyRootfs"] or any(
            mount["Type"] == "bind" for mount in runtime["Mounts"]
        ):
            raise RuntimeError("The MCP runtime must not mount host source or the Docker socket")
        if "MEALIE_API_KEY" in env or "MCP_AUTH_TOKEN" in env:
            raise RuntimeError("E2E runtimes must use credential files")
        directory = Path(os.environ["MCP_E2E_SECRET_DIR"])
        key = (directory / "mealie_api_key").read_text()
        bearer = (directory / "mcp_auth_token").read_text()
        if not key or len(bearer) < 32 or bearer == key:
            raise RuntimeError("Invalid disposable credentials")
        return cls(
            project,
            stack.network,
            image,
            artifacts,
            "http://" + mealie["Name"].lstrip("/") + ":9000",
            "http://" + runtime["Name"].lstrip("/") + ":8000/mcp",
            stack.compose,
            stack.env,
            key,
            bearer,
        )

    def observer(self):
        return httpx.AsyncClient(
            base_url=self.mealie_url,
            headers={"Authorization": "Bearer " + self.api_key},
            timeout=30,
            trust_env=False,
        )

    def assert_stdio(self, name):
        obj = inspect("container", name)
        Stack(self.project, self.image, self.artifacts).require_owned(obj, "mcp-stdio")
        env = dict(item.split("=", 1) for item in obj["Config"]["Env"] if "=" in item)
        if obj["Image"] != self.image or "MCP_AUTH_TOKEN_FILE" in env or "MCP_AUTH_TOKEN" in env:
            raise RuntimeError("stdio must use the same image without HTTP credentials")
        return obj["Id"]


def catalog_names():
    return {
        tool["name"]
        for tool in json.loads(
            (ROOT / "src/mealie_mcp_server/resources/tool-catalog.json").read_text()
        )["tools"]
    }


def baseline_arguments():
    args = {}
    for path in sorted((ROOT / "tests/fixtures/compatibility/cases").glob("*.json")):
        for case in json.loads(path.read_text()):
            args.setdefault(case["tool"], case["arguments"])
    if set(args) != catalog_names():
        raise RuntimeError("Missing baseline arguments for argument-rejection tests")
    return args
