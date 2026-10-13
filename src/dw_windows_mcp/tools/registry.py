"""Windows registry access, via stdlib winreg (Windows-only)."""
from __future__ import annotations

import sys

from ..db import User
from ..auth.rbac import ToolCategory
from . import tool

if sys.platform == "win32":
    import winreg

    _HIVES = {
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_USERS": winreg.HKEY_USERS,
        "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
    }
else:
    winreg = None
    _HIVES = {}


def _resolve_hive(hive_name: str):
    if winreg is None:
        raise RuntimeError("Registry-Zugriff ist nur unter Windows verfügbar.")
    hive = _HIVES.get(hive_name.upper())
    if hive is None:
        raise ValueError(f"Unbekannte Hive '{hive_name}'. Erlaubt: {list(_HIVES)}")
    return hive


@tool(
    name="registry.read_value",
    category=ToolCategory.REGISTRY_READ,
    description="Liest einen Registry-Wert (hive, subkey, value_name).",
)
def read_value(user: User, hive: str, subkey: str, value_name: str) -> dict:
    h = _resolve_hive(hive)
    with winreg.OpenKey(h, subkey) as key:
        value, reg_type = winreg.QueryValueEx(key, value_name)
    return {"value": value, "type": reg_type}


@tool(
    name="registry.list_values",
    category=ToolCategory.REGISTRY_READ,
    description="Listet alle Werte und Subkeys unter einem Registry-Pfad.",
)
def list_values(user: User, hive: str, subkey: str) -> dict:
    h = _resolve_hive(hive)
    values, subkeys = [], []
    with winreg.OpenKey(h, subkey) as key:
        i = 0
        while True:
            try:
                name, value, reg_type = winreg.EnumValue(key, i)
                values.append({"name": name, "value": value, "type": reg_type})
                i += 1
            except OSError:
                break
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
    return {"values": values, "subkeys": subkeys}


@tool(
    name="registry.write_value",
    category=ToolCategory.REGISTRY_WRITE,
    description="Schreibt/überschreibt einen Registry-Wert.",
    destructive=True,
    confirm_description="Schreibt einen Registry-Wert — kann Systemverhalten/Anwendungen beeinflussen.",
)
def write_value(
    user: User,
    hive: str,
    subkey: str,
    value_name: str,
    value,
    value_type: str = "REG_SZ",
    confirm_token: str | None = None,
) -> dict:
    h = _resolve_hive(hive)
    reg_type = getattr(winreg, value_type)
    with winreg.CreateKeyEx(h, subkey) as key:
        winreg.SetValueEx(key, value_name, 0, reg_type, value)
    return {"hive": hive, "subkey": subkey, "value_name": value_name}


@tool(
    name="registry.delete_value",
    category=ToolCategory.REGISTRY_WRITE,
    description="Löscht einen Registry-Wert unwiderruflich.",
    destructive=True,
    confirm_description="Löscht einen Registry-Wert unwiderruflich.",
)
def delete_value(user: User, hive: str, subkey: str, value_name: str, confirm_token: str | None = None) -> dict:
    h = _resolve_hive(hive)
    with winreg.OpenKey(h, subkey, 0, winreg.KEY_SET_VALUE) as key:
        winreg.DeleteValue(key, value_name)
    return {"deleted": value_name}
