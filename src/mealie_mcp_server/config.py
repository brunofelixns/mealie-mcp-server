"""Explicit, isolated settings loading with transport-specific secret validation."""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

type Transport = Literal["stdio", "http"]


class ConfigurationError(ValueError):
    """A safe error containing configuration field names, never secret values."""


def _url(value: str, name: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be an http(s) URL without credentials, query or fragment.")
    return value.rstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, extra="forbid")

    mealie_base_url: str
    mealie_api_key: SecretStr
    transport: Transport = "stdio"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    mcp_auth_token: SecretStr | None = None
    public_url: str | None = None
    require_https: bool = False
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "[::1]")
    allowed_origins: tuple[str, ...] = ()
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    tz: str = "UTC"
    max_request_bytes: int = Field(default=32 * 1024 * 1024, ge=1)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # load_settings supplies the chosen mapping; never merge another process environment.
        return (init_settings,)

    @field_validator("mealie_base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _url(value, "MEALIE_BASE_URL")

    @field_validator("public_url")
    @classmethod
    def validate_public_url(cls, value: str | None) -> str | None:
        return _url(value, "MCP_PUBLIC_URL") if value is not None else None

    @model_validator(mode="after")
    def validate_active_transport(self) -> Self:
        key = self.mealie_api_key.get_secret_value()
        if not key or any(character in key for character in "\r\n"):
            raise ValueError("MEALIE_API_KEY must be a non-empty header-safe value.")
        if self.transport == "http":
            if self.require_https and (
                not self.public_url or urlsplit(self.public_url).scheme != "https"
            ):
                raise ValueError("MCP_PUBLIC_URL must use HTTPS when MCP_REQUIRE_HTTPS is enabled.")
            token = self.mcp_auth_token.get_secret_value() if self.mcp_auth_token else ""
            if len(token) < 32 or any(
                ord(character) < 33 or ord(character) > 126 for character in token
            ):
                raise ValueError(
                    "MCP_AUTH_TOKEN must contain at least 32 visible ASCII characters."
                )
            if token == key:
                raise ValueError("MCP_AUTH_TOKEN must differ from MEALIE_API_KEY.")
        try:
            ZoneInfo(self.tz)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("TZ must name an installed time zone.") from error
        return self


ENV_FIELDS = {
    "MEALIE_BASE_URL": "mealie_base_url",
    "MCP_TRANSPORT": "transport",
    "MCP_HOST": "host",
    "MCP_PORT": "port",
    "MCP_PUBLIC_URL": "public_url",
    "MCP_REQUIRE_HTTPS": "require_https",
    "MEALIE_MCP_DEBUG": "debug",
    "LOG_LEVEL": "log_level",
    "TZ": "tz",
}


def _secret(environ: Mapping[str, str], name: str) -> str:
    file_name = name + "_FILE"
    if name in environ and file_name in environ:
        raise ConfigurationError(f"Set only one of {name} and {file_name}.")
    if file_name in environ:
        try:
            return Path(environ[file_name]).read_text(encoding="utf-8").strip()
        except OSError, UnicodeError:
            raise ConfigurationError(f"Cannot read {file_name}.") from None
    if not environ.get(name):
        raise ConfigurationError(f"{name} is required.")
    return environ[name]


def load_settings(
    environ: Mapping[str, str], overrides: Mapping[str, object] | None = None
) -> Settings:
    """Load only the supplied mapping and the secrets required by its active transport."""
    values: dict[str, object] = {
        field: environ[name] for name, field in ENV_FIELDS.items() if name in environ
    }
    values.update(overrides or {})
    if not values.get("mealie_base_url"):
        raise ConfigurationError("MEALIE_BASE_URL is required.")
    values["mealie_api_key"] = _secret(environ, "MEALIE_API_KEY")
    transport = values.get("transport", "stdio")
    if transport == "http":
        values["mcp_auth_token"] = _secret(environ, "MCP_AUTH_TOKEN")
    for env_name, field in [
        ("MCP_ALLOWED_HOSTS", "allowed_hosts"),
        ("MCP_ALLOWED_ORIGINS", "allowed_origins"),
    ]:
        if env_name in environ and field not in (overrides or {}):
            values[field] = tuple(
                item.strip() for item in environ[env_name].split(",") if item.strip()
            )
    if values.get("public_url"):
        try:
            public = _url(str(values["public_url"]), "MCP_PUBLIC_URL")
            hostname = urlsplit(public).hostname
            if hostname:
                normalized = f"[{hostname}]" if ":" in hostname else hostname
                hosts = values.get("allowed_hosts", ("localhost", "127.0.0.1", "[::1]"))
                if not isinstance(hosts, (list, tuple)):
                    raise ValueError("MCP_ALLOWED_HOSTS must be a list.")
                values["allowed_hosts"] = tuple(dict.fromkeys((*hosts, normalized)))
        except ValueError as error:
            raise ConfigurationError(str(error)) from None
    try:
        return Settings.model_validate(values)
    except ValidationError as error:
        messages = [
            f"{'.'.join(map(str, item['loc'])) or 'settings'}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        ]
        raise ConfigurationError("Invalid configuration: " + "; ".join(messages)) from None
