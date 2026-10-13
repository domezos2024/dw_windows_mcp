# dw-windows-mcp

[🇩🇪 Deutsch](README.md) | 🇬🇧 English

Full installation guide: [docs/INSTALL.de.md](docs/INSTALL.de.md) · [docs/INSTALL.en.md](docs/INSTALL.en.md)

MCP server exposing full control over a Windows 11 system and its internet
connection as MCP tools — usable locally (stdio, e.g. from Claude
Desktop/Code) and remotely (HTTP/SSE with OAuth2, e.g. from a phone).

## Feature overview

| Category | Tools |
| --- | --- |
| System | `system.info`, `system.disks` |
| Filesystem | `fs.list_dir`, `fs.read_text`, `fs.write_text`, `fs.mkdir`, `fs.copy`, `fs.move`, `fs.delete`* |
| Processes | `process.list`, `process.start`, `process.kill`* |
| Registry | `registry.read_value`, `registry.list_values`, `registry.write_value`*, `registry.delete_value`* |
| Services | `services.list`, `services.start`, `services.stop`*, `services.restart`* |
| Power | `power.lock`, `power.shutdown`*, `power.restart`*, `power.sleep`*, `power.cancel_shutdown` |
| Network/Internet | `network.info`, `network.connections`, `network.ping`, `network.http_request`†, `network.download_file`†, `network.search_web` |
| Installation | `install.search`, `install.install`*, `install.uninstall`*, `install.list_installed` |
| Clipboard | `clipboard.get`, `clipboard.set` |
| GUI automation | `gui.screenshot`, `gui.mouse_move`, `gui.mouse_click`, `gui.type_text`, `gui.key_press` |
| Text-to-speech | `tts.speak`, `tts.text_to_wav`, `tts.text_to_mp3` (needs ffmpeg) |
| Documents | `documents.create_markdown`, `documents.create_docx`, `documents.create_xlsx`, `documents.create_pptx` |
| Memory (key/value) | `memory.set`, `memory.get`, `memory.list`, `memory.delete` |
| Filesystem (extra) | `fs.batch_rename` (regex, dry-run safe)*, `fs.compare_files` |

\* destructive — always requires a confirm-token (see below), unless the
calling admin has `skip_confirmation` enabled. `fs.batch_rename` only
requires it when actually executing (`dry_run=false`) — with the default
`dry_run=true` it just previews the planned renames without changing
anything.

† requires the `standard` or `admin` role (category `network_write` —
arbitrary outbound HTTP requests/downloads are treated as being just as
far-reaching as installing software).

## Security model

- **Roles** (coarse): `admin` (everything), `standard` (no registry writes,
  no power management, no service stop/restart), `readonly` (read-only
  tools only).
- **Confirm-token requirement:** every destructive tool call must happen
  twice:
  1. Call without `confirm_token` → the response contains a `confirm_token`
     plus a plain-text description of the action.
  2. Repeat the call with the same arguments plus `confirm_token` →
     execution.
  Tokens expire after 120s (`DW_MCP_CONFIRM_TTL`).
- **Admin opt-out:** an admin can disable the confirm requirement for
  themselves: `dw-windows-mcp user-skip-confirm <username> --enable`.
  Non-admin roles cannot do this.
- **Audit log:** every tool call (successful, denied, or errored) is logged
  to SQLite: `dw-windows-mcp audit-tail`.
- **Filesystem sandbox (optional):** `DW_MCP_FS_ROOTS` (paths separated by
  `;`) restricts all `fs.*` tools to those root directories. Empty = no
  restriction.

## Installation

```bash
pip install -e .
dw-windows-mcp init
```

Creates the SQLite database under `%USERPROFILE%\.dw_windows_mcp\` and walks
you interactively through creating the first admin user.

Additional users:

```bash
dw-windows-mcp user-add bob somesecretpass --role standard
dw-windows-mcp user-list
```

## Local usage (stdio)

For Claude Desktop (`claude_desktop_config.json`) or any other AI client
with MCP stdio support:

```json
{
  "mcpServers": {
    "dw-windows-mcp": {
      "command": "dw-windows-mcp",
      "args": ["run-stdio"],
      "env": { "DW_MCP_LOCAL_USER": "admin" }
    }
  }
}
```

Without `DW_MCP_LOCAL_USER`, the first admin found is used automatically.

## Remote usage (HTTP/SSE + OAuth2)

```bash
dw-windows-mcp run-http --host 0.0.0.0 --port 8765
```

The server only ever binds to `host:port`. How it's made reachable from the
outside (public IP:port, port forwarding, DynDNS, reverse proxy, a tunnel
like ngrok/Cloudflare Tunnel) is decided and configured by the user — that's
intentionally not part of this server.

### Register an OAuth2 client

```bash
dw-windows-mcp oauth-register-client "My Phone" --redirect-uri "myapp://callback"
```

Prints `client_id` + `client_secret` (shown only once).

### Get a token — simple way (password grant, first-party clients)

```bash
curl -X POST http://HOST:8765/oauth/token \
  -d grant_type=password -d username=bob -d password=somesecretpass \
  -d client_id=<client_id>
```

### Get a token — authorization-code flow with PKCE (third-party apps)

1. Open in a browser: `GET /oauth/authorize?client_id=...&redirect_uri=...&code_challenge=...&code_challenge_method=S256&state=...`
2. User signs in → redirect with `?code=...`
3. `POST /oauth/token` with `grant_type=authorization_code`, `code`,
   `client_id`, `client_secret`, `redirect_uri`, `code_verifier`

The returned `access_token` is sent as `Authorization: Bearer <token>` when
connecting to `GET /sse`.

## Autostart (optional)

```bash
dw-windows-mcp install-autostart --host 0.0.0.0 --port 8765
dw-windows-mcp autostart-status
dw-windows-mcp uninstall-autostart
```

Creates a Windows Task Scheduler task that starts `dw-windows-mcp run-http`
when the current user logs in. Details: [docs/INSTALL.en.md](docs/INSTALL.en.md#6-set-up-autostart-optional).

## CLI overview

```
dw-windows-mcp init
dw-windows-mcp user-add <username> <password> [--role admin|standard|readonly]
dw-windows-mcp user-list
dw-windows-mcp user-skip-confirm <username> [--enable|--disable]
dw-windows-mcp oauth-register-client <name> [--redirect-uri ...]
dw-windows-mcp audit-tail [-n 50]
dw-windows-mcp run-stdio
dw-windows-mcp run-http [--host 0.0.0.0] [--port 8765]
dw-windows-mcp install-autostart [--host 0.0.0.0] [--port 8765]
dw-windows-mcp uninstall-autostart
dw-windows-mcp autostart-status
```

## License

MIT — see [LICENSE](LICENSE).
