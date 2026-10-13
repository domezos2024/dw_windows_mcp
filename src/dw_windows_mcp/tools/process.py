"""Process listing and control."""
from __future__ import annotations

import subprocess

import psutil

from ..db import User
from ..auth.rbac import ToolCategory
from . import tool


@tool(
    name="process.list",
    category=ToolCategory.PROCESS_READ,
    description="Listet laufende Prozesse (PID, Name, CPU%, RAM-MB, Owner).",
)
def process_list(user: User) -> list[dict]:
    result = []
    for p in psutil.process_iter(["pid", "name", "username", "memory_info", "cpu_percent"]):
        info = p.info
        mem = info.get("memory_info")
        result.append(
            {
                "pid": info.get("pid"),
                "name": info.get("name"),
                "username": info.get("username"),
                "ram_mb": round(mem.rss / 1024**2, 1) if mem else None,
                "cpu_percent": info.get("cpu_percent"),
            }
        )
    return result


@tool(
    name="process.start",
    category=ToolCategory.PROCESS_WRITE,
    description="Startet einen neuen Prozess (ohne Shell-Interpretation).",
)
def process_start(user: User, executable: str, args: list[str] | None = None) -> dict:
    proc = subprocess.Popen([executable, *(args or [])])
    return {"pid": proc.pid, "executable": executable}


@tool(
    name="process.kill",
    category=ToolCategory.PROCESS_WRITE,
    description="Beendet einen Prozess per PID unwiderruflich.",
    destructive=True,
    confirm_description="Beendet den angegebenen Prozess (force-kill, kein Speichern laufender Arbeit).",
)
def process_kill(user: User, pid: int, confirm_token: str | None = None) -> dict:
    p = psutil.Process(pid)
    name = p.name()
    p.kill()
    return {"killed_pid": pid, "name": name}
