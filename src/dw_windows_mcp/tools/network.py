"""Read-only network diagnostics."""
from __future__ import annotations

import socket
import subprocess

import psutil

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="network.info",
    category=ToolCategory.NETWORK_READ,
    description="Netzwerk-Interfaces mit IP-Adressen.",
)
def network_info(user: User) -> dict:
    interfaces = {}
    for name, addrs in psutil.net_if_addrs().items():
        interfaces[name] = [
            {"family": str(a.family), "address": a.address} for a in addrs
        ]
    return {"hostname": socket.gethostname(), "interfaces": interfaces}


@tool(
    name="network.connections",
    category=ToolCategory.NETWORK_READ,
    description="Aktive Netzwerkverbindungen (lokale/entfernte Adresse, Status, PID).",
)
def connections(user: User) -> list[dict]:
    result = []
    for c in psutil.net_connections(kind="inet"):
        result.append(
            {
                "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                "status": c.status,
                "pid": c.pid,
            }
        )
    return result


@tool(
    name="network.ping",
    category=ToolCategory.NETWORK_READ,
    description="Pingt einen Host an (4 Pakete).",
)
def ping(user: User, host: str) -> dict:
    proc = subprocess.run(["ping", "-n", "4", host], check=False, capture_output=True, text=True, timeout=20)
    return {"host": host, "output": proc.stdout, "reachable": proc.returncode == 0}
