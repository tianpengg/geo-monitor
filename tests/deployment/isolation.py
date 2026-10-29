"""Fault checks for disposable acceptance collectors only; never a production tool."""

import errno
import hashlib
import json
import math
import threading
import time

import httpx

ORIGIN = r"""
import sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_): pass
    def do_GET(self):
        rows = 4000 if urlsplit(self.path).path == "/burst" else 1
        stamp = time.strftime("%d/%b/%Y:%H:%M:%S +0000", time.gmtime())
        raw = ('203.0.113.55 - - [' + stamp + '] "GET /isolation-origin HTTP/1.1" '
               '200 2 "-" "GeoMonitor-Synthetic-Origin/1.0"\n').encode()
        with open(sys.argv[1], "ab", buffering=0) as output:
            output.write(raw * rows)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
"""

METRICS = r"""
import json
from pathlib import Path
root = Path("/sys/fs/cgroup")
if not (root / "cgroup.controllers").is_file():
    raise RuntimeError("Resource acceptance requires a cgroup v2 Linux runner")
def pairs(name):
    return {key: int(value) for key, value in
            (line.split() for line in (root / name).read_text().splitlines())}
io = {"rbytes": 0, "wbytes": 0}
for line in (root / "io.stat").read_text().splitlines():
    for part in line.split()[1:]:
        key, value = part.split("=", 1)
        if key in io: io[key] += int(value)
rss = next(int(line.split()[1]) * 1024 for line in
           Path("/proc/1/status").read_text().splitlines() if line.startswith("VmRSS:"))
print(json.dumps({"cpu_max": (root / "cpu.max").read_text().strip(),
    "memory_max": int((root / "memory.max").read_text()),
    "pids_max": int((root / "pids.max").read_text()),
    "memory_current": int((root / "memory.current").read_text()),
    "pid1_rss_bytes": rss, "cpu": pairs("cpu.stat"), "io": io}))
"""

WRITE_PROBES = r"""
import errno, json, os
from pathlib import Path
results = {}
for label, name in (("root", "/isolation-write-probe"), ("source", "/logs/example.com.log")):
    try:
        fd = os.open(name, os.O_WRONLY | (os.O_CREAT if label == "root" else os.O_APPEND), 0o600)
    except OSError as exc:
        results[label] = exc.errno
    else:
        os.close(fd)
        results[label] = 0
scratch = Path("/state/.isolation-write-probe")
scratch.write_text("synthetic-state-probe")
results["state_writable"] = scratch.read_text() == "synthetic-state-probe"
scratch.unlink()
print(json.dumps(results))
"""

CPU_LOAD = "import time; end=time.monotonic()+2; x=0\nwhile time.monotonic()<end: x=(x+1)%1000003"
OOM_LOAD = r"""
from pathlib import Path
# Prefer the collector's PID 1 as this disposable cgroup's OOM victim. No host changes.
Path("/proc/1/oom_score_adj").write_text("1000")
blocks = []
for _ in range(40):
    block = bytearray(8 * 1024 * 1024)
    for index in range(0, len(block), 4096): block[index] = 1
    blocks.append(block)
"""


def require_disposable(inspection, project):
    """Reject normal projects before any CPU or OOM operation is possible."""
    if not project.startswith("geo-monitor-check-") or len(project) < 28:
        raise ValueError("Only a minted acceptance project may run fault checks")
    labels = inspection.get("Config", {}).get("Labels", {})
    if labels.get("com.docker.compose.project") != project + "-installed":
        raise ValueError("Collector does not belong to this disposable project")
    if labels.get("com.docker.compose.service") != "collector":
        raise ValueError("Fault target must be the acceptance collector")


def summarize(samples):
    if not samples or any(not math.isfinite(elapsed) or elapsed < 0 for elapsed, _ in samples):
        raise ValueError("Probe needs finite, nonnegative measured samples")
    times = sorted(elapsed for elapsed, _ in samples)
    errors = sum(not ok for _, ok in samples)
    return {
        "requests": len(samples),
        "errors": errors,
        "error_rate": errors / len(samples),
        "p95_ms": round(times[math.ceil(len(times) * 0.95) - 1] * 1000, 3),
        "max_ms": round(times[-1] * 1000, 3),
    }


