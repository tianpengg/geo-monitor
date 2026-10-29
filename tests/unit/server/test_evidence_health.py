import time
from datetime import UTC, datetime

import httpx
import pytest

from internal.crawler.evidence import parse_networks, verify
from internal.crawler.rules import RULES, identify, mask_ip
from internal.protocol import Heartbeat
from internal.server.services.ingest import heartbeat
from internal.server.services.queries import bounds, health


def test_evidence_schema_ipv4_ipv6_and_invalid_data():
    assert parse_networks(
        {"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}, {"ipv6Prefix": "2001:db8::/32"}]}
    ) == ["2001:db8::/32", "203.0.113.0/24"]
    assert parse_networks({"ips": ["203.0.113.9"]}) == ["203.0.113.9/32"]
    for payload in [[], {}, {"prefixes": "bad"}, {"prefixes": [{"ipv4Prefix": "not-an-ip"}]}]:
        with pytest.raises(ValueError):
            parse_networks(payload)


def test_evidence_refresh_error_and_expiry(admin):
    store = admin.app.state.evidence

    def good(request):
        return httpx.Response(200, json={"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})

    with httpx.Client(transport=httpx.MockTransport(good)) as client:
        store.refresh(client)
    snapshots = store.snapshot()
    now = time.time()
    assert verify(RULES[0], "203.0.113.9", "trusted", snapshots, now)["verification"] == "verified"
    assert (
        verify(RULES[0], "198.51.100.1", "trusted", snapshots, now)["verification"] == "ip_mismatch"
    )
    assert (
        verify(RULES[0], "203.0.113.9", "unknown", snapshots, now)["verification"]
        == "client_ip_unknown"
    )
    assert verify(RULES[3], "203.0.113.9", "trusted", snapshots, now)["verification"] == "ua_only"
    assert (
        verify(RULES[0], "203.0.113.9", "trusted", snapshots, now + 86401)["verification"]
        == "evidence_unavailable"
    )
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"prefixes": "invalid"})
        )
    ) as client:
        store.refresh(client)
    assert (
        verify(RULES[0], "203.0.113.9", "trusted", store.snapshot(), now)["verification"]
        == "evidence_unavailable"
    )

    def offline(request):
        raise httpx.ConnectTimeout("test timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        store.refresh(client)


def test_tokens_do_not_match_unrelated_products():
    assert identify("notKimiBot/1") is None
    assert identify("KimiBot-fake/1") is None
    assert identify("Mozilla/5.0 (compatible; KimiBot/1.0)").token == "KimiBot"
    assert mask_ip("2001:db8:1234::abcd") == "2001:0db8:1234:*:*:*:*:*"
    assert identify("Mozilla/5.0 (+https://example.com/GPTBot)") is None


@pytest.mark.parametrize(
    "token",
    [
        "GPTBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "ClaudeBot",
        "Claude-SearchBot",
        "Claude-User",
        "PerplexityBot",
        "Perplexity-User",
    ],
)
def test_additional_official_crawlers_are_identified_and_verified(
    admin, make_batch, headers, token
):
    rule = next(rule for rule in RULES if rule.token == token)
    admin.app.state.evidence.save(rule, {"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})
    response = admin.post(
        "/api/collector/batches", json=make_batch(ua=token + "/1.0"), headers=headers
    )
    assert response.status_code == 200
    event = admin.get("/api/events?days=1").json()["items"][0]
    assert event["crawler"] == token
    assert event["verification"] == "verified"


def test_shared_official_feed_is_fetched_once_per_refresh(admin):
    requests = []

    def handle(request):
        requests.append(str(request.url))
        return httpx.Response(200, json={"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        admin.app.state.evidence.refresh(client)
    assert requests.count("https://claude.com/crawling/bots.json") == 1


def test_health_distinguishes_quiet_error_disconnect_and_gap(admin, source):
    database = admin.app.state.database
    source_id = source["source_id"]
    assert health(database, source_id)["overall"] == "not_installed"
    message = Heartbeat(
        site_id=source["site_id"],
        source_id=source_id,
        instance_id="instance",
        sequence=1,
        baseline_at=datetime.now(UTC),
        state="ok",
        read_offset=0,
        acknowledged_offset=0,
        pending_bytes=0,
    )
    heartbeat(database, message, now=1000)
    assert health(database, source_id, now=1050)["overall"] == "healthy"
    assert health(database, source_id, now=1091)["overall"] == "disconnected"
    message.sequence = 2
    message.state = "read_error"
    message.error_code = "unreadable"
    heartbeat(database, message, now=1100)
    assert health(database, source_id, now=1101)["overall"] == "error"
    # Delayed duplicate heartbeat cannot overwrite a newer failure.
    heartbeat(database, message.model_copy(update={"sequence": 1, "state": "ok"}), now=1102)
    assert health(database, source_id, now=1103)["overall"] == "error"


def test_calendar_boundaries_and_install_coverage(admin, source, headers):
    now = datetime(2026, 10, 27, 17, 0, tzinfo=UTC).timestamp()
    start, end = bounds("Asia/Shanghai", 7, now=now)
    assert str(start.date()) == "2026-10-22"
    assert str(end.date()) == "2026-10-29"
    response = admin.get("/api/overview?days=30")
    assert all(day["requests"] is None for day in response.json()["trend"])
    payload = {
        "site_id": source["site_id"],
        "source_id": source["source_id"],
        "instance_id": "new",
        "sequence": 1,
        "baseline_at": datetime.now(UTC).isoformat(),
        "state": "ok",
        "read_offset": 0,
        "acknowledged_offset": 0,
        "pending_bytes": 0,
    }
    assert admin.post("/api/collector/heartbeat", json=payload, headers=headers).status_code == 200
    overview = admin.get("/api/overview?days=30").json()
    assert overview["empty_message"] == "未观察到可识别的 AI 爬虫访问"
    assert overview["trend"][-1]["coverage"] == "incomplete"
    assert all(day["coverage"] == "unobserved" for day in overview["trend"][:-1])


def test_transaction_failure_leaves_no_partial_events(admin, make_batch, headers):
    database = admin.app.state.database
    with database.transaction() as conn:
        conn.execute(
            "CREATE TRIGGER fail_event BEFORE INSERT ON events WHEN NEW.path='/fail' BEGIN SELECT RAISE(ABORT,'test rollback'); END"
        )
    payload = make_batch(count=2)
    payload["events"][1]["path"] = "/fail"
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        admin.post("/api/collector/batches", json=payload, headers=headers)
    with database.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
