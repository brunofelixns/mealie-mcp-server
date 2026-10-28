import os
import subprocess
import sys

import pytest

from mealie_mcp_server import version


def clean_env():
    return {
        key: value for key, value in os.environ.items() if not key.startswith(("MEALIE_", "MCP_"))
    }


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_do_not_load_secret_files(option):
    environment = {
        **clean_env(),
        "MEALIE_API_KEY_FILE": "/missing/must-not-be-read",
        "MCP_TRANSPORT": "http",
        "MCP_AUTH_TOKEN_FILE": "/missing/http-secret",
    }
    result = subprocess.run(
        [sys.executable, "-m", "mealie_mcp_server", option],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "mealie-mcp-server" in result.stdout
    assert "must-not-be-read" not in result.stderr
    if option == "--version":
        assert result.stdout.strip() == "mealie-mcp-server " + version()
    else:
        assert "--transport" in result.stdout


def test_console_entrypoint_has_same_version():
    result = subprocess.run(
        ["mealie-mcp-server", "--version"],
        env=clean_env(),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "mealie-mcp-server " + version()


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {
            "MEALIE_BASE_URL": "https://user:secret-must-not-print@mealie.test",
            "MEALIE_API_KEY": "key-must-not-print",
        },
    ],
)
def test_invalid_configuration_exits_nonzero_with_safe_stderr(environment):
    result = subprocess.run(
        [sys.executable, "-m", "mealie_mcp_server"],
        env={**clean_env(), **environment},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert not result.stdout and "Configuration error" in result.stderr
    assert (
        "key-must-not-print" not in result.stderr and "secret-must-not-print" not in result.stderr
    )
    assert "Traceback" not in result.stderr
