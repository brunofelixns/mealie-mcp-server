"""Mealie MCP server: deterministic tools backed by the Mealie REST API."""

from importlib.metadata import version as distribution_version


def version() -> str:
    """Return the version of the installed distribution."""
    return distribution_version("mealie-mcp-server")
