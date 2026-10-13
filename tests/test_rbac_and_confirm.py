"""RBAC enforcement, destructive-tool confirm-token round trip, admin opt-out,
and audit logging — all against mocked system calls."""
from __future__ import annotations

from sqlalchemy import select

from dw_windows_mcp.auth.rbac import PermissionError_
from dw_windows_mcp.auth.users import create_user, set_skip_confirmation
from dw_windows_mcp.confirm import ConfirmationRequired
from dw_windows_mcp.db import AuditLog, Role, get_session
from dw_windows_mcp.tools import ToolExecutionError, invoke_tool


def _make_users():
    admin = create_user("t_admin", "AdminPass123", Role.ADMIN)
    standard = create_user("t_standard", "StdPass123", Role.STANDARD)
    readonly = create_user("t_readonly", "ReadPass123", Role.READONLY)
    return admin, standard, readonly


def test_readonly_can_read_system_info():
    _, _, readonly = _make_users()
    result = invoke_tool(readonly, "system.info", {})
    assert "hostname" in result


def test_readonly_cannot_write_files(tmp_path):
    _, _, readonly = _make_users()
    try:
        invoke_tool(readonly, "fs.write_text", {"path": str(tmp_path / "x.txt"), "content": "hi"})
        assert False, "sollte PermissionError_ werfen"
    except PermissionError_:
        pass


def test_standard_cannot_use_power_tools():
    _, standard, _ = _make_users()
    try:
        invoke_tool(standard, "power.shutdown", {"delay_seconds": 5})
        assert False, "sollte PermissionError_ werfen"
    except PermissionError_:
        pass


def test_admin_power_shutdown_requires_confirm_token(block_subprocess_calls=None):
    admin, _, _ = _make_users()
    try:
        invoke_tool(admin, "power.shutdown", {"delay_seconds": 5})
        assert False, "sollte ConfirmationRequired werfen"
    except ConfirmationRequired as cr:
        token = cr.token

    # Zweiter Aufruf mit Token -> Ausführung (läuft über den gemockten subprocess.run)
    result = invoke_tool(admin, "power.shutdown", {"delay_seconds": 5, "confirm_token": token})
    assert result["action"] == "shutdown"


def test_confirm_token_is_single_use():
    admin, _, _ = _make_users()
    try:
        invoke_tool(admin, "power.restart", {"delay_seconds": 3})
    except ConfirmationRequired as cr:
        token = cr.token

    invoke_tool(admin, "power.restart", {"delay_seconds": 3, "confirm_token": token})

    # Derselbe Token darf nicht nochmal funktionieren.
    try:
        invoke_tool(admin, "power.restart", {"delay_seconds": 3, "confirm_token": token})
        assert False, "abgelaufener/benutzter Token sollte erneut ConfirmationRequired auslösen"
    except ConfirmationRequired:
        pass


def test_confirm_token_bound_to_exact_arguments():
    admin, _, _ = _make_users()
    try:
        invoke_tool(admin, "power.shutdown", {"delay_seconds": 5})
    except ConfirmationRequired as cr:
        token = cr.token

    # Token wurde für delay_seconds=5 ausgestellt — mit anderen Argumenten ungültig.
    try:
        invoke_tool(admin, "power.shutdown", {"delay_seconds": 999, "confirm_token": token})
        assert False, "Token darf nicht für andere Argumente gültig sein"
    except ConfirmationRequired:
        pass


def test_admin_skip_confirmation_bypasses_token():
    admin, _, _ = _make_users()
    set_skip_confirmation(admin.username, True)

    with get_session() as s:
        admin_fresh = s.scalar(select(type(admin)).where(type(admin).username == admin.username))

    result = invoke_tool(admin_fresh, "power.sleep", {})
    assert result["action"] == "sleep"


def test_non_admin_cannot_get_skip_confirmation():
    _, standard, _ = _make_users()
    try:
        set_skip_confirmation(standard.username, True)
        assert False, "Nicht-Admin darf skip_confirmation nicht aktivieren können"
    except ValueError:
        pass


def test_unknown_tool_raises():
    admin, _, _ = _make_users()
    try:
        invoke_tool(admin, "does.not.exist", {})
        assert False
    except ToolExecutionError:
        pass


def test_every_call_is_audit_logged():
    admin, standard, _ = _make_users()
    invoke_tool(admin, "system.info", {})
    try:
        invoke_tool(standard, "power.shutdown", {"delay_seconds": 1})
    except PermissionError_:
        pass

    with get_session() as s:
        rows = s.scalars(select(AuditLog)).all()
    outcomes = {r.tool_name: r.outcome for r in rows}
    assert outcomes["system.info"] == "success"
    assert outcomes["power.shutdown"] == "denied"
