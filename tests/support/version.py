"""Expected release identity comes from project metadata, not captured upstream versions."""

import tomllib
from pathlib import Path

PROJECT_VERSION = tomllib.loads(
    (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text()
)["project"]["version"]
