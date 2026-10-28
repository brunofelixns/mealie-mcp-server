"""Process entry point. Human diagnostics use stderr; stdio belongs to JSON-RPC."""

import argparse
import logging
import os
import sys
from collections.abc import Sequence

import anyio

from mealie_mcp_server import version
from mealie_mcp_server.config import ConfigurationError, Settings, load_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mealie-mcp-server", description="Mealie MCP server")
    parser.add_argument("--version", action="store_true", help="show installed package version")
    parser.add_argument(
        "--transport", choices=["stdio"], default=None, help="MCP transport (default: stdio)"
    )
    parser.add_argument("--host", default=None, help="HTTP bind address")
    parser.add_argument("--port", type=int, default=None, help="HTTP port")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default=None
    )
    parser.add_argument(
        "--debug", action="store_true", default=None, help="safe request timings on stderr"
    )
    return parser


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("mealie_mcp_server").setLevel(
        "DEBUG" if settings.debug else settings.log_level
    )
    # Third-party debug logs may contain request bodies or signed URLs.
    for name in ("httpx2", "httpcore2", "mcp"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def _serve_stdio(settings: Settings) -> None:
    from mealie_mcp_server.server import create_server
    from mealie_mcp_server.support.stdio import terminating_stdin

    server = create_server(settings)
    with terminating_stdin():
        library_level = "INFO" if settings.log_level == "DEBUG" else settings.log_level
        await server.run_stdio_async(show_banner=False, log_level=library_level)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(None if argv is None else list(argv))
    if args.version:
        print("mealie-mcp-server " + version())
        return 0
    overrides = {
        key: getattr(args, key)
        for key in ("transport", "host", "port", "log_level", "debug")
        if getattr(args, key) is not None
    }
    try:
        settings = load_settings(os.environ, overrides)
        if settings.transport != "stdio":
            raise ConfigurationError(
                "HTTP transport is not available in this implementation phase."
            )
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    _configure_logging(settings)
    try:
        anyio.run(_serve_stdio, settings)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"Server error: {type(error).__name__}.", file=sys.stderr)
        return 1
