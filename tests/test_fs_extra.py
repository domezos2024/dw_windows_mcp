"""fs.batch_rename (dry_run safety + confirm-token on real execution) and
fs.compare_files — all confined to the sandbox temp dir."""
from __future__ import annotations

import os

from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.confirm import ConfirmationRequired
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def _sandbox() -> str:
    return os.environ["DW_MCP_FS_ROOTS"]


def test_batch_rename_dry_run_does_not_touch_files():
    admin = create_user("rename_admin", "Pass1234", Role.STANDARD)
    d = os.path.join(_sandbox(), "batch1")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "img_001.jpg"), "w").close()
    open(os.path.join(d, "img_002.jpg"), "w").close()

    result = invoke_tool(
        admin, "fs.batch_rename", {"directory": d, "pattern": r"img_(\d+)", "replacement": r"photo_\1"}
    )
    assert result["dry_run"] is True
    assert len(result["planned_renames"]) == 2
    assert os.path.exists(os.path.join(d, "img_001.jpg"))
    assert not os.path.exists(os.path.join(d, "photo_001.jpg"))


def test_batch_rename_execution_requires_confirm_token():
    admin = create_user("rename_admin2", "Pass1234", Role.STANDARD)
    d = os.path.join(_sandbox(), "batch2")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "img_001.jpg"), "w").close()

    args = {"directory": d, "pattern": r"img_(\d+)", "replacement": r"photo_\1", "dry_run": False}
    try:
        invoke_tool(admin, "fs.batch_rename", args)
        assert False
    except ConfirmationRequired as cr:
        token = cr.token

    result = invoke_tool(admin, "fs.batch_rename", {**args, "confirm_token": token})
    assert result["dry_run"] is False
    assert os.path.exists(os.path.join(d, "photo_001.jpg"))
    assert not os.path.exists(os.path.join(d, "img_001.jpg"))


def test_compare_files_identical_and_diff():
    admin = create_user("cmp_admin", "Pass1234", Role.STANDARD)
    a = os.path.join(_sandbox(), "a.txt")
    b = os.path.join(_sandbox(), "b.txt")
    c = os.path.join(_sandbox(), "c.txt")

    with open(a, "w") as f:
        f.write("zeile1\nzeile2\n")
    with open(b, "w") as f:
        f.write("zeile1\nzeile2\n")
    with open(c, "w") as f:
        f.write("zeile1\nANDERS\n")

    identical = invoke_tool(admin, "fs.compare_files", {"path_a": a, "path_b": b})
    assert identical["identical"] is True
    assert identical["diff"] is None

    different = invoke_tool(admin, "fs.compare_files", {"path_a": a, "path_b": c})
    assert different["identical"] is False
    assert any("ANDERS" in line for line in different["diff"])
