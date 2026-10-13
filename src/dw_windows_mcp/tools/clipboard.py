"""Clipboard access via pywin32."""
from __future__ import annotations

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="clipboard.get",
    category=ToolCategory.CLIPBOARD,
    description="Liest den aktuellen Text-Inhalt der Zwischenablage.",
)
def get_clipboard(user: User) -> dict:
    import win32clipboard

    win32clipboard.OpenClipboard()
    try:
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except TypeError:
            text = ""
    finally:
        win32clipboard.CloseClipboard()
    return {"text": text}


@tool(
    name="clipboard.set",
    category=ToolCategory.CLIPBOARD,
    description="Setzt den Text-Inhalt der Zwischenablage.",
)
def set_clipboard(user: User, text: str) -> dict:
    import win32clipboard

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()
    return {"bytes_set": len(text)}
