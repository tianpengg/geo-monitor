from datetime import UTC, datetime

import httpx
import pytest

from internal.collector.runtime import Collector, preflight
from internal.collector.tailer import Tailer
from internal.config import CollectorConfig
from internal.logparse import ParseError, parse_line
from internal.protocol import MAX_LINE_BYTES


def line(path="/article?q=private", ua="KimiBot/1.0", ip="203.0.113.99", status=200):
    stamp = datetime.now(UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'{ip} - - [{stamp}] "GET {path} HTTP/1.1" {status} 42 "-" "{ua}"\n'.encode()


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "site.access.log"
    path.write_bytes(line("/old"))
    return CollectorConfig(
        server_url="https://monitor.example.com",
        site_id="site",
        source_id="source",
        token="synthetic-collector-token",
        log_path=path,
        state_path=tmp_path / "state" / "state.json",
    )


def append(config, raw):
    with config.log_path.open("ab") as handle:
        handle.write(raw)


def ack(tailer, batch):
    tailer.acknowledge(batch, {"batch_id": batch.batch_id, "acknowledged_offset": batch.end_offset})


def test_first_baseline_complete_lines_and_byte_offsets(config):
    old_size = config.log_path.stat().st_size
    tailer = Tailer(config)
    assert tailer.next_batch() is None
    raw = line("/中文页面")
    append(config, raw[:-1])
    assert tailer.next_batch() is None
    append(config, b"\n")
    batch = tailer.next_batch()
    assert batch.start_offset == old_size
    assert batch.end_offset == old_size + len(raw)
    assert batch.events[0].path == "/中文页面"
    ack(tailer, batch)
    assert Tailer(config).next_batch() is None


def test_initial_partial_line_is_not_a_new_request(config):
    config.log_path.write_bytes(line()[:-20])
    tailer = Tailer(config)
    append(config, line()[-20:] + line("/new"))
    batch = tailer.next_batch()
    assert len(batch.events) == 1
    assert batch.events[0].path == "/new"
    assert batch.issues[0].reason == "initial_partial_line"


def test_restart_before_ack_resends_same_event_identity(config):
    tailer = Tailer(config)
    append(config, line())
    pending = tailer.next_batch()
    restarted = Tailer(config)
    repeated = restarted.next_batch()
    assert repeated.batch_id == pending.batch_id
    assert repeated.generation == pending.generation
    assert repeated.events[0].offset == pending.events[0].offset
    with pytest.raises(ValueError):
        restarted.acknowledge(
            repeated, {"batch_id": "bad", "acknowledged_offset": repeated.end_offset}
        )
    assert restarted.state["generations"][0]["acknowledged"] == pending.start_offset


def test_rename_rotation_and_restart(config):
    Tailer(config)
    append(config, line("/old-tail"))
    rotated = config.log_path.with_name(config.log_path.name + ".1")
    config.log_path.rename(rotated)
    config.log_path.write_bytes(line("/new-file"))
    restarted = Tailer(config)
    first = restarted.next_batch()
    assert [event.path for event in first.events] == ["/old-tail"]
    ack(restarted, first)
    second = restarted.next_batch()
    assert [event.path for event in second.events] == ["/new-file"]
    assert second.generation != first.generation
    ack(restarted, second)
    assert restarted.next_batch() is None


def test_multiple_rotations_while_offline_skip_pre_install_history(config):
    history = config.log_path.with_name(config.log_path.name + ".history")
    history.write_bytes(line("/pre-install"))
    Tailer(config)
    append(config, line("/first"))
    config.log_path.rename(config.log_path.with_name(config.log_path.name + ".2"))
    config.log_path.write_bytes(line("/second"))
    config.log_path.rename(config.log_path.with_name(config.log_path.name + ".1"))
    config.log_path.write_bytes(line("/third"))
    tailer = Tailer(config)
    paths = []
    while (batch := tailer.next_batch()) is not None:
        paths.extend(event.path for event in batch.events)
        ack(tailer, batch)
    assert paths == ["/first", "/second", "/third"]


def test_truncation_generation_and_copy_recovery(config):
    tailer = Tailer(config)
    append(config, line("/unconfirmed"))
    copy = config.log_path.with_name(config.log_path.name + ".1")
    copy.write_bytes(config.log_path.read_bytes())
    config.log_path.write_bytes(line("/new"))
    first = tailer.next_batch()
    assert [event.path for event in first.events] == ["/unconfirmed"]
    ack(tailer, first)
    second = tailer.next_batch()
    assert [event.path for event in second.events] == ["/new"]
    assert second.generation != first.generation
    assert tailer.state["gaps"][0]["reason"] == "copytruncate_uncertain"


def test_missing_rotated_file_is_a_gap_not_silent_zero(config):
    Tailer(config)
    config.log_path.unlink()
    config.log_path.write_bytes(line("/new"))
    # inode reuse can happen; overwrite anchor detection also signals incompleteness.
    tailer = Tailer(config)
    batch = tailer.next_batch()
    assert batch.events[0].path == "/new"
    assert tailer.report()["gaps"]


def test_bad_and_overlong_lines_do_not_block(config):
    tailer = Tailer(config)
    append(
        config, b"invalid-client-secret\n" + b"x" * (MAX_LINE_BYTES + 10) + b"\n" + line("/after")
    )
    batch = tailer.next_batch()
    assert [issue.reason for issue in batch.issues] == ["invalid_line", "line_too_long"]
    assert batch.events[0].path == "/after"
    ack(tailer, batch)
    assert tailer.report()["parse_errors"] == 2
    state = config.state_path.read_text()
    assert "invalid-client-secret" not in state
    assert "203.0.113.99" not in state
    assert "KimiBot" not in state


def test_deleting_fully_confirmed_rotated_file_is_not_a_gap(config):
    tailer = Tailer(config)
    rotated = config.log_path.with_name(config.log_path.name + ".1")
    config.log_path.rename(rotated)
    config.log_path.write_bytes(line("/new"))
    batch = tailer.next_batch()
    ack(tailer, batch)
    rotated.unlink()
    assert tailer.next_batch() is None
    assert tailer.report()["gaps"] == []


def test_preflight_is_read_only_and_handles_empty_file(config):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    with httpx.Client(base_url=config.server_url, transport=transport) as client:
        assert preflight(config, client)["ok"]
        assert not config.state_path.exists()
        config.log_path.write_bytes(b"")
        assert preflight(config, client)["checks"]["format"] == "pending"
        config.log_path.write_bytes(b"bad format\n")
        assert not preflight(config, client)["ok"]


@pytest.mark.parametrize("status,expected", [(401, "authentication"), (500, "protocol")])
def test_preflight_reports_connection_failures_without_moving_state(config, status, expected):
    tailer = Tailer(config)
    before = config.state_path.read_bytes()
    with httpx.Client(
        base_url=config.server_url,
        transport=httpx.MockTransport(lambda request: httpx.Response(status)),
    ) as client:
        result = preflight(config, client)
    assert not result["ok"]
    assert result["checks"]["connection"] == expected
    assert config.state_path.read_bytes() == before
    assert tailer.state["generations"]


def test_preflight_unreadable_file_does_not_claim_success(config, monkeypatch):
    original = type(config.log_path).open

    def denied(path, *args, **kwargs):
        if path == config.log_path:
            raise PermissionError("synthetic permission error")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(config.log_path), "open", denied)
    with httpx.Client(
        base_url=config.server_url,
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    ) as client:
        result = preflight(config, client)
    assert not result["ok"]
    assert result["checks"]["permission"] == "unreadable"
    assert not config.state_path.exists()


