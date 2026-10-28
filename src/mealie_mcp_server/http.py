"""One Streamable HTTP endpoint, bounded input, and a single owned lifespan."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.auth.middleware import RequireAuthMiddleware
from fastmcp.server.http import StreamableHTTPASGIApp
from mcp.server.transport_security import RequestBodyLimitMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route

from mealie_mcp_server.config import Settings
from mealie_mcp_server.health import health, readiness


def _configure_sdk_limit(app: Starlette, limit: int) -> None:
    """Bridge the pinned FastMCP 4.1.4 / SDK 2.3.0 configuration gap.

    FastMCP does not expose the SDK's 4 MiB default in http_app yet. Configure
    the per-app manager's public limiter after startup, before readiness. Fail
    closed if an upgrade changes this wiring; never patch module globals.
    """
    route = next(route for route in app.routes if isinstance(route, Route) and route.path == "/mcp")
    protected = route.endpoint
    if not isinstance(protected, RequireAuthMiddleware):
        raise RuntimeError("Unsupported authenticated MCP route layout.")
    transport = protected.app
    if not isinstance(transport, StreamableHTTPASGIApp) or transport.session_manager is None:
        raise RuntimeError("Unsupported MCP session manager layout.")
    manager = transport.session_manager
    if not isinstance(manager.asgi_app, RequestBodyLimitMiddleware):
        raise RuntimeError("Unsupported MCP request limiter layout.")
    manager.max_request_body_size = limit
    manager.asgi_app.max_body_size = limit


def create_http_app(server: FastMCP, settings: Settings) -> Starlette:
    if settings.transport != "http" or settings.mcp_auth_token is None or server.auth is None:
        raise ValueError("HTTP requires an authenticated HTTP server configuration.")
    mcp_app = server.http_app(
        path="/mcp",
        transport="http",
        stateless_http=False,
        json_response=False,
        host_origin_protection=True,
        allowed_hosts=list(settings.allowed_hosts),
        allowed_origins=list(settings.allowed_origins),
    )

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with mcp_app.router.lifespan_context(mcp_app):
            _configure_sdk_limit(mcp_app, settings.max_request_bytes)
            app.state.ready = True
            try:
                yield
            finally:
                app.state.ready = False

    return Starlette(
        routes=[Route("/healthz", health), Route("/readyz", readiness), Mount("/", app=mcp_app)],
        lifespan=lifespan,
    )
