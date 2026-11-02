"""Publish the bundled, manually installable skill through SEP-2640."""

from importlib.resources import files
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers.skills import SkillsDirectoryProvider
from fastmcp.skills.extension import SkillsExtension


def register_skills(server: FastMCP) -> None:
    # Wheels contain the build-time copy; editable checkouts use the canonical folder.
    root = Path(str(files("mealie_mcp_server").joinpath("resources/skills")))
    if not root.is_dir():
        root = Path(__file__).resolve().parents[2] / "skills"
    if not (root / "mealie/SKILL.md").is_file():
        raise FileNotFoundError("The bundled Mealie skill is missing.")
    provider = SkillsDirectoryProvider(
        roots=root,
        supporting_files="resources",
        experimental_skills=True,
    )
    server.add_provider(provider)
    server.add_extension(SkillsExtension(providers=[provider]))
