"""Registry tools run entirely against the in-memory fake winreg from
conftest.py (never the real registry). Process-kill runs against a fake
psutil.Process (never a real PID)."""
from __future__ import annotations

from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.confirm import ConfirmationRequired
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def test_registry_write_read_delete(fake_winreg):
    admin = create_user("reg_admin", "Pass1234", Role.ADMIN)

    try:
        invoke_tool(
            admin,
            "registry.write_value",
            {
                "hive": "HKEY_CURRENT_USER",
                "subkey": r"Software\dw_test",
                "value_name": "Greeting",
                "value": "hallo",
                "value_type": "REG_SZ",
            },
        )
        assert False
    except ConfirmationRequired as cr:
        token = cr.token

    invoke_tool(
        admin,
        "registry.write_value",
        {
            "hive": "HKEY_CURRENT_USER",
            "subkey": r"Software\dw_test",
            "value_name": "Greeting",
            "value": "hallo",
            "value_type": "REG_SZ",
            "confirm_token": token,
        },
    )

    read = invoke_tool(
        admin,
        "registry.read_value",
        {"hive": "HKEY_CURRENT_USER", "subkey": r"Software\dw_test", "value_name": "Greeting"},
    )
    assert read["value"] == "hallo"

    try:
        invoke_tool(
            admin,
            "registry.delete_value",
            {"hive": "HKEY_CURRENT_USER", "subkey": r"Software\dw_test", "value_name": "Greeting"},
        )
        assert False
    except ConfirmationRequired as cr:
        token2 = cr.token

    invoke_tool(
        admin,
        "registry.delete_value",
        {
            "hive": "HKEY_CURRENT_USER",
            "subkey": r"Software\dw_test",
            "value_name": "Greeting",
            "confirm_token": token2,
        },
    )


def test_process_kill_requires_confirm_and_uses_fake_process(fake_psutil_process):
    admin = create_user("proc_admin", "Pass1234", Role.ADMIN)

    try:
        invoke_tool(admin, "process.kill", {"pid": 4321})
        assert False
    except ConfirmationRequired as cr:
        token = cr.token

    result = invoke_tool(admin, "process.kill", {"pid": 4321, "confirm_token": token})
    assert result["killed_pid"] == 4321
    assert fake_psutil_process == [4321]
