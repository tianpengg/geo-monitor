import io
import sqlite3
import tarfile
from pathlib import Path

from internal.server.downloads import collector_archive
from internal.storage.database import MIGRATIONS, Database


def test_download_bundle_is_a_fixed_regular_file_allowlist(client):
    response = client.get("/downloads/collector.tar.gz")
    assert response.status_code == 200
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        members = archive.getmembers()
        names = {item.name for item in members}
        assert "pyproject.toml" in names
        assert "uv.lock" in names
        assert "LICENSE" in names
        assert archive.extractfile("LICENSE").read() == Path("LICENSE").read_bytes()
        assert "internal/collector/runtime.py" in names
        assert "deploy/collector.Dockerfile" in names
        assert all(
            item.isfile() and not item.name.startswith("/") and ".." not in Path(item.name).parts
            for item in members
        )
        assert not any(
            ".env" in name or "collector.json" in name or "sqlite" in name for name in names
        )
    assert client.get("/downloads/install-collector.sh").status_code == 200


def test_consistent_database_backup_restores(tmp_path):
    database = Database(tmp_path / "source.sqlite3")
    database.migrate()
    with database.transaction() as conn:
        conn.execute("INSERT INTO admin VALUES(1,'synthetic-admin','synthetic-hash')")
    backup = tmp_path / "backup.sqlite3"
    database.backup(backup)
    with sqlite3.connect(backup) as conn:
        assert conn.execute("SELECT username FROM admin").fetchone()[0] == "synthetic-admin"
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_fixture_secrets_not_distributed(tmp_path):
    result = collector_archive(Path.cwd())
    assert b"synthetic-test-password-2026" not in result
    assert b"REPLACE_COLLECTOR_TOKEN" not in result
