import threading
import time

import pytest
from fastapi.testclient import TestClient

from internal.server.app import create_app
from internal.server.services.sitemap import SitemapError
from internal.server.services.sitemap_sync import INTERVAL, SitemapSync

BASE = "/api/inventory/sitemap"


def xml(*paths):
    return ("<urlset>" + "".join(f"<url><loc>{path}</loc></url>" for path in paths) + "</urlset>").encode()


def configure(admin, url="https://example.com/map.xml", enabled=True):
    return admin.put(BASE, json={"url": url, "enabled": enabled})


def test_save_queue_merge_and_periodic_retry_are_persistent(admin, source):
    service = admin.app.state.sitemap
    assert admin.get(BASE).json()["state"] == "not_configured"
    admin.post("/api/inventory/import", json={"format": "json", "text": '[{"path":"/a","title":"手动标题"},"/old"]'}).raise_for_status()
    saved = configure(admin).json()
    assert saved["state"] == "pending" and saved["last_success_at"] is None
    assert "run_token" not in saved and "site_id" not in saved
    service.fetch = lambda *args: xml("https://example.com/a?secret=discarded", "/new")
    assert service.run_due()
    status = admin.get(BASE).json()
    assert status["state"] == "success" and status["pages"] == 2 and status["added"] == 1
    assert status["files"] == 1 and status["next_run_at"] - status["last_success_at"] == pytest.approx(INTERVAL, abs=1)
    rows = admin.get("/api/inventory").json()["items"]
    assert {r["path"]: r["title"] for r in rows} == {"/a": "手动标题", "/new": "", "/old": ""}
    restarted = SitemapSync(service.database, fetch=lambda *args: xml("/later"))
    assert restarted.status({"id": source["site_id"], "domain": "example.com"})["url"] == saved["url"]
    assert not restarted.run_due()
    with service.database.transaction() as conn:
        conn.execute("UPDATE sitemap_sources SET next_run_at=0")
    assert restarted.run_due()
    assert admin.get("/api/inventory").json()["total"] == 4


def test_failure_preserves_directory_and_last_success_and_hides_network_secrets(admin, source):
    service = admin.app.state.sitemap
    configure(admin)
    service.fetch = lambda *args: xml("/safe")
    service.run_due()
    success = admin.get(BASE).json()["last_success_at"]
    admin.post(BASE + "/sync")
    service.fetch = lambda *args: (_ for _ in ()).throw(OSError("credential=do-not-leak"))
    service.run_due()
    status = admin.get(BASE).json()
    assert status["state"] == "failed" and status["last_success_at"] == success
    assert "do-not-leak" not in status["last_error"]
    assert status["next_run_at"] > time.time() and admin.get("/api/inventory").json()["total"] == 1


def test_bad_child_rolls_back_entire_download(admin, source):
    service = admin.app.state.sitemap
    configure(admin)
    files = {
        "https://example.com/map.xml": b"<sitemapindex><sitemap><loc>https://example.com/a.xml</loc></sitemap><sitemap><loc>https://example.com/b.xml</loc></sitemap></sitemapindex>",
        "https://example.com/a.xml": xml("/must-not-appear"),
        "https://example.com/b.xml": xml("https://evil.example/page"),
    }
    service.fetch = lambda url, *args: files[url]
    service.run_due()
    assert admin.get(BASE).json()["state"] == "failed"
    assert admin.get("/api/inventory").json()["total"] == 0


def test_directory_limit_rolls_back_merge_and_records_failure(admin, source):
    service = admin.app.state.sitemap
    with service.database.transaction() as conn:
        conn.executemany("INSERT INTO content_pages VALUES(?,?,?,?,?)", [(source["site_id"], "example.com", f"/{i}", "", time.time()) for i in range(10000)])
    configure(admin)
    service.fetch = lambda *args: xml("/overflow")
    service.run_due()
    assert "10000" in admin.get(BASE).json()["last_error"]
    assert admin.get("/api/inventory").json()["total"] == 10000


@pytest.mark.parametrize("action", ["change", "pause", "host", "change_failure"])
def test_old_result_cannot_apply_after_config_or_host_change(admin, source, action):
    service = admin.app.state.sitemap
    configure(admin)

    def fetch(*args):
        if action == "host":
            admin.put("/api/site", json={"domain": "other.example"}).raise_for_status()
        else:
            configure(admin, "https://example.com/new.xml", enabled=action != "pause").raise_for_status()
        if action == "change_failure":
            raise SitemapError("旧任务失败")
        return xml("/stale")

    service.fetch = fetch
    service.run_due()
    status = admin.get(BASE).json()
    assert status["state"] == ("not_configured" if action == "host" else "paused" if action == "pause" else "pending")
    assert status["last_success_at"] is None and not status["last_error"]
    assert admin.get("/api/inventory").json()["total"] == 0


def test_pause_and_manual_sync_do_not_schedule_automatic_requests(admin, source):
    service = admin.app.state.sitemap
    configure(admin, enabled=False)
    assert not service.run_due()
    assert admin.post(BASE + "/sync").status_code == 202
    service.fetch = lambda *args: xml("/manual")
    service.run_due()
    status = admin.get(BASE).json()
    assert status["state"] == "success" and not status["enabled"] and status["next_run_at"] is None
    assert not service.run_due()
    configure(admin, enabled=False)
    assert admin.get("/api/inventory").json()["total"] == 1


def test_active_lease_blocks_duplicate_jobs_and_expired_lease_recovers(admin, source):
    service = admin.app.state.sitemap
    configure(admin)

    def fetch(*args):
        assert not service.run_due()
        assert admin.post(BASE + "/sync").json()["state"] == "running"
        return xml("/one")

    service.fetch = fetch
    service.run_due()
    with service.database.transaction() as conn:
        conn.execute("UPDATE sitemap_sources SET state='running',next_run_at=0,lease_until=0,run_token='crashed'")
    assert service.run_due()
    assert admin.get(BASE).json()["state"] == "success"


def test_missing_config_bad_urls_and_csrf_never_queue(admin, source):
    assert admin.post(BASE + "/sync").status_code == 400
    assert configure(admin, "https://else.example/map.xml").status_code == 400
    assert configure(admin, enabled="true").status_code == 422
    assert admin.get(BASE).json()["state"] == "not_configured"
    del admin.headers["X-CSRF-Token"]
    assert configure(admin).status_code == 403
    assert admin.post(BASE + "/sync").status_code == 403
    admin.cookies.clear()
    assert admin.get(BASE).status_code == 401
    assert configure(admin).status_code == 401
    assert admin.post(BASE + "/sync").status_code == 401


def test_real_lifespan_worker_processes_saved_queue_after_restart(admin, source):
    configure(admin)
    app = create_app(admin.app.state.config, refresh_evidence=False)
    completed = threading.Event()

    def fetch(*args):
        completed.set()
        return xml("/after-restart")

    app.state.sitemap.fetch = fetch
    with TestClient(app):
        assert completed.wait(3)
        # The worker keeps running until the actual write is observed.
        for _ in range(100):
            if admin.get(BASE).json()["state"] == "success":
                break
            time.sleep(0.01)
        assert admin.get(BASE).json()["state"] == "success"
        assert admin.get("/api/inventory").json()["items"][0]["path"] == "/after-restart"
    assert app.state.sitemap.stop.is_set()
