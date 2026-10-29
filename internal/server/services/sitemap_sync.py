"""Persistent single-site Sitemap scheduling with stale-result protection."""

import secrets
import threading
import time

from internal.server.services.inventory import merge_pages
from internal.server.services.sitemap import SitemapError, collect_pages, sitemap_url

INTERVAL = 24 * 3600
LEASE_SECONDS = 300


class SitemapSync:
    def __init__(self, database, *, fetch=None):
        self.database = database
        self.fetch = fetch
        self.wake = threading.Event()
        self.stop = threading.Event()

    def status(self, site):
        with self.database.read() as conn:
            row = conn.execute(
                "SELECT * FROM sitemap_sources WHERE site_id=? AND host=?",
                (site["id"], site["domain"]),
            ).fetchone()
        result = dict(row) if row else {
            "host": site["domain"], "url": "", "enabled": False, "revision": 0,
            "state": "not_configured", "last_attempt_at": None, "last_success_at": None,
            "next_run_at": None, "last_error": None, "pages": None, "files": None, "added": None,
        }
        for private in ("site_id", "run_token", "lease_until"):
            result.pop(private, None)
        result["enabled"] = bool(result["enabled"])
        result["interval_seconds"] = INTERVAL
        return result

    def configure(self, site, url, enabled):
        url = sitemap_url(url, site["domain"])
        now = time.time()
        with self.database.transaction() as conn:
            self._assert_current(conn, site)
            conn.execute(
                """INSERT INTO sitemap_sources(site_id,host,url,enabled,revision,state,next_run_at)
                VALUES(?,?,?,?,1,?,?) ON CONFLICT(site_id,host) DO UPDATE SET
                url=excluded.url,enabled=excluded.enabled,revision=sitemap_sources.revision+1,
                state=excluded.state,next_run_at=excluded.next_run_at,run_token=NULL,lease_until=NULL,
                last_error=NULL,
                last_attempt_at=CASE WHEN url=excluded.url THEN last_attempt_at END,
                last_success_at=CASE WHEN url=excluded.url THEN last_success_at END,
                pages=CASE WHEN url=excluded.url THEN pages END,
                files=CASE WHEN url=excluded.url THEN files END,
                added=CASE WHEN url=excluded.url THEN added END""",
                (site["id"], site["domain"], url, enabled,
                 "pending" if enabled else "paused", now if enabled else None),
            )
        self.wake.set()
        return self.status(site)

    def request(self, site):
        with self.database.transaction() as conn:
            self._assert_current(conn, site)
            row = conn.execute(
                "SELECT * FROM sitemap_sources WHERE site_id=? AND host=?",
                (site["id"], site["domain"]),
            ).fetchone()
            if not row:
                raise ValueError("请先保存 Sitemap 地址")
            now = time.time()
            if row["state"] != "running" or (row["lease_until"] or 0) <= now:
                conn.execute(
                    """UPDATE sitemap_sources SET state='pending',next_run_at=?,last_error=NULL,
                    run_token=NULL,lease_until=NULL WHERE site_id=? AND host=?""",
                    (now, site["id"], site["domain"]),
                )
        self.wake.set()
        return self.status(site)

    @staticmethod
    def _assert_current(conn, site):
        row = conn.execute("SELECT domain FROM site WHERE id=?", (site["id"],)).fetchone()
        if not row or row["domain"] != site["domain"]:
            raise ValueError("官网已变更，请刷新后重新配置")

    def run_due(self):
        now = time.time()
        token = secrets.token_hex(16)
        with self.database.transaction() as conn:
            row = conn.execute(
                """SELECT s.* FROM sitemap_sources s JOIN site t ON t.id=s.site_id AND t.domain=s.host
                WHERE s.next_run_at<=? AND (s.lease_until IS NULL OR s.lease_until<=?)
                AND (s.enabled=1 OR s.state IN ('pending','running')) LIMIT 1""", (now, now),
            ).fetchone()
            if not row:
                return False
            job = dict(row)
            conn.execute(
                """UPDATE sitemap_sources SET state='running',last_attempt_at=?,run_token=?,
                lease_until=? WHERE site_id=? AND host=?""",
                (now, token, now + LEASE_SECONDS, job["site_id"], job["host"]),
            )
        try:
            pages, files = collect_pages(job["url"], job["host"], self.fetch)
            with self.database.transaction() as conn:
                if not self._current_job(conn, job, token):
                    return True
                try:
                    result = merge_pages(conn, {"id": job["site_id"], "domain": job["host"]},
                                         pages, preserve_titles=True)
                except ValueError as exc:
                    raise SitemapError(str(exc)) from None
                conn.execute(
                    """UPDATE sitemap_sources SET state='success',last_success_at=?,next_run_at=?,
                    last_error=NULL,pages=?,files=?,added=?,run_token=NULL,lease_until=NULL
                    WHERE site_id=? AND host=?""",
                    (time.time(), time.time() + INTERVAL if job["enabled"] else None,
                     result["accepted"], files, result["added"], job["site_id"], job["host"]),
                )
        except Exception as exc:
            message = str(exc) if isinstance(exc, SitemapError) else "Sitemap 获取失败，请检查网络、证书或文件格式后重试"
            with self.database.transaction() as conn:
                if self._current_job(conn, job, token):
                    conn.execute(
                        """UPDATE sitemap_sources SET state='failed',last_error=?,next_run_at=?,
                        run_token=NULL,lease_until=NULL WHERE site_id=? AND host=?""",
                        (message, time.time() + INTERVAL if job["enabled"] else None,
                         job["site_id"], job["host"]),
                    )
        return True

    @staticmethod
    def _current_job(conn, job, token):
        return conn.execute(
            """SELECT 1 FROM sitemap_sources s JOIN site t ON t.id=s.site_id AND t.domain=s.host
            WHERE s.site_id=? AND s.host=? AND s.revision=? AND s.run_token=?""",
            (job["site_id"], job["host"], job["revision"], token),
        ).fetchone() is not None

    def maintain(self):
        while not self.stop.is_set():
            self.wake.clear()
            try:
                self.run_due()
            except Exception:
                # No URLs, remote response bodies or exception values in application logs.
                pass
            self.wake.wait(30)
