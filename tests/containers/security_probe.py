"""Executed inside the installed runtime image, never imported by the test runner."""

import importlib.metadata as metadata
import json
import os
import shutil
import ssl
from importlib.resources import files
from pathlib import Path
from zoneinfo import ZoneInfo

import icu

assert os.getuid() != 0
for tool in ("node", "npm", "yarn", "uv", "pip", "pip3", "gcc", "g++", "git", "sudo"):
    assert shutil.which(tool) is None, tool
for package in ("pytest", "ruff", "mypy"):
    try:
        metadata.version(package)
    except metadata.PackageNotFoundError:
        pass
    else:
        raise AssertionError(package)
try:
    Path("/opt/write-must-fail").write_text("must fail")
except OSError:
    pass
else:
    raise AssertionError("Root filesystem is writable")
Path("/tmp/runtime-check").write_text("ok")
assert files("mealie_mcp_server").joinpath("resources/server-instructions.md").read_text()
assert files("mealie_mcp_server").joinpath("resources/weekly-meal-plan.md").read_text()
assert ssl.get_default_verify_paths().cafile
assert ZoneInfo("Europe/Madrid")
assert not Path("/usr/local/lib/python3.14/ensurepip").exists()
print(
    json.dumps(
        {
            "version": metadata.version("mealie-mcp-server"),
            "uid": os.getuid(),
            "icu": icu.ICU_VERSION,
        }
    )
)
