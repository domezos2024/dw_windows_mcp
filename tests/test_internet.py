"""network.http_request / download_file / search_web — all against a fake
urlopen, so the test suite never makes a real internet request."""
from __future__ import annotations

import os

from dw_windows_mcp.auth.rbac import PermissionError_
from dw_windows_mcp.auth.users import create_user
from dw_windows_mcp.db import Role
from dw_windows_mcp.tools import invoke_tool


def test_http_request_get(fake_urlopen):
    admin = create_user("net_admin", "Pass1234", Role.ADMIN)
    fake_urlopen["response"] = type(fake_urlopen["response"])(
        b'{"ok": true}', status=200, headers={"Content-Type": "application/json"}
    )

    result = invoke_tool(admin, "network.http_request", {"url": "https://example.invalid/api"})
    assert result["status"] == 200
    assert '"ok": true' in result["body"]


def test_http_request_requires_network_write_permission(fake_urlopen):
    _, readonly = create_user("net_std", "Pass1234", Role.STANDARD), create_user(
        "net_ro", "Pass1234", Role.READONLY
    )
    try:
        invoke_tool(readonly, "network.http_request", {"url": "https://example.invalid"})
        assert False
    except PermissionError_:
        pass


def test_download_file_writes_into_sandbox(fake_urlopen):
    admin = create_user("dl_admin", "Pass1234", Role.ADMIN)
    fake_urlopen["response"] = type(fake_urlopen["response"])(b"hello binary content")

    sandbox = os.environ["DW_MCP_FS_ROOTS"]
    dest = os.path.join(sandbox, "downloaded.bin")
    result = invoke_tool(
        admin, "network.download_file", {"url": "https://example.invalid/file.bin", "destination": dest}
    )
    assert result["bytes_written"] == len(b"hello binary content")
    with open(dest, "rb") as f:
        assert f.read() == b"hello binary content"


def test_search_web_parses_ddg_lite_html(fake_urlopen):
    admin = create_user("search_admin", "Pass1234", Role.STANDARD)
    html = (
        b'<html><body><table>'
        b'<tr><td><a rel="nofollow" href="https://example.com/a">Example A</a></td></tr>'
        b'<tr><td class="result-snippet">Some snippet text</td></tr>'
        b'<tr><td><a rel="nofollow" href="https://example.com/b">Example B</a></td></tr>'
        b"</table></body></html>"
    )
    fake_urlopen["response"] = type(fake_urlopen["response"])(html)

    result = invoke_tool(admin, "network.search_web", {"query": "test query"})
    titles = [r["title"] for r in result["results"]]
    assert "Example A" in titles
    assert "Example B" in titles
