"""Assert the wire manifest agrees with the manually installable files."""

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL_URI = "skill://mealie/SKILL.md"
EXTENSION = "io.modelcontextprotocol/skills"


async def assert_skill_bytes(client):
    listing = await client.list_skills_mcp()
    assert listing.result_type == "complete"
    assert listing.ttl_ms >= 0
    assert listing.cache_scope in {"public", "private"}
    assert [entry.uri for entry in listing.skills] == [SKILL_URI]
    entry = listing.skills[0]
    assert (await client.get_skill_mcp(SKILL_URI)).skill == entry
    assert entry.frontmatter.name == "mealie"
    assert isinstance(entry.resources, list)
    expected = {
        "skill://mealie/" + path.relative_to(ROOT / "skills/mealie").as_posix(): path
        for path in (ROOT / "skills/mealie").rglob("*")
        if path.is_file()
    }
    assert len(expected) >= 4
    assert {resource.uri for resource in entry.resources} == set(expected)
    for resource in entry.resources:
        result = await client.read_resource(resource.uri)
        assert len(result) == 1
        raw = result[0].text.encode("utf-8")
        assert raw == expected[resource.uri].read_bytes()
        assert len(raw) == resource.size
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == resource.digest
    text = (await client.read_resource(SKILL_URI))[0].text
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert entry.frontmatter.model_dump() == frontmatter
