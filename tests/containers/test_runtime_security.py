import json
import os
from pathlib import Path

from tests.containers.conftest import docker, run_arguments, unique_name
from tests.support.version import PROJECT_VERSION


def test_runtime_nonroot_readonly_without_node_build_tools_or_dev_dependencies(runtime_image):
    name = unique_name()
    docker("volume", "create", name)
    preparer = docker(
        "create",
        "--platform",
        "linux/" + os.environ.get("MCP_TEST_ARCH", "amd64"),
        "--mount",
        f"type=volume,src={name},dst=/probe",
        "--entrypoint",
        "/opt/venv/bin/python",
        runtime_image,
        "--version",
    ).stdout.strip()
    probe = None
    try:
        docker(
            "cp",
            str(Path(__file__).with_name("security_probe.py")),
            preparer + ":/probe/security_probe.py",
        )
        arguments = run_arguments(
            runtime_image,
            "--mount",
            f"type=volume,src={name},dst=/probe,readonly",
            "--entrypoint",
            "/opt/venv/bin/python",
        )
        arguments[0] = "create"
        arguments.remove("--rm")
        probe = docker(*arguments, "/probe/security_probe.py").stdout.strip()
        result = docker("start", "--attach", probe, check=False)
        exit_code = docker("wait", probe).stdout.strip()
        result = docker("logs", probe)
        assert exit_code == "0", result.stderr
        inspected = json.loads(docker("inspect", probe).stdout)[0]
        assert inspected["State"]["ExitCode"] == 0, result.stderr
    finally:
        if probe:
            docker("rm", "--force", probe, check=False)
        docker("rm", "--force", preparer, check=False)
        docker("volume", "rm", name, check=False)
    metadata = json.loads(result.stdout)
    assert metadata["version"] == PROJECT_VERSION and metadata["icu"] == "72.1"


def test_image_has_expected_architecture_labels_no_env_secrets_and_no_stdio_healthcheck(
    runtime_image,
):
    inspected = json.loads(docker("image", "inspect", runtime_image).stdout)[0]
    assert inspected["Os"] == "linux"
    assert inspected["Architecture"] == os.environ.get("MCP_TEST_ARCH", "amd64")
    config = inspected["Config"]
    assert config["User"] == "10001:10001"
    assert config.get("Healthcheck", {}).get("Test", ["NONE"]) == ["NONE"]
    assert config["Labels"]["org.opencontainers.image.licenses"] == "MIT"
    assert config["Labels"]["org.opencontainers.image.version"] == PROJECT_VERSION
    assert not any(
        value.startswith(("MEALIE_API_KEY=", "MCP_AUTH_TOKEN=")) for value in config["Env"]
    )
