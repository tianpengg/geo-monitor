import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from internal.collector import runtime
from internal.collector.tailer import READ_BUDGET, Tailer
from internal.config import CollectorConfig


def request_line(path="/after"):
    stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'203.0.113.99 - - [{stamp}] "GET {path} HTTP/1.1" 200 1 "-" "KimiBot"\n'.encode()


@pytest.fixture
def config(tmp_path):
    log = tmp_path / "access.log"
    log.write_bytes(b"")
    return CollectorConfig(server_url="https://monitor.example.test", site_id="site",
                           source_id="source", token="synthetic-token", log_path=log,
                           state_path=tmp_path / "state.json")


def confirm(tailer, batch):
    tailer.acknowledge(batch, {"batch_id": batch.batch_id, "acknowledged_offset": batch.end_offset})


@pytest.mark.parametrize("prefix,initial_partial", [(False, False), (True, False), (False, True)])
def test_large_line_budget_restart_once_only_and_source_unchanged(config, monkeypatch, prefix, initial_partial):
    if initial_partial:
        config.log_path.write_bytes(b"pre-install-partial")
    tailer = Tailer(config)
    baseline = config.log_path.stat().st_size
    payload = (request_line("/prefix") if prefix else b"") + b"x" * (4 * 1024 * 1024) + b"\n" + request_line()
    with config.log_path.open("ab") as handle:
        handle.write(payload)
    source = config.log_path.read_bytes()
    original = Path.open
    count = [0]

    class Counted:
        def __init__(self, handle): self.handle = handle
        def __enter__(self): return self
        def __exit__(self, *args): self.handle.close()
        def __getattr__(self, name): return getattr(self.handle, name)
        def readline(self, size=-1):
            raw = self.handle.readline(size)
            count[0] += len(raw)
            return raw

    def counted(path, *args, **kwargs):
        handle = original(path, *args, **kwargs)
        return Counted(handle) if path == config.log_path and args and args[0] == "rb" else handle

    monkeypatch.setattr(Path, "open", counted)
    paths, issues = [], []
    for turn in range(50):
        count[0] = 0
        batch = tailer.next_batch()
        assert count[0] <= READ_BUDGET
        if turn == 1:
            # Volatile scan cursors can be lost without advancing confirmation.
            tailer = Tailer(config)
            continue
        if batch:
            assert tailer.next_batch().batch_id == batch.batch_id
            paths.extend(event.path for event in batch.events)
            issues.extend(issue.reason for issue in batch.issues)
            confirm(tailer, batch)
        if "/after" in paths:
            break
    assert paths == (["/prefix", "/after"] if prefix else ["/after"])
    assert issues == ["initial_partial_line" if initial_partial else "line_too_long"]
    assert tailer.report()["parse_errors"] == (0 if initial_partial else 1)
    assert tailer.state["generations"][0]["acknowledged"] == baseline + len(payload)
    assert config.log_path.read_bytes() == source
    saved = config.state_path.read_text()
    assert len(saved) < 8192 and "203.0.113.99" not in saved and "KimiBot" not in saved


def test_unterminated_old_line_does_not_hide_new_rotation(config):
    tailer = Tailer(config)
    config.log_path.write_bytes(b"x" * (READ_BUDGET * 3))
    assert tailer.next_batch() is None
    config.log_path.rename(config.log_path.with_name("access.log.1"))
    config.log_path.write_bytes(request_line("/new-generation"))
    batch = None
    for _ in range(8):
        batch = tailer.next_batch()
        if batch:
            break
    assert batch and batch.events[0].path == "/new-generation"
    confirm(tailer, batch)
    assert tailer.report()["pending_bytes"] > 0


def test_idle_poll_and_empty_gap_ack_do_not_fsync(config, monkeypatch):
    tailer = Tailer(config)
    before = config.state_path.read_bytes()
    sync = MagicMock()
    monkeypatch.setattr("internal.collector.tailer.os.fsync", sync)
    for _ in range(3):
        assert tailer.next_batch() is None
        tailer.acknowledge_gaps(set())
    sync.assert_not_called()
    assert config.state_path.read_bytes() == before
    config.log_path.write_bytes(request_line())
    assert tailer.next_batch()
    assert sync.called


def test_retired_generation_history_is_reclaimed_but_gap_is_kept(config):
    tailer = Tailer(config)
    for index in range(30):
        old = config.log_path.with_name(f"access.log.{index}")
        config.log_path.rename(old)
        config.log_path.write_bytes(b"")
        tailer.next_batch()
        old.unlink()
        tailer.next_batch()
        assert len(tailer.state["generations"]) == 1
    config.log_path.write_bytes(request_line("/unconfirmed"))
    tailer.discover()
    config.log_path.unlink()
    config.log_path.write_bytes(request_line("/new"))
    tailer.next_batch()
    assert tailer.report()["gaps"]
    assert len(config.state_path.read_bytes()) < 8192


def test_local_save_failure_rolls_back_position_and_diagnostic_count(config, monkeypatch):
    tailer = Tailer(config)
    config.log_path.write_bytes(b"invalid-line\n")
    batch = tailer.next_batch()
    from internal.collector import tailer as module
    replace = module.os.replace
    failures = [1]

    def fail_once(source, target):
        if Path(target) == config.state_path and failures[0]:
            failures[0] -= 1
            raise OSError("synthetic state write failure")
        return replace(source, target)

    monkeypatch.setattr(module.os, "replace", fail_once)
    with pytest.raises(OSError):
        confirm(tailer, batch)
    assert tailer.state["generations"][0]["acknowledged"] == batch.start_offset
    assert tailer.report()["parse_errors"] == 0 and tailer.pending == batch
    assert json.loads(config.state_path.read_text())["parse_errors"] == 0
    confirm(tailer, batch)
    assert tailer.report()["parse_errors"] == 1
    assert Tailer(config).state["generations"][0]["acknowledged"] == batch.end_offset


@pytest.mark.parametrize("value", [0, -1, 0.01, 31, float("nan"), float("inf")])
def test_catchup_wait_cannot_be_disabled_or_unbounded(config, value):
    assert config.catchup_pause_seconds == 0.25
    with pytest.raises(ValueError):
        CollectorConfig.model_validate({**config.model_dump(), "catchup_pause_seconds": value})


def test_loop_yields_during_backlog_and_preserves_error_backoff(config, monkeypatch):
    Tailer(config)
    waits = []

    class Stop:
        stopped = False
        def is_set(self): return self.stopped
        def set(self): self.stopped = True
        def wait(self, delay):
            waits.append(delay)
            if len(waits) == 4:
                self.set()

    stop = Stop()
    thread = MagicMock()
    monkeypatch.setattr(runtime.threading, "Event", lambda: stop)
    monkeypatch.setattr(runtime.threading, "Thread", lambda **kwargs: thread)
    monkeypatch.setattr(runtime.signal, "signal", lambda *args: None)
    monkeypatch.setattr(runtime.httpx, "Client", MagicMock())
    collector = MagicMock()
    sequence = iter([(True, "backlog"), (True, "ok"), (False, "retrying"), (False, "auth_error")])

    def step():
        success, collector.state = next(sequence)
        return success

    collector.step.side_effect = step
    monkeypatch.setattr(runtime, "Collector", lambda *args: collector)
    runtime.run(config)
    assert waits == [0.25, config.flush_seconds, 20, 30]
    thread.start.assert_called_once()
    thread.join.assert_called_once()
