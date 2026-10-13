"""Filesystem tools. If DW_MCP_FS_ROOTS is set, access is restricted to those
root directories (and their subpaths); if unset, the whole filesystem is in
scope for the roles that have filesystem_write/read permission."""
from __future__ import annotations

import difflib
import hashlib
import re
import shutil
from pathlib import Path

from ..auth.rbac import ToolCategory
from ..config import settings
from ..confirm import require_confirmation
from ..db import User
from . import tool


class FsAccessDenied(Exception):
    pass


def _check_allowed(path: str) -> Path:
    p = Path(path).resolve()
    roots = settings.allowed_fs_roots
    if roots and not any(str(p).lower().startswith(str(Path(r).resolve()).lower()) for r in roots):
        raise FsAccessDenied(f"Pfad '{p}' liegt außerhalb der erlaubten Wurzeln: {roots}")
    return p


@tool(
    name="fs.list_dir",
    category=ToolCategory.FILESYSTEM_READ,
    description="Listet Dateien/Ordner in einem Verzeichnis auf.",
)
def list_dir(user: User, path: str) -> list[dict]:
    p = _check_allowed(path)
    entries = []
    for entry in p.iterdir():
        try:
            stat = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                }
            )
        except OSError:
            continue
    return entries


@tool(
    name="fs.read_text",
    category=ToolCategory.FILESYSTEM_READ,
    description="Liest den Textinhalt einer Datei (UTF-8, max. 1 MB).",
)
def read_text(user: User, path: str) -> str:
    p = _check_allowed(path)
    if p.stat().st_size > 1024 * 1024:
        raise ValueError("Datei größer als 1 MB — nutze fs.read_bytes_chunk für große Dateien.")
    return p.read_text(encoding="utf-8", errors="replace")


@tool(
    name="fs.write_text",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Schreibt Textinhalt in eine Datei (überschreibt falls vorhanden).",
)
def write_text(user: User, path: str, content: str, append: bool = False) -> dict:
    p = _check_allowed(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(p, mode, encoding="utf-8") as f:
        f.write(content)
    return {"path": str(p), "bytes_written": len(content.encode("utf-8"))}


@tool(
    name="fs.mkdir",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Erstellt ein Verzeichnis (inkl. Elternverzeichnisse).",
)
def mkdir(user: User, path: str) -> dict:
    p = _check_allowed(path)
    p.mkdir(parents=True, exist_ok=True)
    return {"path": str(p)}


@tool(
    name="fs.copy",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Kopiert eine Datei oder ein Verzeichnis.",
)
def copy(user: User, source: str, destination: str) -> dict:
    src = _check_allowed(source)
    dst = _check_allowed(destination)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return {"source": str(src), "destination": str(dst)}


@tool(
    name="fs.move",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Verschiebt/benennt eine Datei oder ein Verzeichnis um.",
)
def move(user: User, source: str, destination: str) -> dict:
    src = _check_allowed(source)
    dst = _check_allowed(destination)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source": str(src), "destination": str(dst)}


@tool(
    name="fs.delete",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Löscht eine Datei oder ein Verzeichnis (rekursiv) unwiderruflich.",
    destructive=True,
    confirm_description="Löscht die angegebene Datei/den angegebenen Ordner unwiderruflich (kein Papierkorb).",
)
def delete(user: User, path: str, confirm_token: str | None = None) -> dict:
    p = _check_allowed(path)
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return {"deleted": str(p)}


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


@tool(
    name="fs.compare_files",
    category=ToolCategory.FILESYSTEM_READ,
    description="Vergleicht zwei Dateien (Hash-Gleichheit + Text-Diff falls Textdatei).",
)
def compare_files(user: User, path_a: str, path_b: str) -> dict:
    a = _check_allowed(path_a)
    b = _check_allowed(path_b)
    size_a, size_b = a.stat().st_size, b.stat().st_size
    identical = size_a == size_b and _hash_file(a) == _hash_file(b)

    diff_lines: list[str] | None = None
    if not identical and size_a < 2 * 1024 * 1024 and size_b < 2 * 1024 * 1024:
        try:
            text_a = a.read_text(encoding="utf-8", errors="strict").splitlines(keepends=True)
            text_b = b.read_text(encoding="utf-8", errors="strict").splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(text_a, text_b, fromfile=str(a), tofile=str(b)))[:500]
        except UnicodeDecodeError:
            diff_lines = None  # binary file — no text diff

    return {
        "identical": identical,
        "size_a": size_a,
        "size_b": size_b,
        "diff": diff_lines,
    }


@tool(
    name="fs.batch_rename",
    category=ToolCategory.FILESYSTEM_WRITE,
    description="Benennt mehrere Dateien in einem Verzeichnis per Regex-Suchen/Ersetzen um. "
    "dry_run=true (Standard) zeigt nur die geplanten Umbenennungen, ohne sie auszuführen "
    "(kein Confirm-Token nötig). Erst dry_run=false führt sie aus und erfordert einen Confirm-Token.",
)
def batch_rename(
    user: User,
    directory: str,
    pattern: str,
    replacement: str,
    dry_run: bool = True,
    confirm_token: str | None = None,
) -> dict:
    d = _check_allowed(directory)
    regex = re.compile(pattern)
    planned = []
    for entry in d.iterdir():
        if not entry.is_file():
            continue
        new_name = regex.sub(replacement, entry.name)
        if new_name != entry.name:
            planned.append({"old": entry.name, "new": new_name})

    if dry_run:
        return {"dry_run": True, "planned_renames": planned}

    # Nur die tatsächliche Ausführung (dry_run=false) braucht einen Confirm-Token.
    require_confirmation(
        user,
        "fs.batch_rename",
        {"directory": directory, "pattern": pattern, "replacement": replacement, "confirm_token": confirm_token},
        f"Benennt {len(planned)} Datei(en) in '{d}' gemäß Muster '{pattern}' -> '{replacement}' um.",
    )

    executed = []
    for item in planned:
        src = d / item["old"]
        dst = d / item["new"]
        src.rename(dst)
        executed.append(item)
    return {"dry_run": False, "renamed": executed}
