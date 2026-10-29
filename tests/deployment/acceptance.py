"""Linux acceptance against real containers, HTTP(S), files and production scripts.

Only fixtures use a local CA, fixed evidence and a response-loss proxy. No insecure
TLS option or fault-injection route is added to the shipped application.
"""

import hashlib
import json
import os
import pty
import secrets
import select
import shutil
import socket
import ssl
import subprocess
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from isolation import run_checks

from internal.crawler.rules import RULES

ROOT = Path(os.environ["ACCEPTANCE_DIRECTORY"])
PROJECT = os.environ["ACCEPTANCE_PROJECT"]
NETWORK = os.environ["ACCEPTANCE_NETWORK"]
COLLECTOR_PROJECT = PROJECT + "-installed"
PROTOCOL = os.environ.get("ACCEPTANCE_PROTOCOL", "https")
ORIGIN = f"{PROTOCOL}://acceptance:8443"
DOCKER = "/usr/local/bin/docker-real"
REPORT = {
    "checks": [],
    "kind": "linux-container-acceptance",
    "started_at": datetime.now(UTC).isoformat(),
    "protocol": PROTOCOL,
}


def command(*args, env=None, timeout=240):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Never include arguments/environment, which may contain bootstrap credentials.
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-2500:]}")
    return result.stdout.strip()


def wait_for(predicate, timeout=65, label="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except (httpx.HTTPError, FileNotFoundError):
            pass
        time.sleep(0.5)
    raise AssertionError(f"Timed out: {label}")


def passed(label):
    REPORT["checks"].append(label)
    print("PASS " + label, flush=True)


def log_line(path, ua="KimiBot/1.0", address="203.0.113.99", status=200):
    stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{address} - - [{stamp}] "GET {path} HTTP/1.1" {status} 1 "-" "{ua}"\n'.encode()


class Proxy(BaseHTTPRequestHandler):
    lose_next_batch = False
    lost = threading.Event()
    batches = []

    def log_message(self, *_):
        pass

    def forward(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        batch = self.path.endswith("/batches")
        if batch:
            type(self).batches.append(json.loads(body)["batch_id"])
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "connection", "accept-encoding"}
        }
        headers["Accept-Encoding"] = "identity"
        try:
            with httpx.Client(timeout=20, trust_env=False) as backend:
                response = backend.request(
                    self.command, "http://monitor:8000" + self.path, content=body, headers=headers
                )
        except httpx.HTTPError:
            self.send_error(503)
            return
        if batch and type(self).lose_next_batch and response.is_success:
            type(self).lose_next_batch = False
            type(self).lost.set()
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            if key.lower() not in {
                "content-length",
                "connection",
                "transfer-encoding",
                "content-encoding",
            }:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(response.content)))
        self.end_headers()
        self.wfile.write(response.content)

    do_GET = do_POST = do_PUT = forward


