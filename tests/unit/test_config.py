"""Settings must be isolated, transport-aware and safe to report."""

from pathlib import Path

import pytest

from mealie_mcp_server.config import ConfigurationError, load_settings

BASE = {"MEALIE_BASE_URL": "http://mealie:9000/subpath///", "MEALIE_API_KEY": "fixture-mealie-key"}
HTTP_TOKEN = "reference-http-token-" + "x" * 32


def test_missing_mealie_url_fails_before_startup() -> None:
    with pytest.raises(ConfigurationError, match="MEALIE_BASE_URL"):
        load_settings({})


def test_private_base_url_subpath_and_unrelated_environment() -> None:
    settings = load_settings(
        {**BASE, "PATH": "/unrelated", "UNRELATED_SECRET": "not-configuration"}
    )
    assert settings.mealie_base_url == "http://mealie:9000/subpath"
    assert settings.mealie_api_key.get_secret_value() == "fixture-mealie-key"
    assert settings.transport == "stdio"
    assert settings.tz == "UTC"
    assert "fixture-mealie-key" not in repr(settings)


def test_mealie_key_is_required_even_for_stdio() -> None:
    with pytest.raises(ConfigurationError, match="MEALIE_API_KEY"):
        load_settings({"MEALIE_BASE_URL": "http://mealie:9000"})


def test_stdio_does_not_read_or_require_http_token_file(tmp_path: Path) -> None:
    settings = load_settings(
        {
            **BASE,
            "MCP_AUTH_TOKEN": "short-inactive",
            "MCP_AUTH_TOKEN_FILE": str(tmp_path / "missing"),
        }
    )
    assert settings.mcp_auth_token is None


def test_http_needs_its_own_token() -> None:
    with pytest.raises(ConfigurationError, match="MCP_AUTH_TOKEN"):
        load_settings({**BASE, "MCP_TRANSPORT": "http"})


def test_http_token_must_not_reuse_mealie_credential() -> None:
    with pytest.raises(ConfigurationError, match="MCP_AUTH_TOKEN"):
        load_settings(
            {
                **BASE,
                "MEALIE_API_KEY": HTTP_TOKEN,
                "MCP_TRANSPORT": "http",
                "MCP_AUTH_TOKEN": HTTP_TOKEN,
            }
        )


def test_cli_overrides_transport_and_port() -> None:
    settings = load_settings(
        {**BASE, "MCP_TRANSPORT": "stdio", "MCP_PORT": "8000", "MCP_AUTH_TOKEN": HTTP_TOKEN},
        {"transport": "http", "port": 8123},
    )
    assert settings.transport == "http"
    assert settings.port == 8123
    assert settings.mcp_auth_token.get_secret_value() == HTTP_TOKEN


def test_secret_files_strip_trailing_newline(tmp_path: Path) -> None:
    key = tmp_path / "key"
    token = tmp_path / "token"
    key.write_text("fixture-mealie-key\n")
    token.write_text(HTTP_TOKEN + "\n")
    settings = load_settings(
        {
            "MEALIE_BASE_URL": "http://mealie:9000",
            "MEALIE_API_KEY_FILE": str(key),
            "MCP_TRANSPORT": "http",
            "MCP_AUTH_TOKEN_FILE": str(token),
        }
    )
    assert settings.mealie_api_key.get_secret_value() == "fixture-mealie-key"
    assert settings.mcp_auth_token.get_secret_value() == HTTP_TOKEN


def test_key_and_file_conflict_is_not_resolved_silently(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="MEALIE_API_KEY"):
        load_settings({**BASE, "MEALIE_API_KEY_FILE": str(tmp_path / "missing")})


def test_missing_secret_file_has_safe_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings(
            {
                "MEALIE_BASE_URL": "http://mealie:9000",
                "MEALIE_API_KEY_FILE": str(tmp_path / "private-filename"),
            }
        )
    assert "MEALIE_API_KEY_FILE" in str(caught.value)
    assert "private-filename" not in str(caught.value)


@pytest.mark.parametrize("port", ["0", "-1", "65536", "1.5", "not-a-number"])
def test_invalid_ports_rejected_without_leaking_key(port: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings({**BASE, "MCP_PORT": port})
    assert "fixture-mealie-key" not in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://mealie.test",
        "https://user:private-password@mealie.test",
        "http://mealie.test?key=private-password",
        "not a URL",
    ],
)
def test_invalid_base_url_errors_do_not_contain_credentials(url: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        load_settings({**BASE, "MEALIE_BASE_URL": url})
    assert "MEALIE_BASE_URL" in str(caught.value)
    assert "private-password" not in str(caught.value)


def test_http_public_host_is_explicit_and_origins_parsed() -> None:
    settings = load_settings(
        {
            **BASE,
            "MCP_TRANSPORT": "http",
            "MCP_AUTH_TOKEN": HTTP_TOKEN,
            "MCP_PUBLIC_URL": "https://mcp.example.test/mcp",
            "MCP_ALLOWED_ORIGINS": "https://client.example.test, https://another.example.test",
        }
    )
    assert "mcp.example.test" in settings.allowed_hosts
    assert "127.0.0.1" in settings.allowed_hosts
    assert settings.allowed_origins == (
        "https://client.example.test",
        "https://another.example.test",
    )
    assert settings.max_request_bytes == 32 * 1024 * 1024


@pytest.mark.parametrize("token", ["short", "x" * 32 + "\n", "x" * 32 + " token"])
def test_http_token_rejects_weak_or_header_unsafe_values(token: str) -> None:
    with pytest.raises(ConfigurationError, match="MCP_AUTH_TOKEN"):
        load_settings({**BASE, "MCP_TRANSPORT": "http", "MCP_AUTH_TOKEN": token})


def test_timezone_must_exist() -> None:
    with pytest.raises(ConfigurationError, match="TZ"):
        load_settings({**BASE, "TZ": "Mars/Unknown"})
