import json
import ssl
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from internal.crawler.catalog import RuleStore
from internal.crawler.evidence import verify
from internal.crawler.fetch import MAX_EVIDENCE_BYTES, fetch_evidence
from internal.server.app import create_app
from internal.storage.database import MIGRATIONS, Database


def payload(**changes):
    return (
        dict(
            token="ExampleBot",
            match_token="ExampleBot",
            name="示例爬虫",
            operator="示例平台",
            product_attribution="产品归属未确认",
            evidence_url=None,
            documentation_url=None,
            evidence_format="json",
            enabled=True,
        )
        | changes
    )


def test_legacy_database_upgrade_keeps_existing_data(tmp_path):
    database = Database(tmp_path / "legacy.sqlite3")
    database.migrate(MIGRATIONS[:-1])
    with database.transaction() as conn:
        conn.execute("INSERT INTO unknown_agents VALUES('existing','unknownbot',3,1)")
    database.migrate()
    store = RuleStore(database)
    assert len(store.records()) == 20
    store.seed()
    with database.read() as conn:
        assert conn.execute("SELECT request_count FROM unknown_agents").fetchone()[0] == 3
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_rule_count_limit_rejects_new_entries_without_deleting_existing_rules(admin):
    with admin.app.state.database.transaction() as conn:
        for number in range(236):
            conn.execute(
                "INSERT INTO crawler_rules SELECT ?,?,name,operator,product_attribution,evidence_url,documentation_url,evidence_format,0,origin,revision,version,updated_at FROM crawler_rules WHERE token='KimiBot'",
                (f"LimitBot{number}", f"LimitBot{number}"),
            )
    response = admin.post("/api/crawler-rules", json=payload())
    assert response.status_code == 400
    assert len(admin.get("/api/crawler-rules").json()["items"]) == 256


def edit(admin, row, **changes):
    body = {key: row[key] for key in (*payload().keys(), "revision")}
    return admin.put("/api/crawler-rules/" + row["token"], json=body | changes)


def test_rule_endpoints_require_admin_and_csrf(client, admin):
    client.cookies.clear()
    assert client.get("/api/crawler-rules").status_code == 401
    from tests.conftest import TEST_PASSWORD

    session = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    client.headers.pop("X-CSRF-Token", None)
    assert client.post("/api/crawler-rules", json=payload()).status_code == 403
    client.headers["X-CSRF-Token"] = session.json()["csrf_token"]
    assert client.post("/api/crawler-rules", json=payload()).status_code == 201


def test_seed_edit_and_custom_rules_survive_application_restart(admin):
    rows = admin.get("/api/crawler-rules").json()["items"]
    assert len(rows) == 20 and all(row["origin"] == "builtin" for row in rows)
    kimi = next(row for row in rows if row["token"] == "KimiBot")
    changed = edit(admin, kimi, enabled=False).json()
    created = admin.post("/api/crawler-rules", json=payload()).json()
    with TestClient(create_app(admin.app.state.config, refresh_evidence=False)):
        records = RuleStore(admin.app.state.database).records()
        assert len(records) == 21
        assert (
            next(row for row in records if row["token"] == "KimiBot")["version"]
            == changed["version"]
        )
        assert not next(row for row in records if row["token"] == "KimiBot")["enabled"]
        assert (
            next(row for row in records if row["token"] == "ExampleBot")["revision"]
            == created["revision"]
        )


