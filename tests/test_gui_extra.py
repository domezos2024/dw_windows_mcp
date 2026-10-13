"""gui.mouse_move — against a fake pyautogui, never the real mouse."""
from __future__ import annotations

from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def test_mouse_move_calls_fake_pyautogui(fake_pyautogui):
    admin = create_user("gui_admin", "Pass1234", Role.STANDARD)
    result = invoke_tool(admin, "gui.mouse_move", {"x": 123, "y": 456})
    assert result == {"x": 123, "y": 456}
    assert ("moveTo", (123, 456), {"duration": 0.0}) in fake_pyautogui
