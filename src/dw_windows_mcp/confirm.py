"""Confirmation-token flow for destructive tools.

Any tool marked `destructive=True` in its ToolSpec must be called twice:
  1. First call without `confirm_token` -> raises ConfirmationRequired, which the
     MCP layer turns into a response containing a one-time token plus a human
     description of what would happen.
  2. Second call with the same arguments plus `confirm_token=<token>` -> executes.

Exception: a user with role ADMIN and `skip_confirmation=True` bypasses this
entirely (still fully audit-logged). Non-admin roles can never bypass it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets

from .config import settings
from .db import Role, User

_pending: dict[str, "PendingConfirmation"] = {}


class PendingConfirmation:
    __slots__ = ("token", "tool_name", "args_hash", "username", "expires_at")

    def __init__(self, token: str, tool_name: str, args_hash: str, username: str):
        self.token = token
        self.tool_name = tool_name
        self.args_hash = args_hash
        self.username = username
        self.expires_at = dt.datetime.utcnow() + dt.timedelta(seconds=settings.confirm_token_ttl_seconds)


class ConfirmationRequired(Exception):
    def __init__(self, token: str, tool_name: str, description: str):
        self.token = token
        self.tool_name = tool_name
        self.description = description
        super().__init__(description)


def _hash_args(tool_name: str, arguments: dict) -> str:
    canonical = json.dumps({k: v for k, v in arguments.items() if k != "confirm_token"}, sort_keys=True)
    return hashlib.sha256(f"{tool_name}:{canonical}".encode()).hexdigest()


def user_bypasses_confirmation(user: User) -> bool:
    return user.role == Role.ADMIN and user.skip_confirmation


def require_confirmation(
    user: User, tool_name: str, arguments: dict, description: str
) -> None:
    """Call at the top of any destructive tool handler. Raises ConfirmationRequired
    if no valid confirm_token is present among `arguments`; returns normally
    (consuming the token) if the token is valid; does nothing if the user is an
    admin with skip_confirmation enabled."""
    if user_bypasses_confirmation(user):
        return

    token = arguments.get("confirm_token")
    args_hash = _hash_args(tool_name, arguments)

    if not token:
        new_token = secrets.token_urlsafe(24)
        _pending[new_token] = PendingConfirmation(new_token, tool_name, args_hash, user.username)
        raise ConfirmationRequired(new_token, tool_name, description)

    pending = _pending.get(token)
    if (
        not pending
        or pending.tool_name != tool_name
        or pending.args_hash != args_hash
        or pending.username != user.username
        or dt.datetime.utcnow() > pending.expires_at
    ):
        new_token = secrets.token_urlsafe(24)
        _pending[new_token] = PendingConfirmation(new_token, tool_name, args_hash, user.username)
        raise ConfirmationRequired(
            new_token,
            tool_name,
            f"Confirm-Token ungültig oder abgelaufen. Neuer Token ausgestellt: {description}",
        )

    del _pending[token]


def purge_expired() -> None:
    now = dt.datetime.utcnow()
    expired = [t for t, p in _pending.items() if now > p.expires_at]
    for t in expired:
        del _pending[t]
