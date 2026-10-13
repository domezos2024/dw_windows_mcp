"""Minimal, dependency-light OAuth2 server (RFC 6749 subset):

- grant_type=password        (first-party: username+password -> access+refresh token)
- grant_type=refresh_token    (rotate access token)
- grant_type=authorization_code + PKCE (third-party clients, browser redirect flow)

Tokens and auth codes are opaque random strings stored in SQLite (OAuthToken table).
Not a full RFC implementation (no scopes negotiation beyond a free-text string), but
enough for a self-hosted single-user-base server where the admin controls clients.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy import select

from ..config import settings
from ..db import OAuthClient, OAuthToken, User, get_session, utcnow
from .users import authenticate, hash_password, verify_password

# In-memory store for short-lived authorization codes (PKCE). Fine for a single
# process instance; codes live at most a couple of minutes.
_auth_codes: dict[str, AuthCode] = {}


@dataclass
class AuthCode:
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    expires_at: dt.datetime
    scope: str = ""


class OAuthError(Exception):
    def __init__(self, error: str, description: str = ""):
        self.error = error
        self.description = description
        super().__init__(f"{error}: {description}")


def register_client(client_name: str, redirect_uris: list[str]) -> tuple[str, str]:
    """Creates a new OAuth client. Returns (client_id, client_secret) — the secret
    is only ever returned here, never stored in plaintext."""
    client_id = secrets.token_urlsafe(16)
    client_secret = secrets.token_urlsafe(32)
    with get_session() as s:
        s.add(
            OAuthClient(
                client_id=client_id,
                client_secret_hash=hash_password(client_secret),
                client_name=client_name,
                redirect_uris=";".join(redirect_uris),
            )
        )
        s.commit()
    return client_id, client_secret


def _get_client(client_id: str) -> OAuthClient | None:
    with get_session() as s:
        return s.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))


def verify_client_secret(client_id: str, client_secret: str) -> bool:
    client = _get_client(client_id)
    if not client:
        return False
    return verify_password(client_secret, client.client_secret_hash)


def start_authorization_code(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    user: User,
    scope: str = "",
) -> str:
    client = _get_client(client_id)
    if not client:
        raise OAuthError("invalid_client", "Unbekannte client_id")
    allowed_redirects = [u for u in client.redirect_uris.split(";") if u]
    if redirect_uri not in allowed_redirects:
        raise OAuthError("invalid_grant", "redirect_uri nicht registriert")
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = AuthCode(
        code=code,
        client_id=client_id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method or "plain",
        expires_at=utcnow() + dt.timedelta(minutes=5),
        scope=scope,
    )
    return code


def _pkce_matches(verifier: str, challenge: str, method: str) -> bool:
    if method.upper() == "S256":
        digest = hashlib.sha256(verifier.encode()).digest()
        import base64

        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return computed == challenge
    return verifier == challenge  # "plain"


def _issue_token(user: User, client_id: str, scope: str = "") -> dict:
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    now = utcnow()
    with get_session() as s:
        s.add(
            OAuthToken(
                user_id=user.id,
                client_id=client_id,
                access_token=access_token,
                refresh_token=refresh_token,
                scope=scope,
                expires_at=now + dt.timedelta(seconds=settings.access_token_ttl_seconds),
            )
        )
        s.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.access_token_ttl_seconds,
        "scope": scope,
    }


def grant_password(username: str, password: str, client_id: str, scope: str = "") -> dict:
    user = authenticate(username, password)
    if not user:
        raise OAuthError("invalid_grant", "Benutzername oder Passwort falsch")
    return _issue_token(user, client_id, scope)


def grant_authorization_code(
    code: str, client_id: str, client_secret: str, redirect_uri: str, code_verifier: str
) -> dict:
    if not verify_client_secret(client_id, client_secret):
        raise OAuthError("invalid_client", "Client-Authentifizierung fehlgeschlagen")
    entry = _auth_codes.get(code)
    if not entry or entry.client_id != client_id:
        raise OAuthError("invalid_grant", "Unbekannter oder abgelaufener Code")
    del _auth_codes[code]
    if utcnow() > entry.expires_at:
        raise OAuthError("invalid_grant", "Code abgelaufen")
    if entry.redirect_uri != redirect_uri:
        raise OAuthError("invalid_grant", "redirect_uri stimmt nicht")
    if not _pkce_matches(code_verifier, entry.code_challenge, entry.code_challenge_method):
        raise OAuthError("invalid_grant", "PKCE-Verifikation fehlgeschlagen")
    with get_session() as s:
        user = s.get(User, entry.user_id)
    if not user:
        raise OAuthError("invalid_grant", "Benutzer nicht gefunden")
    return _issue_token(user, client_id, entry.scope)


def grant_refresh_token(refresh_token: str, client_id: str) -> dict:
    with get_session() as s:
        tok = s.scalar(
            select(OAuthToken).where(
                OAuthToken.refresh_token == refresh_token,
                OAuthToken.client_id == client_id,
                OAuthToken.revoked == False,
            )
        )
        if not tok:
            raise OAuthError("invalid_grant", "Refresh-Token ungültig")
        user = s.get(User, tok.user_id)
        tok.revoked = True
        s.commit()
    return _issue_token(user, client_id, tok.scope)


def resolve_access_token(access_token: str) -> User | None:
    """Returns the authenticated user for a bearer access token, or None if
    missing/expired/revoked."""
    with get_session() as s:
        tok = s.scalar(select(OAuthToken).where(OAuthToken.access_token == access_token))
        if not tok or tok.revoked:
            return None
        if utcnow() > tok.expires_at:
            return None
        return s.get(User, tok.user_id)


def revoke_token(access_token: str) -> None:
    with get_session() as s:
        tok = s.scalar(select(OAuthToken).where(OAuthToken.access_token == access_token))
        if tok:
            tok.revoked = True
            s.commit()
