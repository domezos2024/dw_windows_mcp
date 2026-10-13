"""tts.* — against a fake win32com SAPI, never the real speech engine."""
from __future__ import annotations

import os

from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def test_speak_calls_fake_sapi(fake_win32com):
    admin = create_user("tts_admin", "Pass1234", Role.STANDARD)
    result = invoke_tool(admin, "tts.speak", {"text": "hallo welt"})
    assert result["chars_spoken"] == len("hallo welt")
    assert ("Speak", "hallo welt") in fake_win32com


def test_text_to_wav_writes_file(fake_win32com):
    admin = create_user("tts_admin2", "Pass1234", Role.STANDARD)
    sandbox = os.environ["DW_MCP_FS_ROOTS"]
    dest = os.path.join(sandbox, "out.wav")

    result = invoke_tool(admin, "tts.text_to_wav", {"text": "test", "path": dest})
    assert result["path"] == dest
    assert os.path.exists(dest)


def test_text_to_mp3_without_ffmpeg_raises(fake_win32com, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)

    admin = create_user("tts_admin3", "Pass1234", Role.STANDARD)
    sandbox = os.environ["DW_MCP_FS_ROOTS"]
    dest = os.path.join(sandbox, "out.mp3")

    try:
        invoke_tool(admin, "tts.text_to_mp3", {"text": "test", "path": dest})
        assert False, "sollte ohne ffmpeg einen RuntimeError auslösen"
    except RuntimeError as e:
        assert "ffmpeg" in str(e)
