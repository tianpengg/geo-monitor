"""Synthetic local processing baseline, never a production capacity guarantee."""

import argparse
import json
import platform
import sqlite3
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from internal.crawler.evidence import EvidenceStore
from internal.crawler.rules import RULES
from internal.protocol import Batch, batch_identity
from internal.server.services.ingest import ingest
from internal.server.services.queries import details, overview
from internal.storage.database import Database, preferred_journal_mode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=30000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.rows <= 1_000_000:
        parser.error("rows must be between 1 and 1000000")
    with tempfile.TemporaryDirectory(prefix="geo-monitor-benchmark-") as folder:
        database = Database(Path(folder) / "benchmark.sqlite3")
        database.migrate()
        store = EvidenceStore(database)
        store.save(RULES[0], {"prefixes": [{"ipv4Prefix": "203.0.113.0/24"}]})
        site = {"id": "benchmark", "source_id": "benchmark", "timezone": "Asia/Shanghai"}
        now = datetime.now(UTC)
        began = time.perf_counter()
        for start in range(0, args.rows, 1000):
            stop = min(start + 1000, args.rows)
            batch = Batch(
                site_id="benchmark",
                source_id="benchmark",
                generation="benchmark",
                start_offset=start * 256,
                end_offset=stop * 256,
                batch_id=batch_identity("benchmark", "benchmark", start * 256, stop * 256),
                events=[
                    {
                        "offset": index * 256,
                        "end_offset": (index + 1) * 256,
                        "occurred_at": now - timedelta(days=index % 30),
                        "client_ip": "203.0.113.99",
                        "method": "GET",
                        "path": f"/page/{index % 1000}",
                        "status": 200,
                        "user_agent": "KimiBot/1.0",
                    }
                    for index in range(start, stop)
                ],
            )
            ingest(database, batch, "trusted", store)
        processing_seconds = time.perf_counter() - began
        began = time.perf_counter()
        result = overview(database, site, 30, None, None, 90)
        overview_ms = (time.perf_counter() - began) * 1000
        began = time.perf_counter()
        rows = details(database, site, 30, None, None, None, None, 50)
        detail_ms = (time.perf_counter() - began) * 1000
        assert result["summary"]["requests"] == args.rows
        assert len(rows["items"]) == min(50, args.rows)
        report = {
            "kind": "synthetic-local-function-baseline",
            "recorded_at": now.isoformat(),
            "os": platform.platform(),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "journal_mode": preferred_journal_mode(sqlite3.sqlite_version_info),
            "rows": args.rows,
            "synthetic_event_bytes": 256,
            "days": 30,
            "processing_seconds": round(processing_seconds, 3),
            "events_per_second": round(args.rows / processing_seconds),
            "overview_30_days_ms": round(overview_ms, 3),
            "first_50_details_ms": round(detail_ms, 3),
            "excludes": ["real network", "Docker", "production peak", "production log retention"],
        }
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)


if __name__ == "__main__":
    main()
