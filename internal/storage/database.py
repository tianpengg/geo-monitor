import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

MIGRATIONS = [
    [
        "CREATE TABLE admin (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, password_hash TEXT NOT NULL)",
        "CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, csrf_token TEXT NOT NULL, expires_at REAL NOT NULL)",
        """CREATE TABLE site (
            id TEXT PRIMARY KEY, singleton INTEGER UNIQUE NOT NULL DEFAULT 1 CHECK(singleton=1),
            source_id TEXT UNIQUE NOT NULL, domain TEXT NOT NULL, timezone TEXT NOT NULL,
            token_hash TEXT, client_ip_mode TEXT NOT NULL DEFAULT 'unknown')""",
        """CREATE TABLE generations (
            source_id TEXT NOT NULL, generation TEXT NOT NULL,
            acknowledged_offset INTEGER NOT NULL, PRIMARY KEY(source_id,generation))""",
        """CREATE TABLE receipts (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, generation TEXT NOT NULL,
            end_offset INTEGER NOT NULL, received_at REAL NOT NULL)""",
        """CREATE TABLE events (
            id TEXT PRIMARY KEY, site_id TEXT NOT NULL, occurred_at REAL NOT NULL,
            received_at REAL NOT NULL, path TEXT NOT NULL, method TEXT NOT NULL, status INTEGER NOT NULL,
            crawler TEXT NOT NULL, name TEXT NOT NULL, operator TEXT NOT NULL,
            product_attribution TEXT NOT NULL, verification TEXT NOT NULL, masked_ip TEXT NOT NULL,
            rule_version TEXT NOT NULL, evidence_source TEXT, evidence_version TEXT,
            evidence_fetched_at REAL, evidence_expires_at REAL)""",
        "CREATE INDEX events_time ON events(site_id,occurred_at DESC,id DESC)",
        "CREATE INDEX events_crawler_time ON events(site_id,crawler,occurred_at DESC,id DESC)",
        """CREATE TABLE collector_health (
            source_id TEXT PRIMARY KEY, instance_id TEXT, sequence INTEGER NOT NULL DEFAULT -1,
            heartbeat_at REAL, baseline_at REAL, log_received_at REAL, processed_at REAL,
            last_read_at REAL, state TEXT, error_code TEXT, read_offset INTEGER NOT NULL DEFAULT 0,
            acknowledged_offset INTEGER NOT NULL DEFAULT 0, pending_bytes INTEGER,
            parse_errors INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE gaps (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, reason TEXT NOT NULL,
            detected_at REAL NOT NULL, generation TEXT, start_offset INTEGER, end_offset INTEGER)""",
        """CREATE TABLE evidence (
            crawler TEXT PRIMARY KEY, source TEXT NOT NULL, version TEXT NOT NULL,
            fetched_at REAL NOT NULL, expires_at REAL NOT NULL, networks_json TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1)""",
        """CREATE TABLE unknown_agents (
            fingerprint TEXT PRIMARY KEY, hint TEXT NOT NULL, request_count INTEGER NOT NULL,
            last_seen_at REAL NOT NULL)""",
    ],
    [
        "CREATE INDEX events_path_time ON events(site_id,path,occurred_at)",
        """CREATE TABLE content_pages (
            site_id TEXT NOT NULL REFERENCES site(id), host TEXT NOT NULL,
            path TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', imported_at REAL NOT NULL,
            PRIMARY KEY(site_id,host,path))""",
    ],
    [
        """CREATE TABLE crawler_rules (
            token TEXT PRIMARY KEY COLLATE NOCASE,
            match_token TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL, operator TEXT NOT NULL, product_attribution TEXT NOT NULL,
            evidence_url TEXT, documentation_url TEXT, evidence_format TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), origin TEXT NOT NULL,
            revision INTEGER NOT NULL, version TEXT NOT NULL, updated_at REAL NOT NULL)""",
    ],
    [
        """CREATE TABLE sitemap_sources (
            site_id TEXT NOT NULL REFERENCES site(id), host TEXT NOT NULL, url TEXT NOT NULL,
            enabled INTEGER NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL,
            last_attempt_at REAL, last_success_at REAL, next_run_at REAL, last_error TEXT,
            pages INTEGER, files INTEGER, added INTEGER, run_token TEXT, lease_until REAL,
            PRIMARY KEY(site_id,host))""",
    ],
    [
        "ALTER TABLE site ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]'",
    ],
]


def preferred_journal_mode(version: tuple[int, ...]) -> str:
    # Official WAL-reset fix, including the two documented backport branches.
    patched = (
        version >= (3, 51, 3)
        or (3, 50, 7) <= version < (3, 51, 0)
        or (3, 44, 6) <= version < (3, 45, 0)
    )
    return "WAL" if patched else "DELETE"


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def migrate(self, migrations: list[list[str]] | None = None) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.read() as conn:
            conn.execute(
                "PRAGMA journal_mode=" + preferred_journal_mode(sqlite3.sqlite_version_info)
            )
        os.chmod(self.path, 0o600)
        with self.transaction() as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            plan = migrations if migrations is not None else MIGRATIONS
            if current > len(plan):
                raise RuntimeError("database schema is newer than this application")
            for number in range(current, len(plan)):
                for statement in plan[number]:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version={number + 1}")

    def backup(self, destination: Path) -> None:
        if destination.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from database")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.read() as source, sqlite3.connect(destination) as target:
            os.chmod(destination, 0o600)
            source.backup(target)
