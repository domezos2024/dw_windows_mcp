"""Power management: shutdown / restart / sleep / lock. All state-changing
actions here are destructive — they always require a confirm token (even for
admins, unless skip_confirmation is set)."""
from __future__ import annotations

import subprocess

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="power.lock",
    category=ToolCategory.POWER,
    description="Sperrt die aktuelle Windows-Sitzung (nicht destruktiv, kein Datenverlust).",
)
def lock(user: User) -> dict:
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
    return {"action": "lock"}


@tool(
    name="power.shutdown",
    category=ToolCategory.POWER,
    description="Fährt den PC herunter.",
    destructive=True,
    confirm_description="Fährt den gesamten PC herunter — alle ungesicherte Arbeit geht verloren.",
)
def shutdown(user: User, delay_seconds: int = 10, confirm_token: str | None = None) -> dict:
    subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], check=True)
    return {"action": "shutdown", "delay_seconds": delay_seconds}


@tool(
    name="power.restart",
    category=ToolCategory.POWER,
    description="Startet den PC neu.",
    destructive=True,
    confirm_description="Startet den gesamten PC neu — alle ungesicherte Arbeit geht verloren.",
)
def restart(user: User, delay_seconds: int = 10, confirm_token: str | None = None) -> dict:
    subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], check=True)
    return {"action": "restart", "delay_seconds": delay_seconds}


@tool(
    name="power.sleep",
    category=ToolCategory.POWER,
    description="Versetzt den PC in den Ruhezustand (Standby).",
    destructive=True,
    confirm_description="Versetzt den PC in Standby — laufende Netzwerkverbindungen/Remote-Sitzungen werden unterbrochen.",
)
def sleep(user: User, confirm_token: str | None = None) -> dict:
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True
    )
    return {"action": "sleep"}


@tool(
    name="power.cancel_shutdown",
    category=ToolCategory.POWER,
    description="Bricht einen zuvor geplanten Shutdown/Restart ab.",
)
def cancel_shutdown(user: User) -> dict:
    subprocess.run(["shutdown", "/a"], check=False)
    return {"action": "cancel_shutdown"}
