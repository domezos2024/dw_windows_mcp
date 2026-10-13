"""Text-to-speech via Windows SAPI5 (through pywin32, already a dependency —
no extra TTS package needed). `tts.text_to_mp3` needs ffmpeg on PATH for the
WAV->MP3 step; without it, use `tts.text_to_wav` instead."""
from __future__ import annotations

import shutil
import subprocess

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool
from .filesystem import _check_allowed

SSFM_CREATE_FOR_WRITE = 3


@tool(
    name="tts.speak",
    category=ToolCategory.AUDIO,
    description="Spricht Text sofort über die Standard-Audioausgabe aus (blockiert bis fertig).",
)
def speak(user: User, text: str, rate: int = 0, volume: int = 100) -> dict:
    import win32com.client

    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.Rate = rate
    voice.Volume = volume
    voice.Speak(text)
    return {"chars_spoken": len(text)}


def _speak_to_wav(text: str, wav_path: str, rate: int = 0, volume: int = 100) -> None:
    import win32com.client

    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    stream.Open(wav_path, SSFM_CREATE_FOR_WRITE, False)
    voice.AudioOutputStream = stream
    voice.Rate = rate
    voice.Volume = volume
    voice.Speak(text)
    stream.Close()


@tool(
    name="tts.text_to_wav",
    category=ToolCategory.AUDIO,
    description="Wandelt Text in eine WAV-Audiodatei um (immer verfügbar, kein externes Tool nötig).",
)
def text_to_wav(user: User, text: str, path: str, rate: int = 0, volume: int = 100) -> dict:
    p = _check_allowed(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _speak_to_wav(text, str(p), rate=rate, volume=volume)
    return {"path": str(p)}


@tool(
    name="tts.text_to_mp3",
    category=ToolCategory.AUDIO,
    description="Wandelt Text in eine MP3-Datei um. Benötigt ffmpeg auf dem PATH "
    "(sonst Fehler — dann tts.text_to_wav nutzen).",
)
def text_to_mp3(user: User, text: str, path: str, rate: int = 0, volume: int = 100) -> dict:
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg nicht auf dem PATH gefunden — für MP3-Export installieren, "
            "oder tts.text_to_wav für eine WAV-Datei ohne diese Abhängigkeit nutzen."
        )

    p = _check_allowed(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wav_path = p.with_suffix(".tmp.wav")

    _speak_to_wav(text, str(wav_path), rate=rate, volume=volume)
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), str(p)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffmpeg-Konvertierung fehlgeschlagen")
    finally:
        wav_path.unlink(missing_ok=True)

    return {"path": str(p)}
