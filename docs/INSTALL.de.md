# Installationsanleitung (Deutsch)

## Voraussetzungen

- Windows 10/11
- Python 3.11 oder neuer (empfohlen: 3.11–3.13; siehe Hinweis zu 3.14 unten)
- Admin-Rechte für Dienste/Registry/Power-Management-Tools (nicht für die
  Installation selbst nötig)

> **Hinweis zu Python 3.14:** Einige Abhängigkeiten (`pywin32`, `wmi`,
> `pyautogui`) haben zum Zeitpunkt dieses Releases unter Python 3.14 teils
> noch keine fertigen Wheels. Falls die Installation fehlschlägt, nutze
> Python 3.11–3.13.

## 1. Repository holen

```powershell
git clone https://github.com/domezos2024/dw_windows_mcp.git
cd dw_windows_mcp
```

## 2. Virtuelle Umgebung + Installation

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

## 3. Ersten Admin-Benutzer anlegen

```powershell
dw-windows-mcp init
```

Fragt interaktiv nach Benutzername + Passwort und legt die SQLite-Datenbank
unter `%USERPROFILE%\.dw_windows_mcp\` an.

Weitere Benutzer mit anderen Rollen:

```powershell
dw-windows-mcp user-add bob GeheimesPasswort123 --role standard
```

Rollen: `admin` (voller Zugriff), `standard` (kein Registry-Write, kein
Power-Management, kein Service-Stop/Restart), `readonly` (nur lesende Tools).

## 4. Lokale Nutzung (stdio) — z.B. Claude Desktop

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dw-windows-mcp": {
      "command": "C:\\Pfad\\zu\\dw_windows_mcp\\.venv\\Scripts\\dw-windows-mcp.exe",
      "args": ["run-stdio"],
      "env": { "DW_MCP_LOCAL_USER": "admin" }
    }
  }
}
```

## 5. Remote-Nutzung (HTTP/SSE + OAuth2) — z.B. vom Smartphone

```powershell
dw-windows-mcp run-http --host 0.0.0.0 --port 8765
```

Der Server lauscht nur lokal auf `host:port`. Erreichbarkeit von außen
(Port-Forwarding, DynDNS, Tunnel wie ngrok/Cloudflare Tunnel) musst du selbst
einrichten — das ist bewusst nicht Teil dieses Servers.

OAuth2-Client registrieren und Token holen: siehe [README.md](../README.md#remote-nutzung-httpsse--oauth2).

## 6. Autostart einrichten (optional)

Damit der HTTP/SSE-Server automatisch bei der Windows-Anmeldung startet:

```powershell
dw-windows-mcp install-autostart --host 0.0.0.0 --port 8765
```

Legt eine Windows-Aufgabenplanung-Task (`dw-windows-mcp-autostart`) an, die
beim Login des aktuellen Benutzers `dw-windows-mcp run-http` startet.

Rückgängig machen:

```powershell
dw-windows-mcp uninstall-autostart
```

Status prüfen:

```powershell
dw-windows-mcp autostart-status
```

## Deinstallation

```powershell
dw-windows-mcp uninstall-autostart
pip uninstall dw-windows-mcp
rmdir /s "%USERPROFILE%\.dw_windows_mcp"
```

## Fehlerbehebung

- **`winreg`/`wmi`/`win32clipboard` Import-Fehler:** Server läuft nicht unter
  Windows oder `pywin32`-Postinstall-Skript wurde nicht ausgeführt:
  `python .venv\Scripts\pywin32_postinstall.py -install`
- **Port bereits belegt:** anderen Port mit `--port` wählen.
- **`winget`-Fehler bei `install.*`-Tools:** App Installer (winget) muss
  installiert sein (Standard bei Windows 11).
