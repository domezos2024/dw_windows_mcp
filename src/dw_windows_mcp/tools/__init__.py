"""Tool registry: wraps every registered tool with RBAC, confirm-token and audit
logging, so individual tool modules only implement the actual Windows action."""
from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..audit import log as audit_log
from ..auth.rbac import PermissionError_, ToolSpec, require_permission
from ..confirm import ConfirmationRequired, require_confirmation
from ..db import User

_REGISTRY: dict[str, RegisteredTool] = {}


@dataclass
class RegisteredTool:
    spec: ToolSpec
    func: Callable[..., Any]
    description: str
    confirm_description: str | None = None


def tool(
    name: str,
    category: str,
    description: str,
    destructive: bool = False,
    confirm_description: str | None = None,
):
    """Decorator for a tool implementation. The wrapped function signature is
    `func(user: User, **arguments) -> Any`."""

    def decorator(func: Callable[..., Any]):
        spec = ToolSpec(name=name, category=category, destructive=destructive)
        _REGISTRY[name] = RegisteredTool(
            spec=spec, func=func, description=description, confirm_description=confirm_description
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def all_tools() -> dict[str, RegisteredTool]:
    return dict(_REGISTRY)


def get_tool(name: str) -> RegisteredTool | None:
    return _REGISTRY.get(name)


class ToolExecutionError(Exception):
    pass


def invoke_tool(user: User, tool_name: str, arguments: dict, client_addr: str | None = None) -> Any:
    """Single entry point for executing a tool call: permission check, destructive
    confirm-token gate, execution, audit logging on every path."""
    reg = get_tool(tool_name)
    if reg is None:
        audit_log(user.username, tool_name, arguments, "error", "Unbekanntes Tool", client_addr)
        raise ToolExecutionError(f"Unbekanntes Tool: {tool_name}")

    try:
        require_permission(user.role, reg.spec)
    except PermissionError_ as e:
        audit_log(user.username, tool_name, arguments, "denied", str(e), client_addr)
        raise

    if reg.spec.destructive:
        try:
            require_confirmation(
                user,
                tool_name,
                arguments,
                reg.confirm_description or f"Destruktive Aktion '{tool_name}' wird ausgeführt.",
            )
        except ConfirmationRequired as cr:
            audit_log(
                user.username,
                tool_name,
                arguments,
                "confirm_required",
                f"token={cr.token}",
                client_addr,
            )
            raise

    try:
        sig = inspect.signature(reg.func)
        accepted = {k: v for k, v in arguments.items() if k in sig.parameters}
        result = reg.func(user, **accepted)
    except ConfirmationRequired as cr:
        # Tools that gate confirmation conditionally (e.g. only when dry_run=False)
        # call require_confirmation() themselves instead of via spec.destructive.
        audit_log(user.username, tool_name, arguments, "confirm_required", f"token={cr.token}", client_addr)
        raise
    except Exception as e:
        audit_log(user.username, tool_name, arguments, "error", str(e), client_addr)
        raise

    audit_log(user.username, tool_name, arguments, "success", "", client_addr)
    return result


# Import tool modules so their @tool decorators register on package import.
from . import (
    audio,  # noqa: F401
    clipboard,  # noqa: F401
    documents,  # noqa: F401
    filesystem,  # noqa: F401
    gui,  # noqa: F401
    install,  # noqa: F401
    memory,  # noqa: F401
    network,  # noqa: F401
    power,  # noqa: F401
    process,  # noqa: F401
    registry,  # noqa: F401
    services,  # noqa: F401
    system,  # noqa: F401
)
