"""Disposable Linux/Docker acceptance; only removes its own unique Compose project."""

import argparse
import csv
import io
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def wait_for(predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise RuntimeError("container acceptance condition timed out")


def line(path):
    stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'203.0.113.99 - - [{stamp}] "GET {path} HTTP/1.1" 200 1 "-" "KimiBot/1.0"\n'.encode()


def main():
    project = "geo-monitor-check-" + secrets.token_hex(6)
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="geo-monitor-container-") as temporary:
        folder = Path(temporary)
        logs = folder / "logs"
        logs.mkdir()
        log = logs / "access.log"
        log.write_bytes(line("/before-install"))
        config_path = folder / "collector.json"
        config_path.write_text("{}")
        password = secrets.token_urlsafe(24)
        base = f"http://127.0.0.1:{port}"
        env = os.environ | {
            "GEO_ADMIN_PASSWORD": password,
            "GEO_PUBLIC_URL": base,
            "GEO_COOKIE_SECURE": "false",
            "GEO_PORT": str(port),
            "GEO_LOG_DIRECTORY": str(logs),
            "GEO_COLLECTOR_CONFIG": str(config_path),
        }
        compose = [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(root / "deploy/compose.yaml"),
            "-f",
            str(root / "deploy/collector.compose.yaml"),
        ]

        def command(*args):
            subprocess.run([*compose, *args], env=env, cwd=root, check=True)

        try:
            command("build")
            command("up", "-d", "monitor")
            with httpx.Client(base_url=base, timeout=5) as client:
                wait_for(lambda: client.get("/api/healthz").is_success)
                login = client.post(
                    "/api/auth/login", json={"username": "admin", "password": password}
                )
                login.raise_for_status()
                client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
                client.put("/api/site", json={"domain": "example.com"}).raise_for_status()
                credentials = client.post("/api/site/credentials").json()
                credentials.update(
                    server_url="http://monitor:8000",
                    log_path="/logs/access.log",
                    state_path="/state/state.json",
                    allow_http=True,
                )
                config_path.write_text(json.dumps(credentials))
                command("run", "--rm", "collector", "--config", "/config/collector.json", "--check")
                command("up", "-d", "collector")
                wait_for(lambda: client.get("/api/collector/health").json().get("heartbeat_at"))
                with log.open("ab") as handle:
                    handle.write(line("/first"))
                wait_for(
                    lambda: client.get("/api/overview?days=1").json()["summary"]["requests"] == 1
                )
                command("stop", "collector")
                with log.open("ab") as handle:
                    handle.write(line("/old-tail"))
                log.rename(logs / "access.log.1")
                log.write_bytes(line("/new-file"))
                command("up", "-d", "collector")
                wait_for(
                    lambda: client.get("/api/overview?days=1").json()["summary"]["requests"] == 3
                )
                command("restart", "collector")
                time.sleep(12)
                assert client.get("/api/overview?days=1").json()["summary"]["requests"] == 3
                pages = client.get("/api/pages?days=1").json()
                assert pages["summary"]["requests"] == 3 and pages["total"] == 3
                assert (
                    client.get("/api/pages/detail", params={"path": "/first", "days": 1}).json()[
                        "summary"
                    ]["requests"]
                    == 1
                )
                exported = client.get("/api/events/export", params={"path": "/first", "days": 1})
                exported.raise_for_status()
                rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
                assert (
                    len(rows) == 1 and rows[0]["path"] == "/first" and "evidence_version" in rows[0]
                )
                imported = client.post(
                    "/api/inventory/import",
                    json={"format": "json", "text": '["/first","/not-observed"]'},
                )
                imported.raise_for_status()
                directory = client.get("/api/inventory?days=1").json()
                assert directory["summary"]["pages"] == 2 and directory["summary"]["observed"] == 1
                assert (
                    client.get("/api/inventory?state=unobserved").json()["items"][0]["path"]
                    == "/not-observed"
                )
                assert client.delete("/api/inventory", params={"path": "/not-observed"}).json()[
                    "removed"
                ]
                assert any(
                    rule.get("token") == "Amzn-SearchBot"
                    for rule in client.get("/api/crawlers").json()["rules"]
                )
                print(
                    "Container acceptance passed: preflight, live append, stop/reconnect, rotation, replay, page analytics, CSV and inventory."
                )
        finally:
            # UUID project scope never targets user deployments.
            command("down", "--volumes", "--remove-orphans")


