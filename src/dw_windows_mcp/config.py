"""Central configuration, loaded from environment variables with sensible defaults."""
from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar


def _data_dir() -> Path:
    d = Path(os.environ.get("DW_MCP_DATA_DIR", Path.home() / ".dw_windows_mcp"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Settings:
    data_dir: Path = _data_dir()
    db_path: Path = data_dir / "dw_windows_mcp.sqlite3"
    db_url: str = f"sqlite:///{db_path}"

    http_host: str = os.environ.get("DW_MCP_HTTP_HOST", "0.0.0.0")
    http_port: int = int(os.environ.get("DW_MCP_HTTP_PORT", "8765"))

    oauth_issuer: str = os.environ.get("DW_MCP_OAUTH_ISSUER", f"http://localhost:{http_port}")
    access_token_ttl_seconds: int = int(os.environ.get("DW_MCP_ACCESS_TOKEN_TTL", "3600"))
    refresh_token_ttl_seconds: int = int(os.environ.get("DW_MCP_REFRESH_TOKEN_TTL", "2592000"))

    confirm_token_ttl_seconds: int = int(os.environ.get("DW_MCP_CONFIRM_TTL", "120"))

    secret_key: str = os.environ.get("DW_MCP_SECRET_KEY", "")

    allowed_fs_roots: ClassVar[list[str]] = [
        p for p in os.environ.get("DW_MCP_FS_ROOTS", "").split(";") if p
    ]


settings = Settings()

if not settings.secret_key:
    import secrets

    key_file = settings.data_dir / "secret.key"
    if key_file.exists():
        settings.secret_key = key_file.read_text().strip()
    else:
        settings.secret_key = secrets.token_urlsafe(48)
        key_file.write_text(settings.secret_key)
