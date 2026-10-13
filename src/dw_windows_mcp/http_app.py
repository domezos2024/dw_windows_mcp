"""HTTP/SSE transport + OAuth2 endpoints, for remote access (LAN or internet,
behind whatever tunnel/DynDNS/reverse-proxy the user sets up themselves — this
process only ever binds to a local host:port)."""
from __future__ import annotations

import contextlib
import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route

from mcp.server.sse import SseServerTransport

from .auth import oauth
from .auth.users import authenticate
from .db import User, init_db
from .mcp_core import current_client_addr, current_user, server

logger = logging.getLogger("dw_windows_mcp.http")

sse_transport = SseServerTransport("/messages/")


def _client_addr(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def handle_sse(request: Request) -> Response:
    token = _bearer_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized", "detail": "Bearer-Token fehlt"}, status_code=401)
    user = oauth.resolve_access_token(token)
    if not user or not user.is_active:
        return JSONResponse({"error": "unauthorized", "detail": "Token ungültig oder abgelaufen"}, status_code=401)

    current_user.set(user)
    current_client_addr.set(_client_addr(request))

    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read, write):
        await server.run(read, write, server.create_initialization_options())
    return Response()


# ---- OAuth2 endpoints -------------------------------------------------------


async def oauth_token(request: Request) -> JSONResponse:
    form = await request.form()
    grant_type = form.get("grant_type")
    client_id = form.get("client_id", "")

    try:
        if grant_type == "password":
            result = oauth.grant_password(
                form.get("username", ""), form.get("password", ""), client_id, form.get("scope", "")
            )
        elif grant_type == "refresh_token":
            result = oauth.grant_refresh_token(form.get("refresh_token", ""), client_id)
        elif grant_type == "authorization_code":
            result = oauth.grant_authorization_code(
                code=form.get("code", ""),
                client_id=client_id,
                client_secret=form.get("client_secret", ""),
                redirect_uri=form.get("redirect_uri", ""),
                code_verifier=form.get("code_verifier", ""),
            )
        else:
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    except oauth.OAuthError as e:
        return JSONResponse({"error": e.error, "error_description": e.description}, status_code=400)

    return JSONResponse(result)


_AUTHORIZE_FORM = """<!doctype html><html><body>
<h3>dw-windows-mcp — Anmelden</h3>
<form method="post">
  <input type="hidden" name="client_id" value="{client_id}">
  <input type="hidden" name="redirect_uri" value="{redirect_uri}">
  <input type="hidden" name="code_challenge" value="{code_challenge}">
  <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
  <input type="hidden" name="state" value="{state}">
  <input type="hidden" name="scope" value="{scope}">
  <p><input name="username" placeholder="Benutzername"></p>
  <p><input name="password" type="password" placeholder="Passwort"></p>
  <button type="submit">Anmelden &amp; autorisieren</button>
</form>
</body></html>"""


async def oauth_authorize(request: Request) -> Response:
    q = request.query_params
    ctx = dict(
        client_id=q.get("client_id", ""),
        redirect_uri=q.get("redirect_uri", ""),
        code_challenge=q.get("code_challenge", ""),
        code_challenge_method=q.get("code_challenge_method", "S256"),
        state=q.get("state", ""),
        scope=q.get("scope", ""),
    )

    if request.method == "GET":
        return HTMLResponse(_AUTHORIZE_FORM.format(**ctx))

    form = await request.form()
    user = authenticate(form.get("username", ""), form.get("password", ""))
    if not user:
        return HTMLResponse(_AUTHORIZE_FORM.format(**ctx) + "<p>Login fehlgeschlagen.</p>", status_code=401)

    try:
        code = oauth.start_authorization_code(
            client_id=form.get("client_id", ""),
            redirect_uri=form.get("redirect_uri", ""),
            code_challenge=form.get("code_challenge", ""),
            code_challenge_method=form.get("code_challenge_method", "S256"),
            user=user,
            scope=form.get("scope", ""),
        )
    except oauth.OAuthError as e:
        return JSONResponse({"error": e.error, "error_description": e.description}, status_code=400)

    redirect_uri = form.get("redirect_uri", "")
    state = form.get("state", "")
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=302)


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "dw-windows-mcp"})


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    init_db()
    yield


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/sse", handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse_transport.handle_post_message),
        Route("/oauth/token", oauth_token, methods=["POST"]),
        Route("/oauth/authorize", oauth_authorize, methods=["GET", "POST"]),
    ],
    lifespan=lifespan,
)