def full_acceptance(report: Path, protocol: str = "https"):
    """Run Linux-only install/restore/fault checks from Windows or Linux Docker."""
    root = Path(__file__).resolve().parents[1]
    project = "geo-monitor-check-" + secrets.token_hex(6)
    network = project + "-network"
    work_volume = project + "-work"
    runner = project + "-runner"

    def docker(*args, check=True, capture=True):
        result = subprocess.run(
            ["docker", *args], cwd=root, check=check, capture_output=capture, text=True
        )
        return result.stdout.strip() if capture else result.returncode

    try:
        for component in ("monitor", "collector"):
            docker(
                "build",
                "-f",
                f"deploy/{'server' if component == 'monitor' else 'collector'}.Dockerfile",
                "-t",
                project + "-" + component,
                ".",
                capture=False,
            )
        docker(
            "build",
            "--build-arg",
            "MONITOR_IMAGE=" + project + "-monitor",
            "-t",
            project + "-runner-image",
            "tests/deployment",
            capture=False,
        )
        docker("volume", "create", work_volume)
        directory = json.loads(docker("volume", "inspect", work_volume))[0]["Mountpoint"]
        docker("network", "create", network)
        docker(
            "create",
            "--name",
            runner,
            "--network",
            network,
            "--network-alias",
            "acceptance",
            "--mount",
            "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock",
            "--mount",
            f"type=volume,src={work_volume},dst={directory}",
            "--env",
            "ACCEPTANCE_DIRECTORY=" + directory,
            "--env",
            "ACCEPTANCE_PROJECT=" + project,
            "--env",
            "ACCEPTANCE_NETWORK=" + network,
            "--env",
            "ACCEPTANCE_MONITOR_IMAGE=" + project + "-monitor",
            "--env",
            "ACCEPTANCE_PROTOCOL=" + protocol,
            project + "-runner-image",
        )
        docker("cp", "deploy/compose.yaml", runner + ":/acceptance-tests/monitor.compose.yaml")
        result = docker("start", "-a", runner, check=False, capture=False)
        state = json.loads(docker("inspect", runner))[0]["State"]
        if result or state["ExitCode"]:
            raise RuntimeError(
                "Full container acceptance failed; inspect the report and console output"
            )
    finally:
        # All deletions are restricted to names minted above or exact Compose labels.
        if docker("ps", "-aq", "--filter", "name=^/" + runner + "$", check=False):
            report.parent.mkdir(parents=True, exist_ok=True)
            docker(
                "cp", runner + ":" + directory + "/report.json", str(report.resolve()), check=False
            )
            docker("rm", "-f", runner, check=False)
        for scoped_project in (project + "-installed", project):
            label = "com.docker.compose.project=" + scoped_project
            containers = docker("ps", "-aq", "--filter", "label=" + label).split()
            if containers:
                docker("rm", "-f", *containers, check=False)
            volumes = docker("volume", "ls", "-q", "--filter", "label=" + label).split()
            if volumes:
                docker("volume", "rm", *volumes, check=False)
        docker("network", "rm", network, check=False)
        docker("volume", "rm", work_volume, check=False)
    print(f"Full container acceptance passed. Report: {report}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="Also test installer, backup and faults"
    )
    parser.add_argument(
        "--protocol", choices=("http", "https"), default="https", help="Full acceptance transport"
    )
    parser.add_argument(
        "--report", type=Path, default=Path(".local/output/container-acceptance.json")
    )
    arguments = parser.parse_args()
    if arguments.full:
        full_acceptance(arguments.report, arguments.protocol)
    else:
        main()
