"""Disposable loopback-only browser QA server, never used for deployment."""

import argparse
import json
import random
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import uvicorn
from fastapi.testclient import TestClient

from internal.config import ServerConfig
from internal.crawler.rules import RULES
from internal.protocol import batch_identity
from internal.server.app import create_app


def sitemap_fixture(url, host, deadline):
    """Explicit QA injection: no network request and never wired into production."""
    if host not in {"preview.example.test", "www.preview.example.test"}:
        raise ValueError("fixture only supports the seeded QA host")
    if url in {"https://preview.example.test/aliases.xml", "https://www.preview.example.test/sitemap.xml"}:
        return b'<urlset><url><loc>https://www.preview.example.test/products</loc></url><url><loc>https://preview.example.test/products</loc></url><url><loc>https://www.preview.example.test/about</loc></url></urlset>'
    if url == "https://preview.example.test/sitemap.xml":
        return b'<sitemapindex><sitemap><loc>https://preview.example.test/pages.xml</loc></sitemap></sitemapindex>'
    if url == "https://preview.example.test/pages.xml":
        return b'<urlset><url><loc>https://preview.example.test/docs/getting-started</loc></url><url><loc>https://preview.example.test/products</loc></url><url><loc>https://preview.example.test/about</loc></url></urlset>'
    return b'<html>invalid sitemap fixture</html>'


def seed(app, config):
    """Controlled samples go through the real ingest API, with reserved test IPs."""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    counts = [185, 244, 310, 365, 342, 421, 501]
    agents = [
        ("KimiBot", 640), ("GPTBot", 528), ("ClaudeBot", 410),
        ("OAI-SearchBot", 310), ("Bytespider", 220), ("HySpider", 100),
        ("Kimi-SearchBot", 80), ("Claude-SearchBot", 50), ("ChatGPT-User", 30),
    ]
    names = [token for token, count in agents for _ in range(count)]
    random.Random(42).shuffle(names)
    rules = {rule.token: rule for rule in RULES}
    with TestClient(app) as client:
        session = client.post("/api/auth/login", json={
            "username": "admin", "password": config.admin_password.get_secret_value(),
        }).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        client.put("/api/site", json={"domain": "preview.example.test", "client_ip_mode": "trusted"}).raise_for_status()
        source = client.post("/api/site/credentials").json()
        fixture = json.loads(Path("tests/fixtures/evidence.json").read_text())
        for rule in RULES:
            if rule.evidence_url:
                app.state.evidence.save(rule, fixture)
        events = []
        verified = 0
        for day_index, count in enumerate(counts):
            day = today - timedelta(days=6 - day_index)
            for index in range(count):
                position = len(events)
                token = names[position]
                if rules[token].evidence_url and verified < 1824:
                    address = "203.0.113.12"
                    verified += 1
                else:
                    address = "198.51.100.12"
                start = day + timedelta(hours=9) if day_index < 6 else max(today, now - timedelta(hours=2))
                stop = day + timedelta(hours=10) if day_index < 6 else now
                occurred = start + (stop - start) * index / count
                path = "/docs/getting-started" if position % 126 == 0 else "/blog/ai-search" if position % 126 == 1 else f"/docs/topic-{position % 126:03}"
                events.append({
                    "offset": position * 100, "end_offset": (position + 1) * 100,
                    "occurred_at": occurred.isoformat(), "client_ip": address,
                    "method": "HEAD" if position % 19 == 0 else "GET", "path": path,
                    "status": 403 if position % 17 == 0 else 304 if position % 11 == 0 else 200,
                    "user_agent": f"{token}/1.0",
                })
        for start_index in range(0, len(events), 800):
            part = events[start_index:start_index + 800]
            first, last = part[0]["offset"], part[-1]["end_offset"]
            client.post("/api/collector/batches", headers={"Authorization": f"Bearer {source['token']}"}, json={
                "version": 1, "site_id": source["site_id"], "source_id": source["source_id"],
                "generation": "browser-fixture", "start_offset": first, "end_offset": last,
                "batch_id": batch_identity(source["source_id"], "browser-fixture", first, last),
                "events": part,
            }).raise_for_status()
        client.post("/api/collector/heartbeat", headers={"Authorization": f"Bearer {source['token']}"}, json={
            "version": 1, "site_id": source["site_id"], "source_id": source["source_id"],
            "instance_id": "browser-fixture", "sequence": 1,
            "baseline_at": (today - timedelta(days=7)).isoformat(), "state": "ok",
            "read_offset": len(events) * 100, "acknowledged_offset": len(events) * 100,
            "pending_bytes": 0, "parse_errors": 0,
        }).raise_for_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument("--heartbeat-timeout", type=int, default=2)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--sitemap-fixture", action="store_true", help="Controlled Sitemap browser QA only")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="geo-monitor-browser-") as directory:
        config = ServerConfig(
            database=Path(directory) / "monitor.sqlite3",
            admin_password="synthetic-browser-password-2026",
            public_url=f"http://127.0.0.1:{args.port}",
            cookie_secure=False,
            evidence_enabled=False,
            heartbeat_timeout=args.heartbeat_timeout,
        )
        app = create_app(config)
        if args.sitemap_fixture:
            app.state.sitemap.fetch = sitemap_fixture
        if args.seed:
            seed(app, config)
        print(f"BROWSER_QA_DATABASE={config.database}", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