def run_checks(
    *, command, wait_for, collector_id, control, state, get, root, project, network, report
):
    docker = "/usr/local/bin/docker-real"
    source = root / "www/wwwlogs/example.com.log"
    origin_name = project + "-origin"
    report.update(kind="synthetic-http-origin-with-real-collector", cgroup_version=2)

    def inspect(target=None):
        value = json.loads(command(docker, "inspect", target or collector_id()))[0]
        if target is None:
            require_disposable(value, project)
        return value

    def execute(code):
        require_disposable(inspect(), project)
        return command(docker, "exec", collector_id(), "python", "-c", code)

    def metrics():
        return json.loads(execute(METRICS))

    inspection = inspect()
    host = inspection["HostConfig"]
    assert host["NanoCpus"] == 250_000_000 and host["Memory"] == 128 * 1024 * 1024
    assert host["PidsLimit"] == 64 and host["ReadonlyRootfs"] is True
    assert host["LogConfig"] == {"Type": "json-file", "Config": {"max-size": "5m", "max-file": "2"}}
    assert not host["Privileged"] and not host["PortBindings"] and host["NetworkMode"] != "host"
    assert not any("docker.sock" in item["Destination"] for item in inspection["Mounts"])
    before = hashlib.sha256(source.read_bytes()).digest()
    writes = json.loads(execute(WRITE_PROBES))
    assert writes == {"root": errno.EROFS, "source": errno.EROFS, "state_writable": True}
    assert hashlib.sha256(source.read_bytes()).digest() == before
    initial = metrics()
    quota, period = map(int, initial["cpu_max"].split())
    assert quota / period == 0.25
    assert initial["memory_max"] == 128 * 1024 * 1024 and initial["pids_max"] == 64
    execute(CPU_LOAD)
    throttled = metrics()["cpu"]["nr_throttled"] - initial["cpu"]["nr_throttled"]
    assert throttled > 0
    report["limits"] = {
        "cpu": 0.25,
        "memory_bytes": initial["memory_max"],
        "pids": 64,
        "cpu_throttled_periods": throttled,
        "write_probes": writes,
        "log_max_size": "5m",
        "log_max_files": 2,
    }
    initial_state = state()
    initial_total = get("/api/overview?days=1")["summary"]["requests"]
    baseline_at = initial_state["baseline_at"]
    source_id = initial_state["source_id"]
    origin_id = command(
        docker,
        "run",
        "-d",
        "--name",
        origin_name,
        "--network",
        network,
        "--label",
        "com.docker.compose.project=" + project,
        "--read-only",
        "--memory",
        "64m",
        "--cpus",
        "0.5",
        "--pids-limit",
        "32",
        "--mount",
        f"type=bind,src={source.parent},dst=/logs",
        "python:3.13-slim-bookworm",
        "python",
        "-u",
        "-c",
        ORIGIN,
        "/logs/example.com.log",
    )
    try:
        with httpx.Client(
            base_url=f"http://{origin_name}:8080", timeout=3, trust_env=False
        ) as origin:
            wait_for(lambda: origin.get("/").status_code == 200, label="synthetic origin startup")
            origin_started_at = inspect(origin_id)["State"]["StartedAt"]

            def probe(samples, stop=None, limit=30):
                for _ in range(limit):
                    if stop is not None and stop.is_set():
                        break
                    start = time.perf_counter()
                    try:
                        ok = origin.get("/").status_code == 200
                    except httpx.HTTPError:
                        ok = False
                    samples.append((time.perf_counter() - start, ok))
                    time.sleep(0.05)

            control("stop")
            samples = []
            probe(samples)
            report["collector_stopped"] = summarize(samples)
            control("reconnect")
            wait_for(lambda: inspect()["State"]["Running"], label="collector restarted")
            assert state()["baseline_at"] == baseline_at
            origin.get("/burst").raise_for_status()
            first = metrics()
            began = time.monotonic()
            samples = []
            probe(samples, limit=60)
            last = metrics()
            elapsed = time.monotonic() - began
            report["collector_catching_up"] = summarize(samples)
            report["active_resources"] = {
                "window_seconds": round(elapsed, 3),
                "cpu_one_core_percent": round(
                    (last["cpu"]["usage_usec"] - first["cpu"]["usage_usec"]) / elapsed / 10000, 3
                ),
                "memory_current_bytes": last["memory_current"],
                "collector_pid1_rss_bytes": last["pid1_rss_bytes"],
                "read_bytes": max(0, last["io"]["rbytes"] - first["io"]["rbytes"]),
                "write_bytes": max(0, last["io"]["wbytes"] - first["io"]["wbytes"]),
            }
            # Docker restart policies require a successfully started container; allow >= 12 s.
            time.sleep(12)
            identifier = collector_id()
            restarted_before = inspect()["RestartCount"]
            event_start = str(int(time.time()) - 1)
            stop = threading.Event()
            samples = []
            worker = threading.Thread(target=probe, args=(samples, stop, 1200), daemon=True)
            worker.start()
            try:
                try:
                    execute(OOM_LOAD)
                except RuntimeError:
                    # An interrupted exec is insufficient: require an actual OOM event and restart.
                    pass
                wait_for(
                    lambda: (
                        inspect()["RestartCount"] > restarted_before
                        and inspect()["State"]["Running"]
                    ),
                    timeout=45,
                    label="collector PID1 auto-restart after real OOM",
                )
            finally:
                stop.set()
                worker.join(timeout=5)
            assert not worker.is_alive()
            events = command(
                docker,
                "events",
                "--since",
                event_start,
                "--until",
                str(int(time.time()) + 1),
                "--filter",
                "container=" + identifier,
                "--filter",
                "event=oom",
                "--format",
                "{{json .}}",
            ).splitlines()
            assert events, "A manual kill must never count as a real OOM"
            report["during_oom"] = summarize(samples)
            report["oom"] = {
                "events": len(events),
                "automatic_restarts": inspect()["RestartCount"] - restarted_before,
            }
            assert inspect(origin_id)["State"]["StartedAt"] == origin_started_at
            assert (
                inspect(origin_id)["RestartCount"] == 0 and inspect(origin_id)["State"]["Running"]
            )
            stamp = time.strftime("%d/%b/%Y:%H:%M:%S +0000", time.gmtime())
            raw = f'203.0.113.99 - - [{stamp}] "GET /isolation-after-oom HTTP/1.1" 200 1 "-" "KimiBot/1.0"\n'.encode()
            with source.open("ab") as output:
                output.write(raw)
            wait_for(
                lambda: get("/api/overview?days=1")["summary"]["requests"] == initial_total + 1,
                timeout=65,
                label="new event after OOM recovery",
            )
            assert state()["baseline_at"] == baseline_at
            assert state()["source_id"] == source_id
            previous_heartbeat = get("/api/collector/health")["heartbeat_at"]
            control("reconnect")
            wait_for(
                lambda: get("/api/collector/health")["heartbeat_at"] != previous_heartbeat,
                label="new heartbeat after reconnect",
            )
            time.sleep(3)
            assert get("/api/overview?days=1")["summary"]["requests"] == initial_total + 1
            assert state()["baseline_at"] == baseline_at
            report["recovery"] = {
                "new_unique_events": 1,
                "baseline_preserved": True,
                "replay_duplicated": False,
            }
            for name in ("collector_stopped", "collector_catching_up", "during_oom"):
                assert report[name]["errors"] == 0
            report["origin_process_preserved"] = True
            report["measurement_limits"] = (
                "Synthetic Python HTTP origin; bounded samples, no production SLA. "
                "Cgroup measurements include probe exec overhead; IO may hit page cache."
            )
    finally:
        command(docker, "rm", "-f", origin_id)
    return report
