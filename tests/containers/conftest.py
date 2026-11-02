import json
import os
import subprocess
import uuid

import pytest

MEALIE_KEY = "fixture-runtime-mealie-key"
AUTH_TOKEN = "fixture-runtime-personal-" + "b" * 40


def docker(*arguments, check=True, input=None, timeout=75):
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
        input=input,
    )


@pytest.fixture
def runtime_image():
    image = os.environ.get("MCP_TEST_IMAGE", "mealie-mcp-server:local")
    # Each test job builds one native platform. Inspect its actual metadata
    # instead of requiring the Docker API 1.49 multi-platform selector.
    result = docker("image", "inspect", image, check=False)
    assert result.returncode == 0, (
        "Build the production runtime image before container tests: " + result.stderr
    )
    metadata = json.loads(result.stdout)[0]
    expected = "linux/" + os.environ.get("MCP_TEST_ARCH", "amd64")
    assert metadata["Os"] + "/" + metadata["Architecture"] == expected, (
        "Runtime image platform does not match the test target: " + expected
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


@pytest.fixture
def secret_volume(runtime_image, tmp_path):
    name = unique_name()
    docker("volume", "create", name)
    preparer = docker(
        "create",
        "--platform",
        "linux/" + os.environ.get("MCP_TEST_ARCH", "amd64"),
        "--mount",
        f"type=volume,src={name},dst=/run/secrets",
        "--entrypoint",
        "/opt/venv/bin/python",
        runtime_image,
        "--version",
    ).stdout.strip()
    try:
        for filename, value in (("mealie_api_key", MEALIE_KEY), ("mcp_auth_token", AUTH_TOKEN)):
            path = tmp_path / filename
            path.write_text(value + "\n")
            path.chmod(0o444)
            docker("cp", str(path), preparer + ":/run/secrets/" + filename)
        yield name
    finally:
        docker("rm", "--force", preparer, check=False)
        docker("volume", "rm", name, check=False)
