"""Wire result and lifespan adapters shared by explicit tool handlers."""

import json
from typing import TYPE_CHECKING

from fastmcp import Context
from mcp.types import CallToolResult, TextContent
from pydantic import JsonValue

if TYPE_CHECKING:
    from mealie_mcp_server.server import AppState


def get_state(ctx: Context) -> AppState:
    from mealie_mcp_server.server import AppState

    state = ctx.lifespan_context.get("state")
    if not isinstance(state, AppState):
        raise RuntimeError("Mealie MCP lifespan has not initialized.")
    return state


def success_result(data: JsonValue) -> CallToolResult:
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return CallToolResult(content=[TextContent(type="text", text=text)])


def error_result(error: Exception) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=str(error))], is_error=True)