def install(script, credentials, log, env):
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(
            "/bin/bash",
            ["bash", str(script), ORIGIN, credentials["site_id"], credentials["source_id"]],
            env,
        )
    output = b""
    sent_path = sent_token = False
    deadline = time.monotonic() + 240
    try:
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.5)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                if not sent_path and b"Combined access log: " in output:
                    os.write(fd, (str(log) + "\n").encode())
                    sent_path = True
                if not sent_token and b"credential (hidden): " in output:
                    os.write(fd, (credentials["token"] + "\n").encode())
                    sent_token = True
            if os.waitpid(pid, os.WNOHANG)[0]:
                pid = None
                break
        else:
            raise RuntimeError("Installer timed out")
        if pid is not None:
            _, status = os.waitpid(pid, 0)
            pid = None
            if os.waitstatus_to_exitcode(status):
                raise RuntimeError(
                    "Installer failed: "
                    + output.decode(errors="replace")[-3500:].replace(
                        credentials["token"], "[redacted]"
                    )
                )
        assert sent_path and sent_token and b"Collector installed." in output
        assert credentials["token"].encode() not in output
    finally:
        if pid:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        os.close(fd)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    os.chmod(ROOT, 0o700)
    ca = ROOT / "ca.crt"
    key = ROOT / "tls.key"
    proxy = ThreadingHTTPServer(("0.0.0.0", 8443), Proxy)
    if PROTOCOL == "https":
        command(
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=Geo Monitor Acceptance",
            "-addext",
            "subjectAltName=DNS:acceptance,DNS:localhost,IP:127.0.0.1",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-keyout",
            str(key),
            "-out",
            str(ca),
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(ca, key)
        proxy.socket = context.wrap_socket(proxy.socket, server_side=True)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    install_root = ROOT / "installed"
    override = ROOT / "collector-test.yaml"
    override.write_text(
        json.dumps(
            {
                "services": {
                    "collector": {
                        "image": PROJECT + "-installed-image",
                        **(
                            {
                                "environment": {"SSL_CERT_FILE": "/acceptance/ca.crt"},
                                "volumes": [f"{ca}:/acceptance/ca.crt:ro"],
                            }
                            if PROTOCOL == "https"
                            else {}
                        ),
                    }
                },
                "networks": {"default": {"external": True, "name": NETWORK}},
            }
        )
    )
    bin_dir = ROOT / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "docker"
    wrapper.write_text('#!/bin/sh\nexec python /acceptance-tests/docker_wrapper.py "$@"\n')
    wrapper.chmod(0o700)
    password = secrets.token_urlsafe(24)
    env = os.environ | {
        "PATH": str(bin_dir) + ":" + os.environ["PATH"],
        "GEO_ADMIN_PASSWORD": password,
        "GEO_PUBLIC_URL": ORIGIN,
        "GEO_COOKIE_SECURE": str(PROTOCOL == "https").lower(),
        "GEO_INSTALL_ROOT": str(install_root),
        "CURL_CA_BUNDLE": str(ca),
        "ACCEPTANCE_COLLECTOR_PROJECT": COLLECTOR_PROJECT,
        "ACCEPTANCE_COLLECTOR_OVERRIDE": str(override),
    }
    monitor_override = ROOT / "monitor-test.yaml"
    monitor_override.write_text(
        f"services:\n  monitor:\n    image: {os.environ['ACCEPTANCE_MONITOR_IMAGE']}\n    ports: !reset []\n    environment:\n      GEO_EVIDENCE_REFRESH: 'false'\nnetworks:\n  default:\n    external: true\n    name: {NETWORK}\n"
    )
    compose = [
        DOCKER,
        "compose",
        "-p",
        PROJECT,
        "-f",
        "/acceptance-tests/monitor.compose.yaml",
        "-f",
        str(monitor_override),
    ]

    def monitor(*args):
        return command(*compose, *args, env=env)

    def control(action):
        return command(
            "bash",
            str(install_root / "scripts/collector-control.sh"),
            str(install_root),
            action,
            env=env,
        )

    def collector_id():
        return command(
            DOCKER,
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={COLLECTOR_PROJECT}",
            "--filter",
            "label=com.docker.compose.service=collector",
            "--filter",
            "label=com.docker.compose.oneoff=False",
        )

    def state():
        return json.loads(
            command(
                DOCKER,
                "run",
                "--rm",
                "--volumes-from",
                collector_id(),
                "python:3.13-slim-bookworm",
                "python",
                "-c",
                "from pathlib import Path; print(Path('/state/state.json').read_text())",
            )
        )

    def collector_volume():
        mounts = json.loads(command(DOCKER, "inspect", collector_id()))[0]["Mounts"]
        return next(item["Name"] for item in mounts if item["Destination"] == "/state")

    log = ROOT / "www/wwwlogs/example.com.log"
    log.parent.mkdir(parents=True)
    log.write_bytes(log_line("/before-install"))
    # Exercise the documented Baota-style path without requiring a running panel.
    Path("/www").mkdir(exist_ok=True)
    Path("/www/wwwlogs").symlink_to(log.parent, target_is_directory=True)
    monitor("up", "-d", "--no-build", "monitor")
    tls = ssl.create_default_context(cafile=str(ca)) if PROTOCOL == "https" else True
    with httpx.Client(
        base_url=f"{PROTOCOL}://localhost:8443", verify=tls, timeout=10, trust_env=False
    ) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def login():
            response = client.post(
                "/api/auth/login", json={"username": "admin", "password": password}
            )
            response.raise_for_status()
            assert ("Secure" in response.headers["set-cookie"]) == (PROTOCOL == "https")
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
            assert client.get("/api/auth/me").is_success

        def count():
            return get("/api/overview?days=1")["summary"]["requests"]

        def await_count(expected):
            wait_for(lambda: count() == expected, label=f"unique total {expected}")

        def append(path, **kwargs):
            with log.open("ab") as handle:
                handle.write(log_line(path, **kwargs))

        wait_for(lambda: client.get("/api/healthz").is_success, label="monitor startup")
        assert 'type="module"' in client.get("/").text
        login()
        client.put(
            "/api/site", json={"domain": "example.com", "client_ip_mode": "trusted"}
        ).raise_for_status()
        credentials_response = client.post("/api/site/credentials")
        credentials_response.raise_for_status()
        credentials = credentials_response.json()
        site_before = get("/api/site")
        # Controlled official-format snapshots, not assertions about real platform IPs.
        seed = "from internal.storage.database import Database; from internal.crawler.evidence import EvidenceStore; from internal.crawler.rules import RULES; store=EvidenceStore(Database('/app/data/monitor.sqlite3')); [store.save(rule, {'prefixes':[{'ipv4Prefix':'203.0.113.0/24'}]}) for rule in RULES if rule.evidence_url]"
        monitor("exec", "-T", "monitor", "python", "-c", seed)
        script = ROOT / "install-collector.sh"
        script.write_bytes(client.get("/downloads/install-collector.sh").raise_for_status().content)
        install(script, credentials, Path("/www/wwwlogs/example.com.log"), env)
        assert (install_root / "collector.json").stat().st_mode & 0o777 == 0o600
        assert json.loads((install_root / "collector.json").read_text())["allow_http"] == (
            PROTOCOL == "http"
        )
        wait_for(
            lambda: get("/api/collector/health")["overall"] == "healthy",
            label="installed collector heartbeat",
        )
        baseline = state()["baseline_at"]
        assert count() == 0
        append("/human", ua="Mozilla/5.0")
        wait_for(
            lambda: get("/api/collector/health").get("log_received_at"),
            label="ordinary request processed",
        )
        assert get("/api/overview?days=1")["empty_message"] == "未观察到可识别的 AI 爬虫访问"
        passed(
            f"{PROTOCOL.upper()} installer, preflight, native Linux permissions, initial EOF, healthy empty state"
        )

        started = time.monotonic()
        for rule in RULES:
            append("/rule/" + rule.token + "?private=removed", ua=rule.token + "/1.0", status=403)
        append("/mismatch", address="198.51.100.99")
        append("/unknown", ua="UnlistedSpider/1.0")
        expected = len(RULES) + 1
        await_count(expected)
        REPORT["normal_visible_seconds"] = round(time.monotonic() - started, 3)
        assert REPORT["normal_visible_seconds"] < 60
        items = get("/api/events?days=1")["items"]
        assert {item["crawler"] for item in items} == {rule.token for rule in RULES}
        assert len({item["id"] for item in items}) == expected
        for item in items:
            assert "?" not in item["path"] and item["masked_ip"] != "203.0.113.99"
            if item["path"] == "/mismatch":
                assert item["verification"] == "ip_mismatch"
            else:
                assert item["status"] == 403
                assert item["verification"] == (
                    "ua_only"
                    if item["crawler"] in {"Bytespider", "MistralAI-Training"}
                    else "verified"
                ), (item["crawler"], item["verification"])
        assert len(get("/api/events?days=1&crawler=Kimi-SearchBot")["items"]) == 1
        assert get("/api/unknown-agents")["items"]
        passed(
            f"{len(RULES)} crawler classifications, evidence states, query privacy, details and overview under 60 seconds"
        )

        control("check")
        control("stop")
        assert state()["baseline_at"] == baseline
        append("/old-tail")
        rotated = log.with_name(log.name + ".1")
        log.rename(rotated)
        log.write_bytes(log_line("/new-file"))
        control("reconnect")
        expected += 2
        await_count(expected)
        control("reconnect")
        assert count() == expected and state()["baseline_at"] == baseline
        passed(
            "actual stop/check/reconnect scripts, offline rename rotation, identity and persistent state"
        )

        Proxy.lose_next_batch = True
        append("/lost-ack")
        wait_for(Proxy.lost.is_set, label="response deliberately lost after commit")
        assert count() == expected + 1
        command(DOCKER, "kill", collector_id())
        control("reconnect")
        expected += 1
        await_count(expected)
        wait_for(
            lambda: max(Counter(Proxy.batches).values()) >= 2, label="same committed batch replayed"
        )
        wait_for(
            lambda: not get("/api/collector/health").get("pending_bytes"),
            label="replay acknowledged",
        )
        passed(
            "committed response lost, container killed, exact batch retried without double counting"
        )

        cid = collector_id()
        command(DOCKER, "network", "disconnect", NETWORK, cid)
        last_heartbeat = get("/api/collector/health")["heartbeat_at"]
        append("/network-old")
        time.sleep(12)
        second = log.with_name(log.name + ".2")
        log.rename(second)
        log.write_bytes(log_line("/network-new"))
        disconnected = wait_for(
            lambda: (
                health
                if (health := get("/api/collector/health"))["overall"] == "disconnected"
                else None
            ),
            timeout=100,
            label="production 90 second disconnection threshold",
        )
        assert disconnected["heartbeat_at"] == last_heartbeat
        assert disconnected["log_received_at"] and not disconnected["gaps"]
        REPORT["disconnected_after_heartbeat_seconds"] = round(time.time() - last_heartbeat, 3)
        command(DOCKER, "network", "connect", NETWORK, cid)
        expected += 2
        await_count(expected)
        wait_for(
            lambda: get("/api/collector/health")["overall"] == "healthy", label="outage recovered"
        )
        # Fully acknowledged rotated-file cleanup is not a missing-data gap.
        second.unlink()
        rotated.unlink()
        append("/after-cleanup")
        expected += 1
        await_count(expected)
        assert not get("/api/collector/health")["gaps"]
        passed(
            "real network disconnect, 90 second health timeout, offline rotation, recovery and safe old-file cleanup"
        )

        control("stop")
        monitor(
            "exec",
            "-T",
            "monitor",
            "python",
            "-m",
            "internal.storage",
            "backup",
            "--database",
            "/app/data/monitor.sqlite3",
            "--output",
            "/app/data/backup.sqlite3",
        )
        monitor("cp", "monitor:/app/data/backup.sqlite3", str(ROOT / "backup.sqlite3"))
        snapshot = state()
        (ROOT / "state-backup.json").write_text(json.dumps(snapshot))
        shutil.copyfile(install_root / "collector.json", ROOT / "config-backup.json")
        monitor("up", "-d", "--no-build", "--force-recreate", "monitor")
        wait_for(lambda: client.get("/api/healthz").is_success, label="monitor recreated")
        login()
        control("reconnect")
        assert count() == expected and get("/api/site")["id"] == site_before["id"]
        append("/after-backup")
        expected += 1
        await_count(expected)
        control("stop")
        monitor("stop", "monitor")
        monitor_id = monitor("ps", "-aq", "monitor")
        restore = "from pathlib import Path; import shutil; root=Path('/work'); [Path('/app/data/'+name).unlink(missing_ok=True) for name in ('monitor.sqlite3-wal','monitor.sqlite3-shm','monitor.sqlite3-journal')]; shutil.copyfile(root/'backup.sqlite3','/app/data/monitor.sqlite3'); Path('/app/data/monitor.sqlite3').chmod(0o600)"
        command(
            DOCKER,
            "run",
            "--rm",
            "--user",
            "0",
            "--volumes-from",
            monitor_id,
            "--mount",
            f"type=bind,src={ROOT},dst=/work,readonly",
            os.environ["ACCEPTANCE_MONITOR_IMAGE"],
            "python",
            "-c",
            restore,
        )
        restore_state = "from pathlib import Path; import shutil; shutil.copyfile('/work/state-backup.json','/state/state.json'); Path('/state/state.json').chmod(0o600)"
        command(
            DOCKER,
            "run",
            "--rm",
            "--mount",
            f"type=volume,src={collector_volume()},dst=/state",
            "--mount",
            f"type=bind,src={ROOT},dst=/work,readonly",
            "python:3.13-slim-bookworm",
            "python",
            "-c",
            restore_state,
        )
        shutil.copyfile(ROOT / "config-backup.json", install_root / "collector.json")
        (install_root / "collector.json").chmod(0o600)
        monitor("up", "-d", "--no-build", "--force-recreate", "monitor")
        wait_for(lambda: client.get("/api/healthz").is_success, label="restored monitor")
        login()
        assert count() == expected - 1
        control("reconnect")
        await_count(expected)
        assert state()["baseline_at"] == baseline
        assert get("/api/site")["source_id"] == credentials["source_id"]
        integrity = monitor(
            "exec",
            "-T",
            "monitor",
            "python",
            "-c",
            "import sqlite3; c=sqlite3.connect('/app/data/monitor.sqlite3'); print(c.execute('pragma integrity_check').fetchone()[0]); print(sqlite3.sqlite_version); print(c.execute('pragma journal_mode').fetchone()[0])",
        )
        assert integrity.splitlines()[0] == "ok"
        REPORT["sqlite"] = integrity.splitlines()[1:]
        passed(
            "container recreation and matching SQLite/config/cursor restore preserve identity and replay once"
        )

        # Remove a known pending generation during a second actual outage.
        command(DOCKER, "network", "disconnect", NETWORK, collector_id())
        append("/intentionally-unrecoverable")
        wait_for(
            lambda: any(
                item["known_size"] > item["acknowledged"]
                for item in state()["generations"]
                if not item["retired"]
            ),
            label="pending bytes persisted before cleanup",
        )
        command(DOCKER, "kill", collector_id())
        log.unlink()
        log.write_bytes(log_line("/after-known-gap"))
        control("reconnect")
        expected += 1
        await_count(expected)
        gaps = wait_for(
            lambda: get("/api/collector/health")["gaps"], label="unrecoverable file gap reported"
        )
        assert gaps[0]["reason"] in {"file_missing", "copytruncate_uncertain"}
        assert get("/api/collector/health")["overall"] == "degraded"
        REPORT["known_gaps"] = len(gaps)
        passed("unconfirmed source cleanup reports known gap and resumes later data")

        inspection = json.loads(command(DOCKER, "inspect", collector_id()))[0]
        assert not inspection["HostConfig"]["PortBindings"]
        assert (
            next(mount for mount in inspection["Mounts"] if mount["Destination"] == "/logs")["RW"]
            is False
        )
        # Raw source records may exist only in the explicitly supplied source log.
        assert "203.0.113.99" not in json.dumps(state())
        database_dump = monitor(
            "exec",
            "-T",
            "monitor",
            "python",
            "-c",
            "import sqlite3; c=sqlite3.connect('/app/data/monitor.sqlite3'); print('\\n'.join(c.iterdump()))",
        )
        assert "203.0.113.99" not in database_dump
        assert credentials["token"] not in database_dump
        assert count() == expected
        REPORT["unique_events"] = expected
        REPORT["state_sha256"] = hashlib.sha256(
            json.dumps(state(), sort_keys=True).encode()
        ).hexdigest()
        REPORT["engine"] = json.loads(command(DOCKER, "version", "--format", "{{json .Server}}"))[
            "Version"
        ]
        passed(
            "read-only source mount, no collector inbound port, masked persistence and final unique total"
        )
        REPORT["isolation"] = {}
        run_checks(
            command=command, wait_for=wait_for, collector_id=collector_id,
            control=control, state=state, get=get, root=ROOT, project=PROJECT, network=NETWORK,
            report=REPORT["isolation"],
        )
        REPORT["unique_events"] = expected + 1
        passed("real cgroup limits, read-only writes, CPU throttling, OOM recovery and independent origin continuity")
    proxy.shutdown()


if __name__ == "__main__":
    try:
        main()
        REPORT["passed"] = True
    except Exception as exc:
        REPORT["passed"] = False
        REPORT["failure"] = str(exc)
        raise
    finally:
        REPORT["finished_at"] = datetime.now(UTC).isoformat()
        (ROOT / "report.json").write_text(json.dumps(REPORT, indent=2) + "\n")
