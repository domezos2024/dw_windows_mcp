"""Autostart install/uninstall/status only ever call the mocked subprocess.run
from conftest.py — this test suite never registers or deletes a real
scheduled task on the host."""
from __future__ import annotations

from dw_windows_mcp import autostart


def test_install_builds_correct_schtasks_command(_block_real_subprocess):
    autostart.install(host="127.0.0.1", port=9999)

    assert len(_block_real_subprocess) == 1
    args = _block_real_subprocess[0]["args"]
    assert args[0] == "schtasks"
    assert "/Create" in args
    assert autostart.TASK_NAME in args
    assert "ONLOGON" in args
    joined = " ".join(args)
    assert "run-http" in joined
    assert "127.0.0.1" in joined
    assert "9999" in joined


def test_uninstall_builds_correct_schtasks_command(_block_real_subprocess):
    autostart.uninstall()

    args = _block_real_subprocess[0]["args"]
    assert args[0] == "schtasks"
    assert "/Delete" in args
    assert autostart.TASK_NAME in args
