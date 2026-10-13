"""User CRUD and password hashing. Bootstraps an initial admin if none exists."""
from __future__ import annotations

import getpass
import hashlib
import hmac
import secrets
import sys

from sqlalchemy import select

from ..db import Role, User, get_session, init_db

_PBKDF2_ITERATIONS = 390_000


def hash_password(raw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(raw: str, hashed: str) -> bool:
    try:
        algo, iterations_s, salt_hex, digest_hex = hashed.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", raw.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations_s)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def get_user_by_username(username: str) -> User | None:
    with get_session() as s:
        return s.scalar(select(User).where(User.username == username))


def create_user(username: str, password: str, role: Role) -> User:
    with get_session() as s:
        existing = s.scalar(select(User).where(User.username == username))
        if existing:
            raise ValueError(f"User '{username}' existiert bereits")
        user = User(username=username, password_hash=hash_password(password), role=role)
        s.add(user)
        s.commit()
        s.refresh(user)
        return user


def authenticate(username: str, password: str) -> User | None:
    user = get_user_by_username(username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def set_skip_confirmation(username: str, skip: bool) -> None:
    """Admin-only toggle: lets an admin disable the confirm-token requirement for
    their own destructive-tool calls. No-op (forced False) for non-admin roles."""
    with get_session() as s:
        user = s.scalar(select(User).where(User.username == username))
        if not user:
            raise ValueError(f"User '{username}' nicht gefunden")
        if user.role != Role.ADMIN:
            raise ValueError("Confirm-Token-Opt-out ist nur für Admin-Rolle verfügbar")
        user.skip_confirmation = skip
        s.commit()


def any_admin_exists() -> bool:
    with get_session() as s:
        return s.scalar(select(User).where(User.role == Role.ADMIN)) is not None


def bootstrap_admin_interactive() -> None:
    """Called on first run (CLI) if no admin user exists yet."""
    init_db()
    if any_admin_exists():
        return
    print("Kein Admin-Account vorhanden. Erstelle initialen Admin-Benutzer.")
    username = input("Admin-Benutzername: ").strip() or "admin"
    password = getpass.getpass("Admin-Passwort: ")
    if not password:
        print("Passwort darf nicht leer sein. Abbruch.", file=sys.stderr)
        raise SystemExit(1)
    create_user(username, password, Role.ADMIN)
    print(f"Admin-Benutzer '{username}' angelegt.")
