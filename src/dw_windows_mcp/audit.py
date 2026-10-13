"""Audit logging: every tool invocation is recorded, regardless of outcome."""
from __future__ import annotations

import json

from .db import AuditLog, get_session


def log(
    username: str | None,
    tool_name: str,
    arguments: dict,
    outcome: str,
    detail: str = "",
    client_addr: str | None = None,
) -> None:
    safe_args = {k: v for k, v in arguments.items() if k != "confirm_token"}
    with get_session() as s:
        s.add(
            AuditLog(
                username=username,
                tool_name=tool_name,
                arguments=json.dumps(safe_args, default=str)[:4000],
                outcome=outcome,
                detail=detail[:4000],
                client_addr=client_addr,
            )
        )
        s.commit()