def test_dynamic_classification_history_toggle_and_replay(admin, source, make_batch, headers):
    created = admin.post("/api/crawler-rules", json=payload()).json()

    def send(start, ua):
        batch = make_batch(start=start, ua=ua, path="/dynamic")
        result = admin.post("/api/collector/batches", json=batch, headers=headers)
        assert result.status_code == 200
        return batch, result.json()["inserted"]

    original, inserted = send(0, "ExampleBot/1.0")
    assert inserted == 1
    assert admin.get("/api/events").json()["items"][0]["verification"] == "ua_only"
    current = edit(admin, created, name="新名称", match_token="ExampleBotV2").json()
    assert send(100, "ExampleBotV2/2.0")[1] == 1
    assert send(200, "NotExampleBotV2Suffix/2.0")[1] == 0
    records = admin.get("/api/events").json()["items"]
    assert {row["name"] for row in records} == {"示例爬虫", "新名称"}
    assert {row["rule_version"] for row in records} == {"ExampleBot@1", "ExampleBot@2"}
    overview = admin.get("/api/overview").json()
    assert len(overview["crawlers"]) == 1 and overview["crawlers"][0]["requests"] == 2
    assert overview["crawlers"][0]["name"] == "新名称"
    page = admin.get("/api/pages/detail", params={"path": "/dynamic"}).json()
    assert len(page["crawlers"]) == 1 and page["crawlers"][0]["requests"] == 2
    current = edit(admin, current, enabled=False).json()
    assert send(300, "ExampleBotV2/2.0")[1] == 0
    assert len(admin.get("/api/events?crawler=ExampleBot").json()["items"]) == 2
    assert (
        next(
            row
            for row in admin.get("/api/crawlers").json()["rules"]
            if row["token"] == "ExampleBot"
        )["coverage"]
        == "已停用"
    )
    assert (
        admin.post("/api/collector/batches", json=original, headers=headers).json()["inserted"] == 0
    )
    edit(admin, current, enabled=True).raise_for_status()
    assert send(400, "ExampleBotV2/2.0")[1] == 1


def test_uniqueness_stale_revision_and_immutable_identity(admin):
    row = admin.post("/api/crawler-rules", json=payload()).json()
    assert admin.post("/api/crawler-rules", json=payload(token="examplebot")).status_code == 409
    assert (
        admin.post(
            "/api/crawler-rules", json=payload(token="AnotherBot", match_token="examplebot")
        ).status_code
        == 409
    )
    updated = edit(admin, row, name="更新名称")
    assert updated.status_code == 200
    assert edit(admin, row, name="过期覆盖").status_code == 409
    assert edit(admin, updated.json(), token="ChangedIdentity").status_code == 400
    assert RuleStore(admin.app.state.database).get(row["token"])["name"] == "更新名称"


@pytest.mark.parametrize(
    "changes",
    [
        {"match_token": ".*Bot"},
        {"token": "Bad/1.0"},
        {"name": ""},
        {"enabled": "true"},
        {"evidence_url": "http://example.com/ips.json"},
        {"evidence_url": "https://127.0.0.1/ips.json"},
        {"evidence_url": "https://user:private@example.com/ips.json"},
        {"evidence_url": "https://example.com:8443/ips.json"},
        {"documentation_url": "javascript:alert(1)"},
        {"evidence_url": 42},
    ],
)
def test_invalid_rule_input_is_rejected_without_echoing_private_values(admin, changes):
    response = admin.post("/api/crawler-rules", json=payload(**changes))
    assert response.status_code == 422
    assert "private" not in response.text
    assert len(admin.get("/api/crawler-rules").json()["items"]) == 20


def test_domestic_attribution_stays_unconfirmed(admin):
    row = next(
        row
        for row in admin.get("/api/crawler-rules").json()["items"]
        if row["token"] == "Bytespider"
    )
    assert edit(admin, row, product_attribution="豆包").status_code == 400
    assert edit(admin, row, enabled=False).status_code == 200


def test_new_source_invalidates_cache_and_old_refresh_cannot_restore_it(admin, monkeypatch):
    row = admin.post(
        "/api/crawler-rules", json=payload(evidence_url="https://example.com/one.json")
    ).json()
    store = admin.app.state.evidence
    old_rule = next(rule for rule in store.rules.snapshot() if rule.token == row["token"])
    store.save(old_rule, ["203.0.113.0/24"])
    changed = edit(admin, row, evidence_url="https://example.com/two.json").json()
    assert row["token"] not in store.snapshot()
    store.save(old_rule, ["203.0.113.0/24"])
    assert row["token"] not in store.snapshot()
    rule = next(rule for rule in store.rules.snapshot() if rule.token == row["token"])
    assert (
        verify(rule, "203.0.113.1", "trusted", store.snapshot(), 0)["verification"]
        == "evidence_unavailable"
    )
    monkeypatch.setattr(
        "internal.crawler.evidence.fetch_evidence",
        lambda url: json.dumps(["203.0.113.0/24"]).encode(),
    )
    refreshed = admin.post(f"/api/crawler-rules/{row['token']}/refresh-evidence")
    assert refreshed.json()["evidence_state"] == "available"
    assert store.snapshot()[row["token"]]["source"] == changed["evidence_url"]
    edit(admin, changed, evidence_url=None).raise_for_status()
    assert admin.post(f"/api/crawler-rules/{row['token']}/refresh-evidence").status_code == 400


