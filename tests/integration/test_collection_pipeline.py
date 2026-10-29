import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from internal.collector.runtime import Collector
from internal.config import CollectorConfig


def raw_line(path="/real-visit", ua="KimiBot/1.0"):
    stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'203.0.113.99 - - [{stamp}] "GET {path} HTTP/1.1" 200 42 "-" "{ua}"\n'.encode()


def wait_for(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("timed out waiting for integration condition")


@pytest.fixture
def live(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = os.environ | {
        "GEO_ADMIN_PASSWORD": "synthetic-live-test-password",
        "GEO_PUBLIC_URL": base,
        "GEO_COOKIE_SECURE": "false",
        "GEO_DATABASE": str(tmp_path / "monitor.sqlite3"),
        "GEO_EVIDENCE_REFRESH": "false",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "internal.server", "--port", str(port)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    with httpx.Client(base_url=base, timeout=2) as client:
        try:

            def healthy():
                try:
                    return client.get("/api/healthz").is_success
                except httpx.HTTPError:
                    return False

            wait_for(healthy)
            session = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "synthetic-live-test-password"},
            ).json()
            client.headers["X-CSRF-Token"] = session["csrf_token"]
            client.put(
                "/api/site", json={"domain": "example.com", "client_ip_mode": "trusted"}
            ).raise_for_status()
            credentials = client.post("/api/site/credentials").json()
            log = tmp_path / "site.access.log"
            log.write_bytes(raw_line("/pre-install"))
            configuration = {
                **credentials,
                "log_path": str(log),
                "state_path": str(tmp_path / "state.json"),
                "allow_http": True,
                "request_timeout": 1,
            }
            config_path = tmp_path / "collector.json"
            config_path.write_text(json.dumps(configuration))
            yield client, configuration, config_path, log
        finally:
            process.terminate()
            process.wait(timeout=10)


def collector_once(path):
    return subprocess.run(
        [sys.executable, "-m", "internal.collector", "--config", str(path), "--once"],
        capture_output=True,
        timeout=15,
    )


def test_continuous_real_log_arrives_automatically(live):
    client, config, config_path, log = live
    process = subprocess.Popen(
        [sys.executable, "-m", "internal.collector", "--config", str(config_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        wait_for(lambda: Path(config["state_path"]).exists())
        began = time.monotonic()
        with log.open("ab") as handle:
            handle.write(raw_line())
        result = wait_for(lambda: client.get("/api/events?days=1").json()["items"], seconds=20)
        assert result[0]["path"] == "/real-visit"
        assert time.monotonic() - began < 60
        assert all(item["path"] != "/pre-install" for item in result)
        state = Path(config["state_path"]).read_text()
        assert "203.0.113.99" not in state
        assert "KimiBot" not in state
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_restart_rotation_and_known_gap_on_live_server(live):
    client, config, config_path, log = live
    assert collector_once(config_path).returncode == 0
    with log.open("ab") as handle:
        handle.write(raw_line("/old-tail"))
    rotated = log.with_name(log.name + ".1")
    log.rename(rotated)
    log.write_bytes(raw_line("/new-file"))
    assert collector_once(config_path).returncode == 0
    assert collector_once(config_path).returncode == 0
    paths = {event["path"] for event in client.get("/api/events?days=1").json()["items"]}
    assert paths == {"/old-tail", "/new-file"}
    # No extra record on another process restart.
    assert collector_once(config_path).returncode == 0
    assert client.get("/api/overview?days=1").json()["summary"]["requests"] == 2
    with rotated.open("ab") as handle:
        handle.write(raw_line("/known-unconfirmed"))
    from internal.collector.tailer import Tailer

    pending = Tailer(CollectorConfig.model_validate(config)).next_batch()
    assert pending is not None
    rotated.unlink()
    assert collector_once(config_path).returncode == 0
    assert client.get("/api/collector/health").json()["gaps"]


def test_response_lost_after_server_commit_and_local_crash(admin, source, tmp_path):
    log = tmp_path / "access.log"
    log.write_bytes(b"")
    config = CollectorConfig(
        server_url="https://monitor.example.com",
        site_id=source["site_id"],
        source_id=source["source_id"],
        token=source["token"],
        log_path=log,
        state_path=tmp_path / "state.json",
    )
    lost = True

    def transport(request):
        nonlocal lost
        result = admin.request(
            request.method,
            request.url.path,
            content=request.content,
            headers={
                "Authorization": "Bearer " + source["token"],
                "Content-Type": "application/json",
            },
        )
        if request.url.path.endswith("batches") and lost:
            lost = False
            raise httpx.ReadError("response lost after committed transaction", request=request)
        return httpx.Response(result.status_code, json=result.json())

    with httpx.Client(base_url=config.server_url, transport=httpx.MockTransport(transport)) as http:
        collector = Collector(config, http)
        log.write_bytes(raw_line())
        assert not collector.step()
        assert admin.get("/api/overview?days=1").json()["summary"]["requests"] == 1
        restarted = Collector(config, http)
        assert restarted.step()
        assert restarted.tailer.state["generations"][0]["acknowledged"] == log.stat().st_size
        assert admin.get("/api/overview?days=1").json()["summary"]["requests"] == 1


def test_credential_update_reconnect_preserves_cursor_and_site(live):
    client, configuration, config_path, log = live
    config = CollectorConfig.load(config_path)
    with httpx.Client(base_url=config.server_url, headers={"Authorization": "Bearer " + configuration["token"]}) as wire:
        original = Collector(config, wire)
        with log.open("ab") as handle:
            handle.write(raw_line("/before-token-update"))
        assert original.step()
        new = client.post("/api/site/credentials").json()
        assert new["site_id"] == configuration["site_id"] and new["source_id"] == configuration["source_id"]
        with log.open("ab") as handle:
            handle.write(raw_line("/after-token-update"))
        source_bytes = log.read_bytes()
        position = original.tailer.state["generations"][0]["acknowledged"]
        assert not original.step() and original.state == "auth_error"
        assert original.tailer.state["generations"][0]["acknowledged"] == position
    configuration["token"] = new["token"]
    config_path.write_text(json.dumps(configuration))
    updated = CollectorConfig.load(config_path)
    with httpx.Client(base_url=updated.server_url, headers={"Authorization": "Bearer " + new["token"]}) as wire:
        reconnected = Collector(updated, wire)
        assert reconnected.step() and reconnected.heartbeat()
        assert reconnected.step()
    assert client.get("/api/overview?days=1").json()["summary"]["requests"] == 2
    assert log.read_bytes() == source_bytes


def test_openresty_main_preflight_new_logs_restart_and_ignored_forwarded_value(live):
    client, configuration, config_path, log = live
    old = raw_line("/pre-install-main").rstrip(b"\n") + b' "-"\n'
    log.write_bytes(old)
    # A real collector process must pass preflight on main before establishing EOF.
    assert collector_once(config_path).returncode == 0
    with log.open("ab") as handle:
        handle.write(raw_line("/new-main").rstrip(b"\n") + b' "198.51.100.17, 2001:db8::17"\n')
    source = log.read_bytes()
    assert collector_once(config_path).returncode == 0
    assert collector_once(config_path).returncode == 0
    events = client.get("/api/events?days=1").json()["items"]
    assert len(events) == 1 and events[0]["path"] == "/new-main"
    assert client.get("/api/overview?days=1").json()["summary"]["requests"] == 1
    assert log.read_bytes() == source
    state = Path(configuration["state_path"]).read_text()
    stored = json.dumps(events) + state
    assert not any(value in stored for value in ("198.51.100.17", "2001:db8::17", "/pre-install-main"))
