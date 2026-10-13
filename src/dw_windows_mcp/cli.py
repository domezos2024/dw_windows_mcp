"""Command-line entry point: `dw-windows-mcp <command>`."""
from __future__ import annotations

import argparse
import json

from .auth import oauth
from .auth.users import (
    bootstrap_admin_interactive,
    create_user,
    set_skip_confirmation,
)
from .db import AuditLog, Role, get_session, init_db


def cmd_init(args: argparse.Namespace) -> None:
    bootstrap_admin_interactive()


def cmd_user_add(args: argparse.Namespace) -> None:
    init_db()
    user = create_user(args.username, args.password, Role(args.role))
    print(f"Benutzer '{user.username}' angelegt mit Rolle '{user.role.value}'.")


def cmd_user_list(args: argparse.Namespace) -> None:
    init_db()
    from sqlalchemy import select

    from .db import User

    with get_session() as s:
        for u in s.scalars(select(User)):
            print(f"{u.username}\trolle={u.role.value}\taktiv={u.is_active}\tskip_confirm={u.skip_confirmation}")


def cmd_user_skip_confirm(args: argparse.Namespace) -> None:
    init_db()
    set_skip_confirmation(args.username, args.enable)
    state = "aktiviert (Confirm-Token wird übersprungen)" if args.enable else "deaktiviert"
    print(f"skip_confirmation für '{args.username}': {state}")


def cmd_oauth_register_client(args: argparse.Namespace) -> None:
    init_db()
    client_id, client_secret = oauth.register_client(args.name, args.redirect_uri)
    print("OAuth-Client angelegt. Secret wird NUR JETZT angezeigt — sicher speichern:")
    print(json.dumps({"client_id": client_id, "client_secret": client_secret}, indent=2))


def cmd_audit_tail(args: argparse.Namespace) -> None:
    init_db()
    from sqlalchemy import select

    with get_session() as s:
        rows = s.scalars(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(args.n)
        ).all()
    for row in reversed(rows):
        print(f"{row.timestamp}\t{row.username}\t{row.tool_name}\t{row.outcome}\t{row.detail}")


def cmd_run_stdio(args: argparse.Namespace) -> None:
    from .server import main as stdio_main

    stdio_main()


def cmd_run_http(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("dw_windows_mcp.http_app:app", host=args.host, port=args.port, log_level="info")


def cmd_install_autostart(args: argparse.Namespace) -> None:
    from . import autostart

    autostart.install(host=args.host, port=args.port)
    print(f"Autostart-Task '{autostart.TASK_NAME}' angelegt (Start bei Login, Port {args.port}).")


def cmd_uninstall_autostart(args: argparse.Namespace) -> None:
    from . import autostart

    autostart.uninstall()
    print(f"Autostart-Task '{autostart.TASK_NAME}' entfernt.")


def cmd_autostart_status(args: argparse.Namespace) -> None:
    from . import autostart

    print(autostart.status())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dw-windows-mcp")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Legt den initialen Admin-Benutzer an (interaktiv)").set_defaults(func=cmd_init)

    p_user_add = sub.add_parser("user-add", help="Legt einen neuen Benutzer an")
    p_user_add.add_argument("username")
    p_user_add.add_argument("password")
    p_user_add.add_argument("--role", choices=[r.value for r in Role], default=Role.READONLY.value)
    p_user_add.set_defaults(func=cmd_user_add)

    sub.add_parser("user-list", help="Listet alle Benutzer").set_defaults(func=cmd_user_list)

    p_skip = sub.add_parser(
        "user-skip-confirm", help="Admin-only: Confirm-Token-Pflicht für diesen Admin an/ausschalten"
    )
    p_skip.add_argument("username")
    p_skip.add_argument("--enable", action="store_true", help="Confirm-Token-Pflicht überspringen")
    p_skip.add_argument("--disable", dest="enable", action="store_false", help="Confirm-Token-Pflicht erzwingen")
    p_skip.set_defaults(enable=True, func=cmd_user_skip_confirm)

    p_client = sub.add_parser("oauth-register-client", help="Registriert einen OAuth2-Client")
    p_client.add_argument("name")
    p_client.add_argument("--redirect-uri", action="append", dest="redirect_uri", default=[])
    p_client.set_defaults(func=cmd_oauth_register_client)

    p_audit = sub.add_parser("audit-tail", help="Zeigt die letzten Audit-Log-Einträge")
    p_audit.add_argument("-n", type=int, default=50)
    p_audit.set_defaults(func=cmd_audit_tail)

    sub.add_parser("run-stdio", help="Startet den MCP-Server über stdio (für lokale KI-Clients)").set_defaults(
        func=cmd_run_stdio
    )

    p_http = sub.add_parser("run-http", help="Startet den MCP-Server über HTTP/SSE + OAuth2")
    p_http.add_argument("--host", default="0.0.0.0")
    p_http.add_argument("--port", type=int, default=8765)
    p_http.set_defaults(func=cmd_run_http)

    p_install_auto = sub.add_parser(
        "install-autostart", help="Registriert den HTTP-Server als Windows-Autostart-Task (Login-Trigger)"
    )
    p_install_auto.add_argument("--host", default="0.0.0.0")
    p_install_auto.add_argument("--port", type=int, default=8765)
    p_install_auto.set_defaults(func=cmd_install_autostart)

    sub.add_parser("uninstall-autostart", help="Entfernt den Autostart-Task").set_defaults(
        func=cmd_uninstall_autostart
    )
    sub.add_parser("autostart-status", help="Zeigt den Status des Autostart-Tasks").set_defaults(
        func=cmd_autostart_status
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
