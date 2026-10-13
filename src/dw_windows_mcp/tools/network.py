"""Network diagnostics (read-only) plus internet access tools (http_request,
download_file, search_web — classified NETWORK_WRITE since they reach out to
arbitrary internet endpoints and/or write files)."""
from __future__ import annotations

import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

import psutil

from ..auth.rbac import ToolCategory
from ..db import User
from . import tool
from .filesystem import _check_allowed

_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200 MB safety cap
_MAX_BODY_CHARS = 20_000  # truncate http_request response bodies in the tool result


@tool(
    name="network.info",
    category=ToolCategory.NETWORK_READ,
    description="Netzwerk-Interfaces mit IP-Adressen.",
)
def network_info(user: User) -> dict:
    interfaces = {}
    for name, addrs in psutil.net_if_addrs().items():
        interfaces[name] = [
            {"family": str(a.family), "address": a.address} for a in addrs
        ]
    return {"hostname": socket.gethostname(), "interfaces": interfaces}


@tool(
    name="network.connections",
    category=ToolCategory.NETWORK_READ,
    description="Aktive Netzwerkverbindungen (lokale/entfernte Adresse, Status, PID).",
)
def connections(user: User) -> list[dict]:
    result = []
    for c in psutil.net_connections(kind="inet"):
        result.append(
            {
                "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None,
                "status": c.status,
                "pid": c.pid,
            }
        )
    return result


@tool(
    name="network.ping",
    category=ToolCategory.NETWORK_READ,
    description="Pingt einen Host an (4 Pakete).",
)
def ping(user: User, host: str) -> dict:
    proc = subprocess.run(["ping", "-n", "4", host], check=False, capture_output=True, text=True, timeout=20)
    return {"host": host, "output": proc.stdout, "reachable": proc.returncode == 0}


@tool(
    name="network.http_request",
    category=ToolCategory.NETWORK_WRITE,
    description="Führt eine beliebige HTTP-Anfrage aus (GET/POST/PUT/DELETE/PATCH) gegen eine URL.",
)
def http_request(
    user: User,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout_seconds: int = 30,
) -> dict:
    req = urllib.request.Request(
        url, data=body.encode("utf-8") if body else None, headers=headers or {}, method=method.upper()
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read()
            status = resp.status
            resp_headers = dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code
        resp_headers = dict(e.headers.items()) if e.headers else {}

    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > _MAX_BODY_CHARS
    return {
        "status": status,
        "headers": resp_headers,
        "body": text[:_MAX_BODY_CHARS],
        "truncated": truncated,
    }


@tool(
    name="network.download_file",
    category=ToolCategory.NETWORK_WRITE,
    description="Lädt eine Datei von einer URL herunter und speichert sie im Dateisystem (Sandbox beachtet).",
)
def download_file(user: User, url: str, destination: str, timeout_seconds: int = 120) -> dict:
    dest = _check_allowed(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": "dw-windows-mcp/0.1"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        written = 0
        with open(dest, "wb") as f:
            while chunk := resp.read(65536):
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"Download überschreitet das Limit von {_MAX_DOWNLOAD_BYTES} Bytes.")
                f.write(chunk)
    return {"url": url, "destination": str(dest), "bytes_written": written}


class _DdgLiteResultParser(HTMLParser):
    """Minimal best-effort parser for DuckDuckGo's lite HTML results page —
    no API key needed, but fragile against markup changes by design."""

    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._in_result_link = False
        self._current_href = ""
        self._current_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href.startswith("http") and "duckduckgo.com" not in href:
                self._in_result_link = True
                self._current_href = href
                self._current_text = ""

    def handle_data(self, data):
        if self._in_result_link:
            self._current_text += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in_result_link:
            self._in_result_link = False
            title = self._current_text.strip()
            if title:
                self.results.append({"title": title, "url": self._current_href})


@tool(
    name="network.search_web",
    category=ToolCategory.NETWORK_READ,
    description="Durchsucht das Web (DuckDuckGo, ohne API-Key, best-effort HTML-Parsing).",
)
def search_web(user: User, query: str, max_results: int = 10) -> dict:
    url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "dw-windows-mcp/0.1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html_text = resp.read().decode("utf-8", errors="replace")

    parser = _DdgLiteResultParser()
    parser.feed(html_text)
    return {"query": query, "results": parser.results[:max_results]}
