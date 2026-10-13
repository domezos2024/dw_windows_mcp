# Installation Guide (English)

## Prerequisites

- Windows 10/11
- Python 3.11 or newer (recommended: 3.11–3.13; see the 3.14 note below)
- Admin rights for services/registry/power-management tools (not required
  for installation itself)

> **Note on Python 3.14:** Some dependencies (`pywin32`, `wmi`, `pyautogui`)
> may not yet ship prebuilt wheels for Python 3.14 at the time of this
> release. If installation fails, use Python 3.11–3.13.

> **Optional, for `tts.text_to_mp3`:** `ffmpeg` on PATH. Without ffmpeg,
> `tts.text_to_wav` still works fully (WAV instead of MP3).

## 1. Clone the repository

```powershell
git clone https://github.com/domezos2024/dw_windows_mcp.git
cd dw_windows_mcp
```

## 2. Virtual environment + install

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## 3. Create the first admin user

```powershell
dw-windows-mcp init
```

Interactively prompts for a username + password and creates the SQLite
database under `%USERPROFILE%\.dw_windows_mcp\`.

Additional users with other roles:

```powershell
dw-windows-mcp user-add bob SomeSecretPass123 --role standard
```

Roles: `admin` (full access), `standard` (no registry writes, no power
management, no service stop/restart), `readonly` (read-only tools only).

## 4. Local usage (stdio) — e.g. Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dw-windows-mcp": {
      "command": "C:\\path\\to\\dw_windows_mcp\\.venv\\Scripts\\dw-windows-mcp.exe",
      "args": ["run-stdio"],
      "env": { "DW_MCP_LOCAL_USER": "admin" }
    }
  }
}
```

## 5. Remote usage (HTTP/SSE + OAuth2) — e.g. from a phone

```powershell
dw-windows-mcp run-http --host 0.0.0.0 --port 8765
```

The server only ever binds locally to `host:port`. Making it reachable from
outside (port forwarding, DynDNS, a tunnel like ngrok/Cloudflare Tunnel) is
up to you — that's intentionally not part of this server.

Registering an OAuth2 client and obtaining a token: see
[README.md](../README.md#remote-nutzung-httpsse--oauth2).

## 6. Set up autostart (optional)

To have the HTTP/SSE server start automatically on Windows login:

```powershell
dw-windows-mcp install-autostart --host 0.0.0.0 --port 8765
```

Creates a Windows Task Scheduler task (`dw-windows-mcp-autostart`) that runs
`dw-windows-mcp run-http` when the current user logs in.

To remove it:

```powershell
dw-windows-mcp uninstall-autostart
```

Check status:

```powershell
dw-windows-mcp autostart-status
```

## Uninstalling

```powershell
dw-windows-mcp uninstall-autostart
pip uninstall dw-windows-mcp
rmdir /s "%USERPROFILE%\.dw_windows_mcp"
```

## Troubleshooting

- **`winreg`/`wmi`/`win32clipboard` import errors:** the server isn't
  running on Windows, or the `pywin32` post-install script wasn't run:
  `python .venv\Scripts\pywin32_postinstall.py -install`
- **Port already in use:** pick a different port with `--port`.
- **`winget` errors on `install.*` tools:** App Installer (winget) must be
  installed (included by default on Windows 11).
