import importlib
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from internal.config import CollectorConfig, ServerConfig
from internal.protocol import Batch, batch_identity
from internal.storage.database import MIGRATIONS, Database, preferred_journal_mode


def test_imports_have_no_runtime_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    importlib.import_module("internal.server.__main__")
    importlib.import_module("internal.collector.__main__")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "version,mode",
    [
        ((3, 50, 4), "DELETE"),
        ((3, 51, 2), "DELETE"),
        ((3, 51, 3), "WAL"),
        ((3, 52, 0), "WAL"),
        ((3, 50, 7), "WAL"),
        ((3, 44, 6), "WAL"),
        ((3, 45, 0), "DELETE"),
    ],
)
def test_journal_mode_excludes_known_unpatched_versions(version, mode):
    assert preferred_journal_mode(version) == mode


def test_missing_configuration_is_safe():
    with pytest.raises(ValidationError):
        ServerConfig(admin_password="short", public_url="")
    result = subprocess.run(
        [sys.executable, "-m", "internal.collector", "--config", "missing.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Invalid collector configuration" in result.stderr


def test_configuration_has_no_secret_repr():
    config = CollectorConfig(
        server_url="https://monitor.example.com",
        site_id="site",
        source_id="source",
        token="not-for-logs",
        log_path="access.log",
    )
    assert "not-for-logs" not in repr(config)


def test_migration_is_repeatable_and_atomic(tmp_path):
    database = Database(tmp_path / "monitor.db")
    database.migrate([MIGRATIONS[0]])
    database.migrate([MIGRATIONS[0]])
    with database.read() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    with pytest.raises(sqlite3.OperationalError):
        database.migrate([[], ["CREATE TABLE partial (id INTEGER)", "INVALID SQL"]])
    with database.read() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            conn.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone() is None
        )


def test_concurrent_transactions_and_rollback(tmp_path):
    database = Database(tmp_path / "monitor.db")
    database.migrate()
    with database.transaction() as conn:
        conn.execute("CREATE TABLE counter (n INTEGER)")
        conn.execute("INSERT INTO counter VALUES(0)")

    def increment(_):
        with database.transaction() as conn:
            conn.execute("UPDATE counter SET n=n+1")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(increment, range(20)))
    with pytest.raises(RuntimeError), database.transaction() as conn:
        conn.execute("UPDATE counter SET n=999")
        raise RuntimeError("rollback")
    with database.read() as conn:
        assert conn.execute("SELECT n FROM counter").fetchone()[0] == 20


def test_protocol_rejects_holes_overlap_and_version():
    base = dict(
        site_id="site",
        source_id="source",
        generation="generation",
        start_offset=0,
        end_offset=10,
        batch_id=batch_identity("source", "generation", 0, 10),
        events=[],
        issues=[dict(offset=0, end_offset=10, reason="invalid_line")],
    )
    assert Batch(**base).end_offset == 10
    for override in [dict(version=2), dict(issues=[]), dict(batch_id="0" * 64)]:
        with pytest.raises(ValidationError):
            Batch(**(base | override))
