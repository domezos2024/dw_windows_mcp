"""Role-based access control: which role may use which tool category, and which
tools are destructive enough to require an explicit confirmation step regardless
of role (including admin)."""
from __future__ import annotations

from dataclasses import dataclass

from ..db import Role


class ToolCategory:
    SYSTEM_INFO = "system_info"
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    PROCESS_READ = "process_read"
    PROCESS_WRITE = "process_write"
    REGISTRY_READ = "registry_read"
    REGISTRY_WRITE = "registry_write"
    SERVICES_READ = "services_read"
    SERVICES_WRITE = "services_write"
    POWER = "power"
    NETWORK_READ = "network_read"
    NETWORK_WRITE = "network_write"
    INSTALL = "install"
    GUI_AUTOMATION = "gui_automation"
    CLIPBOARD = "clipboard"
    AUDIO = "audio"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"


# Role -> set of categories it may invoke at all.
ROLE_CATEGORIES: dict[Role, set[str]] = {
    Role.READONLY: {
        ToolCategory.SYSTEM_INFO,
        ToolCategory.FILESYSTEM_READ,
        ToolCategory.PROCESS_READ,
        ToolCategory.REGISTRY_READ,
        ToolCategory.SERVICES_READ,
        ToolCategory.NETWORK_READ,
        ToolCategory.CLIPBOARD,
        ToolCategory.MEMORY_READ,
    },
    Role.STANDARD: {
        ToolCategory.SYSTEM_INFO,
        ToolCategory.FILESYSTEM_READ,
        ToolCategory.FILESYSTEM_WRITE,
        ToolCategory.PROCESS_READ,
        ToolCategory.PROCESS_WRITE,
        ToolCategory.REGISTRY_READ,
        ToolCategory.SERVICES_READ,
        ToolCategory.NETWORK_READ,
        ToolCategory.NETWORK_WRITE,
        ToolCategory.INSTALL,
        ToolCategory.GUI_AUTOMATION,
        ToolCategory.CLIPBOARD,
        ToolCategory.AUDIO,
        ToolCategory.MEMORY_READ,
        ToolCategory.MEMORY_WRITE,
    },
    Role.ADMIN: {
        ToolCategory.SYSTEM_INFO,
        ToolCategory.FILESYSTEM_READ,
        ToolCategory.FILESYSTEM_WRITE,
        ToolCategory.PROCESS_READ,
        ToolCategory.PROCESS_WRITE,
        ToolCategory.REGISTRY_READ,
        ToolCategory.REGISTRY_WRITE,
        ToolCategory.SERVICES_READ,
        ToolCategory.SERVICES_WRITE,
        ToolCategory.POWER,
        ToolCategory.NETWORK_READ,
        ToolCategory.NETWORK_WRITE,
        ToolCategory.INSTALL,
        ToolCategory.GUI_AUTOMATION,
        ToolCategory.CLIPBOARD,
        ToolCategory.AUDIO,
        ToolCategory.MEMORY_READ,
        ToolCategory.MEMORY_WRITE,
    },
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    category: str
    destructive: bool = False  # True => requires confirm-token even for admin


class PermissionError_(Exception):
    pass


def role_allows(role: Role, category: str) -> bool:
    return category in ROLE_CATEGORIES.get(role, set())


def require_permission(role: Role, spec: ToolSpec) -> None:
    if not role_allows(role, spec.category):
        raise PermissionError_(
            f"Rolle '{role.value}' hat keine Berechtigung für Kategorie '{spec.category}'"
        )
