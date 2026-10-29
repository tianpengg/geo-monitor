import csv
import io
import json
import time
from datetime import UTC, datetime, timedelta

import pytest

from internal.server.services import analytics, inventory
from internal.storage.database import MIGRATIONS, Database


def samples(admin, make_batch, headers):
    for index, (path, status, ua) in enumerate(
        [
            ("/docs/a?private=secret", 200, "KimiBot"),
            ("/docs/a", 403, "KimiBot"),
            ("/docs/ab", 403, "GPTBot"),
            ("/docs/100%_done", 304, "KimiBot"),
        ]
    ):
        response = admin.post(
            "/api/collector/batches",
            headers=headers,
            json=make_batch(start=index * 100, path=path, status=status, ua=ua),
        )
        assert response.status_code == 200


def test_shared_filters_pages_details_and_export(admin, source, make_batch, headers):
    samples(admin, make_batch, headers)
    params = {
        "days": 1,
        "crawler": "KimiBot",
        "q": "/docs/",
        "status": "4xx",
        "verification": "evidence_unavailable",
    }
    events = admin.get("/api/events", params=params).json()["items"]
    pages = admin.get("/api/pages", params=params).json()
    assert len(events) == pages["summary"]["requests"] == 1
    assert pages["items"][0]["path"] == "/docs/a"
    detail = admin.get("/api/pages/detail", params={**params, "path": "/docs/a"}).json()
    assert detail["summary"]["requests"] == 1
    assert detail["statuses"] == [{"status": 403, "requests": 1}]
    assert detail["crawlers"][0]["crawler"] == "KimiBot"
    result = admin.get("/api/events/export", params={**params, "cursor": "ignored", "limit": 1})
    assert result.status_code == 200
    rows = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["path"] == events[0]["path"]
    assert rows[0]["timezone"] == "Asia/Shanghai" and "CDN" in rows[0]["origin_note"]
    assert rows[0]["product_attribution"] == "Kimi"
    assert rows[0]["evidence_source"].startswith("https://")
    assert "203.0.113.99" not in result.text and "private" not in result.text
    assert "no-store" in result.headers["cache-control"]
    assert (
        admin.get("/api/events", params={"q": "%_"}).json()["items"][0]["path"] == "/docs/100%_done"
    )
    assert len(admin.get("/api/events", params={"path": "/docs/a"}).json()["items"]) == 2
    assert admin.get("/api/pages", params={"q": "' OR 1=1--"}).json()["total"] == 0
    all_pages = admin.get("/api/pages?days=1&limit=1").json()
    assert all_pages["items"][0]["path"] == "/docs/a" and all_pages["total"] == 3
    assert len(admin.get("/api/events/export").content.decode("utf-8-sig").splitlines()) == 5


@pytest.mark.parametrize(
    "params",
    [
        {"status": "600"},
        {"status": "all"},
        {"verification": "pretend"},
        {"q": "a" * 201},
        {"path": "evil"},
        {"q": "\x00"},
        {"start": "bad", "end": "bad"},
    ],
)
def test_invalid_shared_filter_rejected(admin, source, params):
    for endpoint in ["/api/events", "/api/pages", "/api/inventory", "/api/events/export"]:
        assert admin.get(endpoint, params=params).status_code == 400


def test_exports_escape_formulas_and_enforce_limits(
    admin, source, make_batch, headers, monkeypatch
):
    admin.post("/api/collector/batches", headers=headers, json=make_batch())
    with admin.app.state.database.transaction() as conn:
        conn.execute("UPDATE events SET name='  =SUM(1,2)'")
    rows = list(
        csv.DictReader(io.StringIO(admin.get("/api/events/export").content.decode("utf-8-sig")))
    )
    assert rows[0]["name"] == "'  =SUM(1,2)"
    monkeypatch.setattr(analytics, "EXPORT_BYTES", 30)
    response = admin.get("/api/events/export")
    assert response.status_code == 400 and "20 MiB" in response.json()["detail"]


def test_actual_export_row_boundary(admin, source, make_batch, headers):
    admin.post("/api/collector/batches", headers=headers, json=make_batch())
    database = admin.app.state.database
    with database.transaction() as conn:
        row = dict(conn.execute("SELECT * FROM events LIMIT 1").fetchone())
        conn.execute("DELETE FROM events")
        sql = f"INSERT INTO events({','.join(row)}) VALUES({','.join('?' for _ in row)})"
        conn.executemany(
            sql, [tuple({**row, "id": f"{index:064x}"}.values()) for index in range(10000)]
        )
    assert admin.get("/api/events/export").status_code == 200
    with database.transaction() as conn:
        row["id"] = f"{10000:064x}"
        conn.execute(sql, tuple(row.values()))
    response = admin.get("/api/events/export")
    assert response.status_code == 400 and "10000" in response.json()["detail"]


def upload(admin, format, text):
    return admin.post("/api/inventory/import", json={"format": format, "text": text})


