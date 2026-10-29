import json

import pytest

from internal.collector.locking import source_lock
from internal.config import CollectorConfig, ServerConfig, local_path, normalize_origin


def test_duplicate_process_lock_released_on_exit(tmp_path):
    path = tmp_path / "state.json"
    with source_lock(path):
        with pytest.raises(OSError):
            with source_lock(path):
                pass
    with source_lock(path):
        pass


@pytest.mark.parametrize("host", ["localhost", "192.0.2.10", "monitor.example.test"])
def test_http_requires_explicit_opt_in(tmp_path, host):
    config = {
        "server_url": f"http://{host}:8000",
        "site_id": "site",
        "source_id": "source",
        "token": "synthetic-token",
        "log_path": "access.log",
    }
    path = tmp_path / "collector.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        CollectorConfig.load(path)
    config["allow_http"] = True
    path.write_text(json.dumps(config))
    assert CollectorConfig.load(path).allow_http


def test_https_collector_remains_available_without_http_permission(tmp_path):
    path = tmp_path / "collector.json"
    path.write_text(
        json.dumps(
            {
                "server_url": "https://monitor.example.test",
                "site_id": "site",
                "source_id": "source",
                "token": "synthetic-token",
                "log_path": "access.log",
            }
        )
    )
    config = CollectorConfig.load(path)
    assert not config.allow_http and config.server_url.startswith("https://")


def test_origin_canonicalization_and_unsafe_configuration_rejection():
    assert normalize_origin("https://MONITOR.EXAMPLE.COM:443/") == "https://monitor.example.com"
    assert normalize_origin("http://[::1]:8000") == "http://[::1]:8000"
    for value in [
        "https://:secret@example.com",
        "https://host'quoted.example",
        "https://example.com:bad",
        "https://example.com/path",
    ]:
        with pytest.raises(ValueError):
            normalize_origin(value)


def test_local_storage_prefers_explicit_configuration_and_preserves_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEO_ADMIN_PASSWORD", "synthetic-local-password-2026")
    monkeypatch.setenv("GEO_PUBLIC_URL", "http://localhost:8000")
    monkeypatch.delenv("GEO_DATABASE", raising=False)
    assert ServerConfig.from_environment().database.as_posix() == ".local/data/monitor.sqlite3"
    legacy = tmp_path / "data/monitor.sqlite3"
    legacy.parent.mkdir()
    legacy.touch()
    assert ServerConfig.from_environment().database.as_posix() == "data/monitor.sqlite3"
    current = tmp_path / ".local/data/monitor.sqlite3"
    current.parent.mkdir(parents=True)
    current.touch()
    assert ServerConfig.from_environment().database.as_posix() == ".local/data/monitor.sqlite3"
    monkeypatch.setenv("GEO_DATABASE", "explicit.sqlite3")
    assert ServerConfig.from_environment().database.as_posix() == "explicit.sqlite3"
    assert local_path(".local/state.json", "legacy-state.json").as_posix() == ".local/state.json"
    (tmp_path / "legacy-state.json").touch()
    assert local_path(".local/state.json", "legacy-state.json").as_posix() == "legacy-state.json"
