"""Software installation via winget."""
from __future__ import annotations

import subprocess

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


def _winget(*args: str, timeout: int = 300) -> str:
    proc = subprocess.run(
        ["winget", *args, "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.stdout + proc.stderr


@tool(
    name="install.search",
    category=ToolCategory.INSTALL,
    description="Sucht ein Paket in den winget-Quellen.",
)
def search(user: User, query: str) -> dict:
    output = _winget("search", query, timeout=60)
    return {"query": query, "output": output}


@tool(
    name="install.install",
    category=ToolCategory.INSTALL,
    description="Installiert ein Paket per winget.",
    destructive=True,
    confirm_description="Installiert Software auf dem System via winget.",
)
def install(user: User, package_id: str, confirm_token: str | None = None) -> dict:
    output = _winget("install", "--id", package_id, "-e")
    return {"package_id": package_id, "output": output}


@tool(
    name="install.uninstall",
    category=ToolCategory.INSTALL,
    description="Deinstalliert ein Paket per winget.",
    destructive=True,
    confirm_description="Deinstalliert Software vom System via winget.",
)
def uninstall(user: User, package_id: str, confirm_token: str | None = None) -> dict:
    output = _winget("uninstall", "--id", package_id, "-e")
    return {"package_id": package_id, "output": output}


@tool(
    name="install.list_installed",
    category=ToolCategory.INSTALL,
    description="Listet installierte Pakete (winget list).",
)
def list_installed(user: User) -> dict:
    output = _winget("list", timeout=60)
    return {"output": output}
