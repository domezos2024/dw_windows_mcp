"""Simple per-user key/value memory store (SQLite-backed), so an AI client can
remember small bits of state across sessions without a full database tool."""
from __future__ import annotations

from sqlalchemy import select

from ..auth.rbac import ToolCategory
from ..db import KVEntry, User, get_session, utcnow
from . import tool


@tool(
    name="memory.set",
    category=ToolCategory.MEMORY_WRITE,
    description="Speichert einen Wert unter einem Schlüssel (pro Benutzer, optional Namespace).",
)
def memory_set(user: User, key: str, value: str, namespace: str = "default") -> dict:
    with get_session() as s:
        entry = s.scalar(
            select(KVEntry).where(
                KVEntry.username == user.username, KVEntry.namespace == namespace, KVEntry.key == key
            )
        )
        if entry:
            entry.value = value
            entry.updated_at = utcnow()
        else:
            entry = KVEntry(username=user.username, namespace=namespace, key=key, value=value)
            s.add(entry)
        s.commit()
    return {"namespace": namespace, "key": key, "stored": True}


@tool(
    name="memory.get",
    category=ToolCategory.MEMORY_READ,
    description="Liest einen zuvor gespeicherten Wert.",
)
def memory_get(user: User, key: str, namespace: str = "default") -> dict:
    with get_session() as s:
        entry = s.scalar(
            select(KVEntry).where(
                KVEntry.username == user.username, KVEntry.namespace == namespace, KVEntry.key == key
            )
        )
    if not entry:
        return {"namespace": namespace, "key": key, "found": False, "value": None}
    return {"namespace": namespace, "key": key, "found": True, "value": entry.value}


@tool(
    name="memory.list",
    category=ToolCategory.MEMORY_READ,
    description="Listet alle Schlüssel in einem Namespace.",
)
def memory_list(user: User, namespace: str = "default") -> list[dict]:
    with get_session() as s:
        entries = s.scalars(
            select(KVEntry).where(KVEntry.username == user.username, KVEntry.namespace == namespace)
        ).all()
    return [{"key": e.key, "value": e.value, "updated_at": str(e.updated_at)} for e in entries]


@tool(
    name="memory.delete",
    category=ToolCategory.MEMORY_WRITE,
    description="Löscht einen gespeicherten Schlüssel.",
)
def memory_delete(user: User, key: str, namespace: str = "default") -> dict:
    with get_session() as s:
        entry = s.scalar(
            select(KVEntry).where(
                KVEntry.username == user.username, KVEntry.namespace == namespace, KVEntry.key == key
            )
        )
        if entry:
            s.delete(entry)
            s.commit()
    return {"namespace": namespace, "key": key, "deleted": entry is not None}
