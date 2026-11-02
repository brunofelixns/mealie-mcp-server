import re
import shutil

import pytest
from fastmcp import Client, FastMCP
from fastmcp.skills import SkillsClientExtension

from mealie_mcp_server import skills
from tests.support.skills import ROOT, SKILL_URI


def test_skill_links_resolve_for_both_mcp_and_manual_readers():
    root = ROOT / "skills/mealie"
    for document in root.rglob("*.md"):
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text()):
            if ":" in target or target.startswith("#"):
                continue
            assert (root / target).is_file(), (document, "MCP skill-root reference", target)
            assert (document.parent / target).is_file(), (document, "Markdown reference", target)


async def test_packaged_skills_are_independent_of_the_working_directory(tmp_path, monkeypatch):
    package = tmp_path / "package"
    shutil.copytree(ROOT / "skills", package / "resources/skills")
    monkeypatch.setattr(skills, "files", lambda _: package)
    monkeypatch.chdir(tmp_path)
    server = FastMCP("packaged-skill-test")
    skills.register_skills(server)
    async with Client(server, extensions=[SkillsClientExtension()]) as client:
        entry = await client.get_skill(SKILL_URI)
        assert entry.frontmatter.name == "mealie"
        assert (await client.read_resource(entry.uri))[0].text.encode("utf-8") == (
            ROOT / "skills/mealie/SKILL.md"
        ).read_bytes()


def test_missing_bundled_skill_fails_before_serving(tmp_path, monkeypatch):
    monkeypatch.setattr(skills, "files", lambda _: tmp_path)
    monkeypatch.setattr(skills, "__file__", str(tmp_path / "src/package/skills.py"))
    with pytest.raises(FileNotFoundError, match="bundled Mealie skill is missing"):
        skills.register_skills(FastMCP("missing-skill-test"))
