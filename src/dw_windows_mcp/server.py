"""stdio MCP server entry point — used by local AI clients (Claude Desktop,
Claude Code, etc.) that spawn this as a child process. There is exactly one
local user per process, resolved once at startup via DW_MCP_LOCAL_USER (or the
first admin found if unset)."""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from .db import Role, User, get_session, init_db
from .mcp_core import current_client_addr, current_user, server


def _resolve_local_user() -> User:
    username = os.environ.get("DW_MCP_LOCAL_USER")
    with get_session() as s:
        if username:
            user = s.scalar(select(User).where(User.username == username))
            if not user:
                raise RuntimeError(
                    f"Lokaler Benutzer '{username}' (DW_MCP_LOCAL_USER) nicht gefunden. "
                    "Lege ihn mit 'dw-windows-mcp user add' an."
                )
            return user
        user = s.scalar(select(User).where(User.role == Role.ADMIN))
        if not user:
            raise RuntimeError(
                "Kein Benutzer vorhanden. Führe 'dw-windows-mcp init' aus, um einen Admin anzulegen."
            )
        return user


async def run_stdio() -> None:
    import mcp.server.stdio

    init_db()
    user = _resolve_local_user()
    current_user.set(user)
    current_client_addr.set("stdio-local")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
