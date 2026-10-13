# dw-windows-mcp

🇩🇪 Deutsch | [🇬🇧 English](README.en.md)

Ausführliche Installationsanleitung: [docs/INSTALL.de.md](docs/INSTALL.de.md) · [docs/INSTALL.en.md](docs/INSTALL.en.md)

MCP-Server, der die volle Kontrolle über ein Windows-11-System und dessen
Internetverbindung als MCP-Tools bereitstellt — nutzbar lokal (stdio, z.B. aus
Claude Desktop/Code) und remote (HTTP/SSE mit OAuth2, z.B. vom Smartphone).

## Funktionsumfang

| Kategorie | Tools |
| --- | --- |
| System | `system.info`, `system.disks` |
| Dateisystem | `fs.list_dir`, `fs.read_text`, `fs.write_text`, `fs.mkdir`, `fs.copy`, `fs.move`, `fs.delete`* |
| Prozesse | `process.list`, `process.start`, `process.kill`* |
| Registry | `registry.read_value`, `registry.list_values`, `registry.write_value`*, `registry.delete_value`* |
| Dienste | `services.list`, `services.start`, `services.stop`*, `services.restart`* |
| Power | `power.lock`, `power.shutdown`*, `power.restart`*, `power.sleep`*, `power.cancel_shutdown` |
| Netzwerk | `network.info`, `network.connections`, `network.ping` |
| Installation | `install.search`, `install.install`*, `install.uninstall`*, `install.list_installed` |
| Zwischenablage | `clipboard.get`, `clipboard.set` |
| GUI-Automation | `gui.screenshot`, `gui.mouse_click`, `gui.type_text`, `gui.key_press` |

\* destruktiv — erfordert zwingend einen Confirm-Token (siehe unten), außer der
aufrufende Admin hat `skip_confirmation` aktiviert.

## Sicherheitsmodell

- **Rollen** (grob): `admin` (alles), `standard` (keine Registry-Writes, kein
  Power-Management, kein Service-Stop/Restart), `readonly` (nur lesende Tools).
- **Confirm-Token-Pflicht:** Jeder destruktive Tool-Call muss zweimal erfolgen:
  1. Aufruf ohne `confirm_token` → Antwort enthält `confirm_token` + Klartext-
     Beschreibung der Aktion.
  2. Erneuter Aufruf mit denselben Argumenten + `confirm_token` → Ausführung.
  Tokens laufen nach 120s ab (`DW_MCP_CONFIRM_TTL`).
- **Admin-Opt-out:** Ein Admin kann für sich selbst die Confirm-Pflicht
  deaktivieren: `dw-windows-mcp user-skip-confirm <username> --enable`.
  Nicht-Admin-Rollen können das nicht.
- **Audit-Log:** Jeder Tool-Call (egal ob erfolgreich, abgelehnt oder mit
  Fehler) wird in SQLite protokolliert: `dw-windows-mcp audit-tail`.
- **Dateisystem-Sandbox (optional):** `DW_MCP_FS_ROOTS` (mit `;` getrennte
  Pfade) beschränkt alle `fs.*`-Tools auf diese Wurzelverzeichnisse. Leer =
  kein Limit.

## Installation

```bash
pip install -e .
dw-windows-mcp init
```

Legt die SQLite-Datenbank unter `%USERPROFILE%\.dw_windows_mcp\` an und führt
interaktiv durch die Erstellung des ersten Admin-Benutzers.

Weitere Benutzer:

```bash
dw-windows-mcp user-add bob geheimesPasswort --role standard
dw-windows-mcp user-list
```

## Lokale Nutzung (stdio)

Für Claude Desktop (`claude_desktop_config.json`) oder jede andere KI mit
MCP-stdio-Unterstützung:

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

Ohne `DW_MCP_LOCAL_USER` wird automatisch der erste gefundene Admin verwendet.

## Remote-Nutzung (HTTP/SSE + OAuth2)

```bash
dw-windows-mcp run-http --host 0.0.0.0 --port 8765
```

Der Server lauscht nur auf `host:port`. Wie er von außen erreichbar gemacht
wird (öffentliche IP:Port, Port-Forwarding, DynDNS, Reverse-Proxy, Tunnel wie
ngrok/Cloudflare Tunnel) entscheidet und konfiguriert der Nutzer selbst — das
ist bewusst nicht Teil dieses Servers.

### OAuth2-Client registrieren

```bash
dw-windows-mcp oauth-register-client "Mein Handy" --redirect-uri "myapp://callback"
```

Gibt `client_id` + `client_secret` aus (nur einmal sichtbar).

### Token holen — einfacher Weg (Password Grant, eigene Clients)

```bash
curl -X POST http://HOST:8765/oauth/token \
  -d grant_type=password -d username=bob -d password=geheimesPasswort \
  -d client_id=<client_id>
```

### Token holen — Authorization-Code-Flow mit PKCE (Drittanbieter-Apps)

1. Browser öffnen: `GET /oauth/authorize?client_id=...&redirect_uri=...&code_challenge=...&code_challenge_method=S256&state=...`
2. Nutzer meldet sich an → Redirect mit `?code=...`
3. `POST /oauth/token` mit `grant_type=authorization_code`, `code`, `client_id`,
   `client_secret`, `redirect_uri`, `code_verifier`

Der zurückgegebene `access_token` wird als `Authorization: Bearer <token>` beim
Verbindungsaufbau zu `GET /sse` gesendet.

## Autostart (optional)

```bash
dw-windows-mcp install-autostart --host 0.0.0.0 --port 8765
dw-windows-mcp autostart-status
dw-windows-mcp uninstall-autostart
```

Legt eine Windows-Aufgabenplanung-Task an, die `dw-windows-mcp run-http` bei
der Anmeldung des aktuellen Benutzers startet. Details: [docs/INSTALL.de.md](docs/INSTALL.de.md#6-autostart-einrichten-optional).

## CLI-Übersicht

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

## Lizenz

MIT — siehe [LICENSE](LICENSE).
