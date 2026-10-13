"""GUI automation: screenshot, mouse, keyboard — via pyautogui."""
from __future__ import annotations

import base64
import io

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool


@tool(
    name="gui.screenshot",
    category=ToolCategory.GUI_AUTOMATION,
    description="Erstellt einen Screenshot und gibt ihn als Base64-PNG zurück.",
)
def screenshot(user: User) -> dict:
    import pyautogui

    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"png_base64": base64.b64encode(buf.getvalue()).decode(), "width": img.width, "height": img.height}


@tool(
    name="gui.mouse_move",
    category=ToolCategory.GUI_AUTOMATION,
    description="Bewegt die Maus an eine Position, ohne zu klicken.",
)
def mouse_move(user: User, x: int, y: int, duration_seconds: float = 0.0) -> dict:
    import pyautogui

    pyautogui.moveTo(x, y, duration=duration_seconds)
    return {"x": x, "y": y}


@tool(
    name="gui.mouse_click",
    category=ToolCategory.GUI_AUTOMATION,
    description="Bewegt die Maus an eine Position und klickt (left/right/middle).",
)
def mouse_click(user: User, x: int, y: int, button: str = "left") -> dict:
    import pyautogui

    pyautogui.click(x=x, y=y, button=button)
    return {"x": x, "y": y, "button": button}


@tool(
    name="gui.type_text",
    category=ToolCategory.GUI_AUTOMATION,
    description="Tippt Text an der aktuellen Cursor-Position.",
)
def type_text(user: User, text: str, interval_seconds: float = 0.01) -> dict:
    import pyautogui

    pyautogui.write(text, interval=interval_seconds)
    return {"chars_typed": len(text)}


@tool(
    name="gui.key_press",
    category=ToolCategory.GUI_AUTOMATION,
    description="Drückt eine Tastenkombination, z.B. ['ctrl','c'].",
)
def key_press(user: User, keys: list[str]) -> dict:
    import pyautogui

    pyautogui.hotkey(*keys)
    return {"keys": keys}
