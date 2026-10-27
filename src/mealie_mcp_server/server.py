"""Build MCP instances without network or secret-reading import side effects."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP

from mealie_mcp_server import version
from mealie_mcp_server.config import Settings
from mealie_mcp_server.mealie.client import MealieClient
from mealie_mcp_server.tools.registry import register_all_tools


@dataclass(frozen=True)
class AppState:
    settings: Settings
    client: MealieClient


def create_server(
    settings: Settings,
    *,
    client_factory: Callable[[], AbstractAsyncContextManager[MealieClient]] | None = None,
) -> FastMCP:
    factory = client_factory or (lambda: MealieClient(settings))

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        async with factory() as client:
            yield {"state": AppState(settings, client)}

    server = FastMCP("mealie-mcp-server", version=version(), lifespan=lifespan)
    register_all_tools(server)
    return server
