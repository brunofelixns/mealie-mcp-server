import pytest

from mealie_mcp_server.auth import PersonalTokenVerifier
from mealie_mcp_server.config import ConfigurationError, load_settings

TOKEN = "fixture-personal-" + "a" * 40


async def test_personal_verifier_accepts_only_configured_token_without_oauth():
    verifier = PersonalTokenVerifier(TOKEN)
    accepted = await verifier.verify_token(TOKEN)
    assert accepted is not None and accepted.client_id == "personal"
    assert verifier.get_routes(mcp_path="/mcp") == []
    assert TOKEN not in repr(verifier)
    for wrong in ("", "wrong", TOKEN + "x", TOKEN.upper(), "ñ" * 40):
        assert await verifier.verify_token(wrong) is None


@pytest.mark.parametrize("public_url", [None, "http://mcp.example.test"])
def test_production_http_requires_https_public_url(public_url):
    env = {
        "MEALIE_BASE_URL": "http://mealie.test",
        "MEALIE_API_KEY": "fixture",
        "MCP_TRANSPORT": "http",
        "MCP_AUTH_TOKEN": TOKEN,
        "MCP_REQUIRE_HTTPS": "true",
    }
    if public_url:
        env["MCP_PUBLIC_URL"] = public_url
    with pytest.raises(ConfigurationError, match="HTTPS"):
        load_settings(env)