def test_metadata_edit_keeps_valid_evidence_but_ua_edit_invalidates_it(admin):
    row = admin.post(
        "/api/crawler-rules", json=payload(evidence_url="https://example.com/ips.json")
    ).json()
    store = admin.app.state.evidence
    rule = next(rule for rule in store.rules.snapshot() if rule.token == row["token"])
    store.save(rule, ["203.0.113.0/24"])
    changed = edit(admin, row, name="新名称").json()
    assert changed["evidence_state"] == "available"
    changed = edit(admin, changed, match_token="ExampleSearchBot").json()
    assert changed["evidence_state"] == "unavailable"
    assert row["token"] not in store.snapshot()


def test_private_dns_is_rejected_before_connection(monkeypatch):
    monkeypatch.setattr(
        "internal.crawler.fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    connect = MagicMock()
    monkeypatch.setattr("internal.crawler.fetch.socket.create_connection", connect)
    with pytest.raises(ValueError):
        fetch_evidence("https://example.com/ips.json")
    connect.assert_not_called()


def test_old_refresh_failure_cannot_invalidate_new_evidence(admin, monkeypatch):
    row = admin.post(
        "/api/crawler-rules", json=payload(evidence_url="https://example.com/old.json")
    ).json()
    evidence = admin.app.state.evidence

    def stale_fetch(_url):
        evidence.rules.save(payload(evidence_url="https://example.com/new.json"), row["revision"])
        rule = next(rule for rule in evidence.rules.snapshot() if rule.token == row["token"])
        evidence.save(rule, ["203.0.113.0/24"])
        raise OSError("old request failed")

    monkeypatch.setattr("internal.crawler.evidence.fetch_evidence", stale_fetch)
    evidence.refresh(token=row["token"])
    snapshot = evidence.snapshot()[row["token"]]
    assert snapshot["available"] == 1 and snapshot["source"] == "https://example.com/new.json"


@pytest.mark.parametrize("mode", ["success", "redirect", "oversize", "certificate"])
def test_fetch_pins_public_ip_preserves_tls_hostname_and_bounds_response(monkeypatch, mode):
    monkeypatch.setattr(
        "internal.crawler.fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
    )
    raw, tls, context, connection = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    raw.__enter__.return_value = raw
    tls.__enter__.return_value = tls
    context.wrap_socket.return_value = tls
    connector = MagicMock(return_value=raw)
    monkeypatch.setattr("internal.crawler.fetch.socket.create_connection", connector)
    monkeypatch.setattr("internal.crawler.fetch.ssl.create_default_context", lambda: context)
    monkeypatch.setattr(
        "internal.crawler.fetch.http.client.HTTPSConnection", lambda *args, **kwargs: connection
    )
    response = connection.getresponse.return_value
    response.status = 302 if mode == "redirect" else 200
    response.read.return_value = b"x" * (MAX_EVIDENCE_BYTES + 1) if mode == "oversize" else b"[]"
    if mode == "certificate":
        context.wrap_socket.side_effect = ssl.SSLCertVerificationError("invalid certificate")
    if mode == "success":
        assert fetch_evidence("https://example.com/ips.json?version=1") == b"[]"
        connection.request.assert_called_once_with(
            "GET", "/ips.json?version=1", headers={"Accept-Encoding": "identity"}
        )
        response.read.assert_called_once_with(MAX_EVIDENCE_BYTES + 1)
    else:
        with pytest.raises((ValueError, ssl.SSLCertVerificationError)):
            fetch_evidence("https://example.com/ips.json")
    connector.assert_called_once_with(("8.8.8.8", 443), timeout=5)
    context.wrap_socket.assert_called_once_with(raw, server_hostname="example.com")
    connection.close.assert_called_once()
