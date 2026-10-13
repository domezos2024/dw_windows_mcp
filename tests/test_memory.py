"""memory.* key/value store — real SQLite, confined to the test DB."""
from __future__ import annotations

from dw_windows_mcp.auth.rbac import PermissionError_
from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def test_set_get_delete_roundtrip():
    admin = create_user("mem_admin", "Pass1234", Role.STANDARD)

    invoke_tool(admin, "memory.set", {"key": "greeting", "value": "hallo"})
    got = invoke_tool(admin, "memory.get", {"key": "greeting"})
    assert got == {"namespace": "default", "key": "greeting", "found": True, "value": "hallo"}

    invoke_tool(admin, "memory.delete", {"key": "greeting"})
    got2 = invoke_tool(admin, "memory.get", {"key": "greeting"})
    assert got2["found"] is False


def test_list_scoped_to_namespace():
    admin = create_user("mem_admin2", "Pass1234", Role.STANDARD)
    invoke_tool(admin, "memory.set", {"key": "a", "value": "1", "namespace": "ns1"})
    invoke_tool(admin, "memory.set", {"key": "b", "value": "2", "namespace": "ns1"})
    invoke_tool(admin, "memory.set", {"key": "c", "value": "3", "namespace": "ns2"})

    ns1 = invoke_tool(admin, "memory.list", {"namespace": "ns1"})
    assert {e["key"] for e in ns1} == {"a", "b"}


def test_entries_are_isolated_per_user():
    alice = create_user("mem_alice", "Pass1234", Role.STANDARD)
    bob = create_user("mem_bob", "Pass1234", Role.STANDARD)

    invoke_tool(alice, "memory.set", {"key": "secret", "value": "alice-value"})
    bob_view = invoke_tool(bob, "memory.get", {"key": "secret"})
    assert bob_view["found"] is False


def test_readonly_cannot_write():
    readonly = create_user("mem_ro", "Pass1234", Role.READONLY)
    try:
        invoke_tool(readonly, "memory.set", {"key": "x", "value": "y"})
        assert False
    except PermissionError_:
        pass
    # readonly can still read
    invoke_tool(readonly, "memory.get", {"key": "x"})