def test_preflight_recognizes_combined_even_when_http_request_is_malformed(config):
    raw = line().replace(b"GET /article?q=private HTTP/1.1", b"-")
    config.log_path.write_bytes(raw)
    with httpx.Client(
        base_url=config.server_url,
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    ) as client:
        assert preflight(config, client)["checks"]["format"] == "combined"
    with pytest.raises(ParseError):
        parse_line(raw, 0)


@pytest.mark.parametrize("failure", ["offline", "response_lost", "authentication", "invalid_ack"])
def test_retry_does_not_advance_confirmation(config, failure):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("batches"):
            if failure in {"offline", "response_lost"}:
                raise httpx.ConnectError("synthetic failure", request=request)
            if failure == "authentication":
                return httpx.Response(401)
            return httpx.Response(200, json={"batch_id": "bad", "acknowledged_offset": 999})
        return httpx.Response(200, json={"accepted": True})

    with httpx.Client(base_url=config.server_url, transport=httpx.MockTransport(handle)) as client:
        collector = Collector(config, client)
        baseline = config.log_path.stat().st_size
        append(config, line())
        assert not collector.step()
        assert collector.tailer.state["generations"][0]["acknowledged"] == baseline
        assert collector.heartbeat()
        assert calls[-1].url.path.endswith("heartbeat")


def test_parser_ipv6_status_escaping_and_errors():
    event = parse_line(
        line("/test", ua='KimiBot/1.0 \\"quoted\\"', ip="2001:db8::123", status=404), 9
    )
    assert event.status == 404
    assert str(event.client_ip) == "2001:db8::123"
    assert event.offset == 9
    with pytest.raises(ParseError) as exc:
        parse_line(b"203.0.113.99 secret\n", 0)
    assert "203.0.113.99" not in str(exc.value)
