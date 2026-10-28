import os
import subprocess
import uuid

import pytest


def docker(*arguments, check=True, input=None):
    return subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, check=check, timeout=75, input=input
    )


@pytest.fixture
def runtime_image():
    image = os.environ.get("MCP_TEST_IMAGE", "mealie-mcp-server:local")
    result = docker(
        "image",
        "inspect",
        "--platform",
        "linux/" + os.environ.get("MCP_TEST_ARCH", "amd64"),
        image,
        check=False,
    )
    assert result.returncode == 0, (
        "Build the production runtime image before container tests: " + result.stderr
    )
    return image


def run_arguments(image, *extra):
    return [
        "run",
        "--rm",
        "--init",
        "--platform",
        "linux/" + os.environ.get("MCP_TEST_ARCH", "amd64"),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--network",
        os.environ.get("MCP_TEST_NETWORK", "mealie-mcp-development_default"),
        *extra,
        image,
    ]


def unique_name():
    return "mealie-mcp-test-" + uuid.uuid4().hex[:12]
