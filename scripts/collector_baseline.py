"""Synthetic file-writer/collector coexistence; never measures a real website or cgroups."""

import argparse
import hashlib
import json
import platform
import tempfile
import threading
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import httpx

from internal.collector.runtime import Collector
from internal.config import CollectorConfig


def measure(rows, enabled):
    with tempfile.TemporaryDirectory(prefix="geo-monitor-collector-baseline-") as folder:
        root = Path(folder)
        log = root / "access.log"
        log.write_bytes(b"")
        config = CollectorConfig(server_url="https://synthetic.example.test", site_id="baseline",
                                 source_id="baseline", token="synthetic-token", log_path=log,
                                 state_path=root / "state.json", flush_seconds=0.05,
                                 heartbeat_seconds=0.1)
        totals = {"events": 0, "batches": 0, "heartbeats": 0, "steps": 0}
        steps = []

        def accept(request):
            body = json.loads(request.content)
            if request.url.path.endswith("batches"):
                totals["events"] += len(body["events"])
                totals["batches"] += 1
                return httpx.Response(200, json={"batch_id": body["batch_id"],
                                                "acknowledged_offset": body["end_offset"]})
            totals["heartbeats"] += 1
            return httpx.Response(200, json={"accepted": True})

        with httpx.Client(base_url=config.server_url, transport=httpx.MockTransport(accept)) as client:
            collector = Collector(config, client) if enabled else None
            stop = threading.Event()

            def collect():
                while not stop.is_set():
                    began = time.perf_counter()
                    ok = collector.step()
                    steps.append((time.perf_counter() - began) * 1000)
                    totals["steps"] += 1
                    delay = config.catchup_pause_seconds if collector.state == "backlog" else config.flush_seconds
                    stop.wait(delay if ok else 1)

            def heartbeat():
                while not stop.is_set():
                    collector.heartbeat()
                    stop.wait(config.heartbeat_seconds)

            workers = [threading.Thread(target=target, daemon=True) for target in (collect, heartbeat)] if enabled else []
            tracemalloc.start()
            cpu = time.process_time()
            elapsed = time.perf_counter()
            for worker in workers:
                worker.start()
            expected = hashlib.sha256()
            latencies = []
            stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
            try:
                with log.open("ab", buffering=0) as handle:
                    for index in range(rows):
                        raw = f'203.0.113.99 - - [{stamp}] "GET /synthetic/{index} HTTP/1.1" 200 1 "-" "KimiBot"\n'.encode()
                        expected.update(raw)
                        began = time.perf_counter()
                        handle.write(raw)
                        latencies.append((time.perf_counter() - began) * 1000)
                        time.sleep(0.001)
                deadline = time.monotonic() + 15
                while enabled and totals["events"] < rows and time.monotonic() < deadline:
                    stop.wait(0.01)
                if enabled and totals["events"] != rows:
                    raise RuntimeError("synthetic collector did not finish all rows")
            finally:
                stop.set()
                for worker in workers:
                    worker.join(5)
            wall = time.perf_counter() - elapsed
            cpu_seconds = time.process_time() - cpu
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            if hashlib.sha256(log.read_bytes()).digest() != expected.digest():
                raise RuntimeError("source file changed unexpectedly")
            state = config.state_path.read_text() if enabled else ""
            if "203.0.113.99" in state or "KimiBot" in state:
                raise RuntimeError("private source data leaked to state")
            return {"rows": rows, "collector": enabled,
                    "writer_append_p95_ms": sorted(latencies)[int((len(latencies) - 1) * 0.95)],
                    "writer_append_max_ms": max(latencies), "wall_seconds": wall,
                    "whole_process_cpu_seconds": cpu_seconds,
                    "whole_process_peak_python_allocated_bytes": peak,
                    "collector_max_step_ms": max(steps, default=0), "state_bytes": len(state),
                    "source_unchanged": True, **totals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.rows <= 10000:
        parser.error("rows must be 1–10000")
    report = {"platform": platform.platform(), "python": platform.python_version(),
              "note": "Synthetic append latencies, not website latency, RSS, cgroup enforcement or production capacity. HTTP is mocked. flush=0.05s, catchup=0.25s, heartbeat=0.1s.",
              "without_collector": measure(args.rows, False), "with_collector": measure(args.rows, True)}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