def test_inventory_formats_merge_and_host_isolation(admin, source, make_batch, headers):
    samples(admin, make_batch, headers)
    assert (
        upload(
            admin,
            "xml",
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/docs/a?q=private#part</loc></url></urlset>',
        ).json()["added"]
        == 1
    )
    result = upload(admin, "csv", "url,title\nhttps://example.com/docs/a,文档\n/new,新页面\n")
    assert result.json() == {"accepted": 2, "added": 1, "updated": 1, "total": 2}
    assert upload(admin, "json", '["/new",{"path":"/last","title":"最后"}]').json()["total"] == 3
    result = admin.get("/api/inventory?days=1").json()
    assert result["summary"] == {"pages": 3, "observed": 1, "unobserved": 2, "ratio": 1 / 3}
    observed = admin.get("/api/inventory?state=observed").json()
    assert observed["items"][0]["title"] == "文档"
    assert observed["items"][0]["requests"] == 2
    assert (
        admin.get("/api/inventory?state=unobserved&limit=1&offset=1").json()["items"][0]["path"]
        == "/new"
    )
    assert admin.get("/api/inventory?crawler=GPTBot").json()["summary"]["observed"] == 0
    assert admin.delete("/api/inventory", params={"path": "/new"}).json()["removed"]
    admin.put("/api/site", json={"domain": "other.example.com"})
    assert admin.get("/api/inventory").json()["summary"]["ratio"] is None
    admin.put("/api/site", json={"domain": "example.com"})
    assert admin.get("/api/inventory").json()["total"] == 2


@pytest.mark.parametrize(
    "format,text",
    [
        ("json", '["/good","https://evil.example/a"]'),
        ("json", '["https://example.com:444/a"]'),
        ("json", '["https://name:secret@example.com/a"]'),
        ("json", '["//evil.example/a"]'),
        ("json", "[42]"),
        ("json", "{}"),
        ("json", "[]"),
        ("json", "["),
        ("csv", "title\nmissing path"),
        (
            "xml",
            "<sitemapindex><sitemap><loc>https://example.com/other.xml</loc></sitemap></sitemapindex>",
        ),
        ("xml", '<!DOCTYPE urlset [<!ENTITY x "private">]><urlset/>'),
        ("xml", "<urlset><url/></urlset>"),
    ],
)
def test_inventory_invalid_input_is_atomic(admin, source, format, text):
    assert upload(admin, "json", '["/existing"]').status_code == 200
    assert upload(admin, format, text).status_code == 400
    assert admin.get("/api/inventory").json()["total"] == 1


def test_inventory_limits(admin, source):
    assert upload(admin, "json", json.dumps([f"/{n}" for n in range(10000)])).status_code == 200
    assert upload(admin, "json", '["/extra"]').status_code == 400
    assert admin.get("/api/inventory").json()["total"] == 10000
    with pytest.raises(ValueError):
        inventory.parse_inventory(" " * (1024 * 1024 + 1), "json", "example.com")
    assert upload(admin, "json", json.dumps(["/"] * 10001)).status_code == 400


def test_inventory_observation_limits(admin, source):
    upload(admin, "json", '["/a"]')
    assert admin.get("/api/inventory").json()["observation"]["state"] == "unobserved"
    now = time.time()
    with admin.app.state.database.transaction() as conn:
        conn.execute(
            "INSERT INTO collector_health(source_id,heartbeat_at,baseline_at,state) VALUES(?,?,?,'ok')",
            (source["source_id"], now, now - 10 * 86400),
        )
    assert admin.get("/api/inventory?days=7").json()["observation"]["state"] == "observed"
    old = (datetime.now(UTC) - timedelta(days=40)).date().isoformat()
    future = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    assert (
        admin.get("/api/inventory", params={"start": future, "end": future}).json()["observation"][
            "state"
        ]
        == "unobserved"
    )
    with admin.app.state.database.transaction() as conn:
        conn.execute("UPDATE collector_health SET baseline_at=?", (now - 60 * 86400,))
    result = admin.get("/api/inventory", params={"start": old, "end": old}).json()
    assert "保留" in result["observation"]["note"]
    with admin.app.state.database.transaction() as conn:
        conn.execute("UPDATE collector_health SET parse_errors=1")
    assert admin.get("/api/inventory").json()["observation"]["state"] == "incomplete"


def test_new_routes_require_admin_and_csrf(client, source, headers):
    client.cookies.clear()
    for path in ["/api/pages", "/api/pages/detail?path=/", "/api/events/export", "/api/inventory"]:
        assert client.get(path, headers=headers).status_code == 401
    assert upload(client, "json", '["/"]').status_code == 401


def test_upgrade_preserves_existing_facts(tmp_path):
    database = Database(tmp_path / "old.db")
    database.migrate(MIGRATIONS[:1])
    with database.transaction() as conn:
        conn.execute("INSERT INTO admin VALUES(1,'original','hash')")
    database.migrate()
    database.migrate()
    with database.read() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        assert conn.execute("SELECT username FROM admin").fetchone()[0] == "original"
        assert conn.execute("SELECT COUNT(*) FROM content_pages").fetchone()[0] == 0


def test_inventory_mutations_require_csrf(admin, source):
    del admin.headers["X-CSRF-Token"]
    assert upload(admin, "json", '["/a"]').status_code == 403
    assert admin.delete("/api/inventory", params={"path": "/a"}).status_code == 403
    assert admin.get("/api/inventory").json()["total"] == 0
