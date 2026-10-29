"""Validated deployment configuration; secrets never appear in repr or errors."""

import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise ValueError("HTTP(S) origin without credentials is required")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("origin must not contain a path or query")
    host = parsed.hostname.encode("idna").decode().lower()
    if ":" in host:
        host = "[" + host + "]"
    elif not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("invalid origin host")
    port = parsed.port
    suffix = f":{port}" if port and port != {"http": 80, "https": 443}[parsed.scheme] else ""
    return f"{parsed.scheme}://{host}{suffix}"


def environment_boolean(name: str, default: bool) -> bool:
    value = os.environ.get(name, str(default)).lower()
    if value not in {"true", "false"}:
        raise ValueError("boolean environment options must be true or false")
    return value == "true"


def local_path(current: str, legacy: str) -> Path:
    """Keep existing local data usable; explicit configuration takes priority."""
    destination, previous = Path(current), Path(legacy)
    return previous if previous.exists() and not destination.exists() else destination


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database: Path = Field(
        default_factory=lambda: local_path(".local/data/monitor.sqlite3", "data/monitor.sqlite3")
    )
    admin_username: str = Field(default="admin", min_length=1, max_length=100)
    admin_password: SecretStr
    public_url: str
    cookie_secure: bool = True
    web_directory: Path = Path("web/dist")
    project_directory: Path = Field(default_factory=Path.cwd)
    evidence_refresh_seconds: int = Field(default=3600, ge=60)
    evidence_ttl_seconds: int = Field(default=86400, ge=60)
    evidence_enabled: bool = True
    heartbeat_timeout: int = Field(default=90, ge=1)
    session_seconds: int = Field(default=28800, ge=60)

    @field_validator("admin_password")
    @classmethod
    def password_length(cls, value: SecretStr) -> SecretStr:
        if not 12 <= len(value.get_secret_value()) <= 1024:
            raise ValueError("administrator password must contain 12 to 1024 characters")
        return value

    @field_validator("public_url")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        return normalize_origin(value)

    @classmethod
    def from_environment(cls) -> "ServerConfig":
        return cls(
            admin_password=SecretStr(os.environ.get("GEO_ADMIN_PASSWORD", "")),
            admin_username=os.environ.get("GEO_ADMIN_USERNAME", "admin"),
            public_url=os.environ.get("GEO_PUBLIC_URL", ""),
            database=Path(os.environ["GEO_DATABASE"])
            if "GEO_DATABASE" in os.environ
            else local_path(".local/data/monitor.sqlite3", "data/monitor.sqlite3"),
            cookie_secure=environment_boolean("GEO_COOKIE_SECURE", True),
            web_directory=Path(os.environ.get("GEO_WEB_DIRECTORY", "web/dist")),
            project_directory=Path(os.environ.get("GEO_PROJECT_DIRECTORY", ".")),
            evidence_enabled=environment_boolean("GEO_EVIDENCE_REFRESH", True),
        )


class CollectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_url: str
    site_id: str = Field(min_length=1, max_length=100)
    source_id: str = Field(min_length=1, max_length=100)
    token: SecretStr = Field(min_length=1, max_length=256)
    log_path: Path
    state_path: Path = Field(
        default_factory=lambda: local_path(
            ".local/collector-state/state.json", "collector-state/state.json"
        )
    )
    rotation_pattern: str | None = None
    batch_size: int = Field(default=200, ge=1, le=1000)
    flush_seconds: float = Field(default=10, gt=0, le=30)
    catchup_pause_seconds: float = Field(default=0.25, ge=0.05, le=30)
    heartbeat_seconds: float = Field(default=30, gt=0, le=30)
    request_timeout: float = Field(default=10, gt=0, le=30)
    allow_http: bool = False

    @field_validator("server_url")
    @classmethod
    def server_address(cls, value: str) -> str:
        return normalize_origin(value)

    @field_validator("rotation_pattern")
    @classmethod
    def relative_pattern(cls, value: str | None) -> str | None:
        if value is not None and (Path(value).is_absolute() or ".." in Path(value).parts):
            raise ValueError("rotation pattern must remain within the mounted log directory")
        return value

    @field_validator("token")
    @classmethod
    def token_format(cls, value: SecretStr) -> SecretStr:
        if any(character.isspace() for character in value.get_secret_value()):
            raise ValueError("collector credential must not contain whitespace")
        return value

    @classmethod
    def load(cls, path: Path) -> "CollectorConfig":
        config = cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if config.server_url.startswith("http:") and not config.allow_http:
            raise ValueError("HTTP requires explicit allow_http; HTTPS remains available")
        if not config.token.get_secret_value():
            raise ValueError("collector token is required")
        return config
