import json
import time
from datetime import UTC, datetime

import pytest

from internal.crawler.rules import RULES
from internal.server.services.ingest import purge


def test_authentication_csrf_and_logout(client):
    assert client.get("/api/site").status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).status_code
        == 401
    )
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "synthetic-test-password-2026"}
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.put("/api/site", json={"domain": "example.com"}).status_code == 403
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_site_is_single_and_secret_not_retrievable(admin, source):
    original = admin.get("/api/site").json()
    updated = admin.put("/api/site", json={"domain": "www.example.com"}).json()
    assert updated["id"] == original["id"]
    assert updated["source_id"] == original["source_id"]
    assert source["token"] not in json.dumps(updated)
    assert admin.put("/api/site", json={"domain": "https://evil.example/path"}).status_code == 422
    with admin.app.state.database.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM site").fetchone()[0] == 1
        assert conn.execute("SELECT token_hash FROM site").fetchone()[0] != source["token"]


def test_collector_token_does_not_authenticate_admin(client, source, headers):
    client.cookies.clear()
    assert client.get("/api/events", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/collector/preflight",
            headers=headers,
            json={"site_id": source["site_id"], "source_id": source["source_id"]},
        ).status_code
        == 200
    )


def test_static_fallback_does_not_swallow_api_errors(client):
    assert client.get("/overview").status_code == 200
    assert client.get("/api/not-real").status_code == 404
    assert client.post("/api/not-real").status_code == 404
    assert client.get("/missing.js").status_code == 404


def test_validation_never_echoes_private_input(admin, make_batch, headers):
    payload = make_batch()
    payload["events"][0]["status"] = "203.0.113.99"
    response = admin.post("/api/collector/batches", json=payload, headers=headers)
    assert response.status_code == 422
    assert "203.0.113.99" not in response.text
    secret = "secret-that-must-not-be-echoed"
    response = admin.post("/api/auth/login", json={"username": [secret], "password": secret})
    assert secret not in response.text


def test_body_is_bounded(admin):
    assert admin.post("/api/auth/login", content=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413


def test_duplicate_and_identical_lines_are_distinct(admin, make_batch, headers):
    payload = make_batch(count=2)
    first = admin.post("/api/collector/batches", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 2
    assert (
        admin.post("/api/collector/batches", json=payload, headers=headers).json()["inserted"] == 0
    )
    result = admin.get("/api/overview?days=1").json()
    assert result["summary"]["requests"] == 2
    assert result["summary"]["pages"] == 1
    event = admin.get("/api/events?days=1").json()["items"][0]
    assert event["path"] == "/article"
    assert event["masked_ip"] == "203.0.113.*"
    assert event["verification"] == "evidence_unavailable"
    for database_file in admin.app.state.database.path.parent.glob("monitor.sqlite3*"):
        private_data = database_file.read_bytes()
        assert b"203.0.113.99" not in private_data
        assert b"?q=secret" not in private_data


def test_credentials_and_atomic_rejection(admin, make_batch, headers):
    payload = make_batch(count=2)
    assert (
        admin.post(
            "/api/collector/batches", json=payload, headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    payload["events"][1]["status"] = 999
    assert admin.post("/api/collector/batches", json=payload, headers=headers).status_code == 422
    assert admin.get("/api/overview?days=1").json()["summary"]["requests"] == 0


def test_purge_keeps_replay_boundary(admin, make_batch, headers):
    payload = make_batch(
        occurred_at=datetime.fromtimestamp(time.time() - 31 * 86400, UTC).isoformat()
    )
    assert (
        admin.post("/api/collector/batches", json=payload, headers=headers).json()["inserted"] == 1
    )
    assert purge(admin.app.state.database) == 1
    assert (
        admin.post("/api/collector/batches", json=payload, headers=headers).json()["inserted"] == 0
    )
    with admin.app.state.database.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_pagination_filters_and_non_success_status(admin, make_batch, headers):
    first = make_batch(count=3, status=403)
    assert admin.post("/api/collector/batches", json=first, headers=headers).status_code == 200
    data = admin.get("/api/events?days=1&limit=2&crawler=KimiBot").json()
    assert len(data["items"]) == 2
    assert all(item["status"] == 403 for item in data["items"])
    second = admin.get(
        "/api/events",
        params={"days": 1, "limit": 2, "crawler": "KimiBot", "cursor": data["next_cursor"]},
    ).json()
    assert len(second["items"]) == 1
    assert not {item["id"] for item in data["items"]} & {item["id"] for item in second["items"]}
    assert admin.get("/api/events?start=2026-10-29&end=2026-10-01").status_code == 400


@pytest.mark.parametrize(
    "ua,name",
    [
        ("Kimi-User", "Kimi 用户触发访问"),
        ("Kimi-SearchBot", "Kimi 搜索爬虫"),
        ("Bytespider", "字节跳动爬虫"),
        ("HySpider", "腾讯混元训练爬虫"),
    ],
)
def test_required_identity_labels(admin, make_batch, headers, ua, name):
    assert (
        admin.post("/api/collector/batches", json=make_batch(ua=ua), headers=headers).status_code
        == 200
    )
    event = admin.get("/api/events?days=1").json()["items"][0]
    assert event["name"] == name


def test_official_verification_and_unknown_samples(admin, make_batch, headers):
    admin.app.state.evidence.save(RULES[0], {"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})
    assert (
        admin.post("/api/collector/batches", json=make_batch(), headers=headers).status_code == 200
    )
    assert admin.get("/api/events?days=1").json()["items"][0]["verification"] == "verified"
    assert (
        admin.post(
            "/api/collector/batches",
            json=make_batch(start=100, ua="NewTestBot/1.0 203.0.113.99"),
            headers=headers,
        ).status_code
        == 200
    )
    hints = admin.get("/api/unknown-agents").json()["items"]
    assert hints[0]["hint"] == "newtestbot"
    assert "203.0.113.99" not in json.dumps(hints)
    assert admin.get("/api/overview?days=1").json()["summary"]["requests"] == 1
