"""fs.* tools only ever touch the DW_MCP_FS_ROOTS sandbox dir set up in
conftest.py — never the real filesystem outside it."""
from __future__ import annotations

import os

from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.confirm import ConfirmationRequired
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool
from dw_windows_mcp.tools.filesystem import FsAccessDenied


def test_write_and_read_inside_sandbox():
    admin = create_user("fs_admin", "Pass1234", Role.ADMIN)
    sandbox = os.environ["DW_MCP_FS_ROOTS"]
    target = os.path.join(sandbox, "note.txt")

    invoke_tool(admin, "fs.write_text", {"path": target, "content": "hallo welt"})
    content = invoke_tool(admin, "fs.read_text", {"path": target})
    assert content == "hallo welt"


def test_path_outside_sandbox_is_denied(tmp_path):
    admin = create_user("fs_admin2", "Pass1234", Role.ADMIN)
    outside = tmp_path / "outside.txt"  # tmp_path is a different temp root
    try:
        invoke_tool(admin, "fs.write_text", {"path": str(outside), "content": "x"})
        assert False, "sollte FsAccessDenied werfen"
    except FsAccessDenied:
        pass
    assert not outside.exists()


def test_delete_requires_confirm_token_and_stays_in_sandbox():
    admin = create_user("fs_admin3", "Pass1234", Role.ADMIN)
    sandbox = os.environ["DW_MCP_FS_ROOTS"]
    target = os.path.join(sandbox, "to_delete.txt")
    invoke_tool(admin, "fs.write_text", {"path": target, "content": "weg damit"})

    try:
        invoke_tool(admin, "fs.delete", {"path": target})
        assert False, "sollte ConfirmationRequired werfen"
    except ConfirmationRequired as cr:
        token = cr.token

    assert os.path.exists(target)
    invoke_tool(admin, "fs.delete", {"path": target, "confirm_token": token})
    assert not os.path.exists(target)
