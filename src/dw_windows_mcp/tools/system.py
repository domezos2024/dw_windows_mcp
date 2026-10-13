"""System information tools (read-only, available to every role)."""
from __future__ import annotations

import platform
import socket

import psutil

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="system.info",
    category=ToolCategory.SYSTEM_INFO,
    description="Grundlegende System-Informationen: OS, Hostname, CPU, RAM, Uptime.",
)
def system_info(user: User) -> dict:
    vm = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_total_gb": round(vm.total / 1024**3, 2),
        "ram_used_percent": vm.percent,
        "boot_time": psutil.boot_time(),
    }


@tool(
    name="system.disks",
    category=ToolCategory.SYSTEM_INFO,
    description="Liste aller Laufwerke mit Speicherplatz-Nutzung.",
)
def system_disks(user: User) -> list[dict]:
    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        disks.append(
            {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": round(usage.total / 1024**3, 2),
                "used_gb": round(usage.used / 1024**3, 2),
                "free_gb": round(usage.free / 1024**3, 2),
                "percent": usage.percent,
            }
        )
    return disks
