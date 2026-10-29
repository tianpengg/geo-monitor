import json
import logging
import signal
import threading
import uuid

import httpx

from internal.collector.tailer import Tailer
from internal.config import CollectorConfig
from internal.logparse import COMBINED
from internal.protocol import MAX_LINE_BYTES

logger = logging.getLogger(__name__)


def preflight(config: CollectorConfig, client: httpx.Client) -> dict:
    checks = {
        "path": "pending",
        "permission": "pending",
        "format": "pending",
        "connection": "pending",
    }
    try:
        if not config.log_path.is_file():
            checks["path"] = "missing"
        else:
            checks["path"] = "ok"
            with config.log_path.open("rb") as handle:
                size = config.log_path.stat().st_size
                start = max(0, size - MAX_LINE_BYTES)
                handle.seek(start)
                if start:
                    handle.readline(MAX_LINE_BYTES)
                lines = handle.read(MAX_LINE_BYTES).splitlines(keepends=True)
            checks["permission"] = "ok"
            complete = [line for line in lines[-20:] if line.endswith(b"\n")]
            if complete:
                checks["format"] = (
                    "combined"
                    if all(
                        COMBINED.fullmatch(line.decode("utf-8", errors="replace"))
                        for line in complete
                    )
                    else "unsupported"
                )
    except PermissionError:
        checks["permission"] = "unreadable"
    except OSError:
        checks["path"] = "unreadable"
    try:
        response = client.post(
            "/api/collector/preflight",
            json={"version": 1, "site_id": config.site_id, "source_id": config.source_id},
        )
        checks["connection"] = (
            "ok"
            if response.is_success
            else ("authentication" if response.status_code == 401 else "protocol")
        )
    except httpx.HTTPError:
        checks["connection"] = "network"
    return {
        "ok": checks["path"] == "ok"
        and checks["permission"] == "ok"
        and checks["format"] in {"pending", "combined"}
        and checks["connection"] == "ok",
        "checks": checks,
    }


class Collector:
    def __init__(self, config: CollectorConfig, client: httpx.Client):
        self.config = config
        self.client = client
        self.tailer = Tailer(config)
        self.instance_id = uuid.uuid4().hex
        self.sequence = 0
        self.state = "ok"
        self.error_code = None

    def step(self) -> bool:
        try:
            batch = self.tailer.next_batch()
            if batch:
                response = self.client.post(
                    "/api/collector/batches",
                    content=batch.model_dump_json(),
                    headers={"Content-Type": "application/json"},
                )
                if not response.is_success:
                    self.state = (
                        "auth_error"
                        if response.status_code == 401
                        else ("retrying" if response.status_code >= 500 else "protocol_error")
                    )
                    self.error_code = (
                        "authentication"
                        if response.status_code == 401
                        else ("network" if response.status_code >= 500 else "protocol")
                    )
                    return False
                self.tailer.acknowledge(batch, response.json())
            if not self.config.log_path.is_file():
                self.state, self.error_code = "read_error", "missing"
                return False
            self.state = "backlog" if self.tailer.report()["pending_bytes"] else "ok"
            self.error_code = None
            return True
        except httpx.HTTPError:
            self.state, self.error_code = "retrying", "network"
        except OSError:
            self.state, self.error_code = "read_error", "unreadable"
        except (ValueError, KeyError):
            self.state, self.error_code = "protocol_error", "protocol"
        return False

    def heartbeat(self) -> bool:
        try:
            report = self.tailer.report()
            self.sequence += 1
            message = {
                "version": 1,
                "site_id": self.config.site_id,
                "source_id": self.config.source_id,
                "instance_id": self.instance_id,
                "sequence": self.sequence,
                "state": self.state,
                "error_code": self.error_code,
                **report,
            }
            response = self.client.post("/api/collector/heartbeat", json=message)
            if response.is_success and response.json().get("accepted"):
                self.tailer.acknowledge_gaps({gap["id"] for gap in report["gaps"]})
                return True
        except (httpx.HTTPError, ValueError, OSError):
            pass
        return False


def run(config: CollectorConfig, *, check: bool = False, once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # HTTPX debug output is intentionally disabled; bearer headers are never logged.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    with httpx.Client(
        base_url=config.server_url,
        headers={"Authorization": "Bearer " + config.token.get_secret_value()},
        timeout=config.request_timeout,
        follow_redirects=False,
    ) as client:
        if check or not config.state_path.exists():
            result = preflight(config, client)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if check or not result["ok"]:
                if not result["ok"]:
                    raise SystemExit(2)
                return
        try:
            collector = Collector(config, client)
        except (ValueError, OSError):
            raise SystemExit(
                "Cannot initialize collector state; check source identity and permissions."
            ) from None
        if once:
            ok = collector.step()
            collector.heartbeat()
            if not ok:
                raise SystemExit(1)
            return

        def heartbeat_worker():
            while not stop.is_set():
                collector.heartbeat()
                stop.wait(config.heartbeat_seconds)

        worker = threading.Thread(target=heartbeat_worker, name="collector-heartbeat", daemon=True)
        worker.start()
        delay = config.flush_seconds
        try:
            while not stop.is_set():
                ok = collector.step()
                if ok:
                    delay = (
                        config.catchup_pause_seconds if collector.state == "backlog"
                        else config.flush_seconds
                    )
                else:
                    logger.warning("Collector status: %s", collector.state)
                    delay = min(30, max(1, delay * 2))
                stop.wait(delay)
        finally:
            stop.set()
            worker.join(config.request_timeout + 2)
