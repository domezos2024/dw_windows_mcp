"""Windows autostart via Task Scheduler (`schtasks`). Registers a task that
runs `dw-windows-mcp run-http` when the current user logs in."""
from __future__ import annotations

import shutil
import subprocess
import sys

TASK_NAME = "dw-windows-mcp-autostart"


def _dw_windows_mcp_exe() -> str:
    exe = shutil.which("dw-windows-mcp")
    if exe:
        return exe
    return f'"{sys.executable}" -m dw_windows_mcp.cli'


def install(host: str = "0.0.0.0", port: int = 8765) -> str:
    exe = _dw_windows_mcp_exe()
    command = f'{exe} run-http --host {host} --port {port}'
    args = [
        "schtasks",
        "/Create",
        "/F",
        "/TN",
        TASK_NAME,
        "/TR",
        command,
        "/SC",
        "ONLOGON",
        "/RL",
        "LIMITED",
    ]
    proc = subprocess.run(args, check=False, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def uninstall() -> str:
    proc = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        check=False, capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def status() -> str:
    proc = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
        check=False, capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return "nicht installiert"
    return proc.stdout.strip()
