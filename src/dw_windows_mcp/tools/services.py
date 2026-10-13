"""Windows service control via `sc` / psutil (no pywin32 dependency needed here)."""
from __future__ import annotations

import subprocess

import psutil

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="services.list",
    category=ToolCategory.SERVICES_READ,
    description="Listet installierte Windows-Dienste mit Status.",
)
def list_services(user: User) -> list[dict]:
    return [
        {"name": s.name(), "display_name": s.display_name(), "status": s.status()}
        for s in psutil.win_service_iter()
    ]


def _sc(*args: str) -> str:
    proc = subprocess.run(["sc", *args], check=False, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


@tool(
    name="services.start",
    category=ToolCategory.SERVICES_WRITE,
    description="Startet einen Windows-Dienst.",
)
def start_service(user: User, service_name: str) -> dict:
    _sc("start", service_name)
    return {"service": service_name, "action": "start"}


@tool(
    name="services.stop",
    category=ToolCategory.SERVICES_WRITE,
    description="Stoppt einen Windows-Dienst.",
    destructive=True,
    confirm_description="Stoppt einen laufenden Windows-Dienst — kann abhängige Funktionen beeinträchtigen.",
)
def stop_service(user: User, service_name: str, confirm_token: str | None = None) -> dict:
    _sc("stop", service_name)
    return {"service": service_name, "action": "stop"}


@tool(
    name="services.restart",
    category=ToolCategory.SERVICES_WRITE,
    description="Startet einen Windows-Dienst neu.",
    destructive=True,
    confirm_description="Startet einen Windows-Dienst neu — kurzer Ausfall des Dienstes möglich.",
)
def restart_service(user: User, service_name: str, confirm_token: str | None = None) -> dict:
    try:
        _sc("stop", service_name)
    except RuntimeError:
        pass
    _sc("start", service_name)
    return {"service": service_name, "action": "restart"}
