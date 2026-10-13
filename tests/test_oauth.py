"""OAuth2 end-to-end tests against the real Starlette app (in-process, no
network socket bound) — password grant, refresh grant, and the full
authorization_code + PKCE flow a third-party app would use."""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from starlette.testclient import TestClient

from dw_windows_mcp.auth import oauth
from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.db import Role
from dw_windows_mcp.http_app import app


def _pkce_pair():
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_password_grant_and_refresh():
    create_user("oauth_user", "OauthPass123", Role.STANDARD)
    client_id, _client_secret = oauth.register_client("TestClient", ["http://localhost/cb"])

    client = TestClient(app)
    resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "password",
            "username": "oauth_user",
            "password": "OauthPass123",
            "client_id": client_id,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    access_token = body["access_token"]
    refresh_token = body["refresh_token"]

    user = oauth.resolve_access_token(access_token)
    assert user is not None
    assert user.username == "oauth_user"

    resp2 = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id},
    )
    assert resp2.status_code == 200
    assert resp2.json()["access_token"] != access_token


def test_password_grant_wrong_password_rejected():
    create_user("oauth_user2", "RightPass123", Role.STANDARD)
    client_id, _ = oauth.register_client("TestClient2", ["http://localhost/cb"])

    client = TestClient(app)
    resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "password",
            "username": "oauth_user2",
            "password": "WrongPass",
            "client_id": client_id,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_authorization_code_pkce_full_flow():
    create_user("oauth_user3", "AuthCodePass123", Role.ADMIN)
    redirect_uri = "http://localhost/cb"
    client_id, client_secret = oauth.register_client("ThirdPartyApp", [redirect_uri])
    verifier, challenge = _pkce_pair()

    client = TestClient(app)

    # 1) GET /oauth/authorize renders a login form
    authorize_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "xyz123",
    }
    get_resp = client.get("/oauth/authorize", params=authorize_params)
    assert get_resp.status_code == 200
    assert "Anmelden" in get_resp.text

    # 2) POST credentials -> redirect with ?code=...&state=...
    post_resp = client.post(
        "/oauth/authorize",
        data={**authorize_params, "username": "oauth_user3", "password": "AuthCodePass123"},
        follow_redirects=False,
    )
    assert post_resp.status_code == 302
    location = post_resp.headers["location"]
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    assert qs["state"] == ["xyz123"]
    code = qs["code"][0]
    assert code

    # 3) Exchange code (+ verifier) for tokens
    token_resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    assert token_resp.status_code == 200
    access_token = token_resp.json()["access_token"]

    user = oauth.resolve_access_token(access_token)
    assert user is not None
    assert user.username == "oauth_user3"

    # Code is single-use: replaying the exchange must fail.
    replay_resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    assert replay_resp.status_code == 400


def test_authorization_code_wrong_verifier_rejected():
    create_user("oauth_user4", "AuthCodePass123", Role.STANDARD)
    redirect_uri = "http://localhost/cb"
    client_id, client_secret = oauth.register_client("ThirdPartyApp2", [redirect_uri])
    _verifier, challenge = _pkce_pair()
    wrong_verifier, _ = _pkce_pair()

    client = TestClient(app)
    authorize_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "abc",
    }
    post_resp = client.post(
        "/oauth/authorize",
        data={**authorize_params, "username": "oauth_user4", "password": "AuthCodePass123"},
        follow_redirects=False,
    )
    code = parse_qs(urlparse(post_resp.headers["location"]).query)["code"][0]

    token_resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": wrong_verifier,
        },
    )
    assert token_resp.status_code == 400
    assert token_resp.json()["error"] == "invalid_grant"


def test_sse_requires_valid_bearer_token():
    create_user("oauth_user5", "SsePass123", Role.STANDARD)
    client_id, _ = oauth.register_client("SseClient", ["http://localhost/cb"])
    client = TestClient(app)

    resp = client.post(
        "/oauth/token",
        data={
            "grant_type": "password",
            "username": "oauth_user5",
            "password": "SsePass123",
            "client_id": client_id,
        },
    )
    token = resp.json()["access_token"]

    no_auth = client.get("/sse")
    assert no_auth.status_code == 401

    bad_auth = client.get("/sse", headers={"Authorization": "Bearer not-a-real-token"})
    assert bad_auth.status_code == 401

    user = oauth.resolve_access_token(token)
    assert user is not None and user.username == "oauth_user5"
