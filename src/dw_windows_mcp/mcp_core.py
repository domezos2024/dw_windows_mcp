"""Shared low-level MCP Server instance wiring our tool registry to the MCP
protocol (list_tools / call_tool), used by both the stdio and the HTTP/SSE
transports in server.py and http_app.py."""
from __future__ import annotations

import contextvars
import json
import logging

from mcp import types
from mcp.server.lowlevel import Server

from .auth.rbac import PermissionError_
from .confirm import ConfirmationRequired
from .db import User
from .tools import ToolExecutionError, all_tools, invoke_tool

logger = logging.getLogger("dw_windows_mcp")

server = Server("dw-windows-mcp")

# Bound per-connection (stdio: once at startup; HTTP/SSE: per authenticated
# connection) so call_tool() below knows which user is calling without having
# to thread it through the MCP protocol itself.
current_user: contextvars.ContextVar[User] = contextvars.ContextVar("current_user")
current_client_addr: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_client_addr", default=None
)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    tools = []
    for name, reg in all_tools().items():
        tools.append(
            types.Tool(
                name=name,
                description=f"[{reg.spec.category}]{' (destructive — requires confirm_token)' if reg.spec.destructive else ''} {reg.description}",
                inputSchema={"type": "object", "additionalProperties": True},
            )
        )
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.ContentBlock]:
    try:
        user = current_user.get()
    except LookupError:
        return [types.TextContent(type="text", text=json.dumps({"error": "no_authenticated_user"}, ensure_ascii=False))]
    return await dispatch_call_tool(user, name, arguments, current_client_addr.get())


async def dispatch_call_tool(user: User, name: str, arguments: dict, client_addr: str | None) -> list[types.ContentBlock]:
    try:
        result = invoke_tool(user, name, arguments or {}, client_addr=client_addr)
    except ConfirmationRequired as cr:
        payload = {
            "confirm_required": True,
            "confirm_token": cr.token,
            "description": cr.description,
            "hint": "Rufe das Tool erneut auf mit demselben Argumenten plus confirm_token.",
        }
        return [types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
    except PermissionError_ as e:
        return [types.TextContent(type="text", text=json.dumps({"error": "permission_denied", "detail": str(e)}, ensure_ascii=False))]
    except ToolExecutionError as e:
        return [types.TextContent(type="text", text=json.dumps({"error": "unknown_tool", "detail": str(e)}, ensure_ascii=False))]
    except Exception as e:
        logger.exception("Tool-Ausführung fehlgeschlagen: %s", name)
        return [types.TextContent(type="text", text=json.dumps({"error": "execution_error", "detail": str(e)}, ensure_ascii=False))]

    return [types.TextContent(type="text", text=json.dumps(result, default=str, ensure_ascii=False))]
