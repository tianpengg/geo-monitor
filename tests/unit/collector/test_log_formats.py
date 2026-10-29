import httpx
import pytest

from internal.collector.runtime import preflight
from internal.config import CollectorConfig
from internal.logparse import COMBINED, ParseError, parse_line

BASE = (
    "203.0.113.10 - - [29/Oct/2026:13:36:55 +0800] "
    '"GET /sitemap.xml HTTP/2.0" 200 3750 "-" "ClaudeBot/1.0"'
)


def check_format(tmp_path, raw):
    path = tmp_path / "access.log"
    path.write_bytes(raw)
    config = CollectorConfig(
        server_url="https://monitor.example.test",
        site_id="site",
        source_id="source",
        token="synthetic-token",
        log_path=path,
        state_path=tmp_path / "state.json",
    )
    with httpx.Client(
        base_url=config.server_url,
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    ) as wire:
        result = preflight(config, wire)
    assert path.read_bytes() == raw
    assert not config.state_path.exists()
    return result


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        ' "-"',
        ' ""',
        ' "198.51.100.17"',
        ' "2001:db8::17, 198.51.100.17"',
        r' "untrusted\x20value\"ignored"',
    ],
)
def test_combined_and_main_share_parser_and_preflight_without_trusting_suffix(tmp_path, suffix):
    raw = (BASE + suffix + "\n").encode()
    assert len(COMBINED.fullmatch(raw.decode()).groups()) == 6
    event = parse_line(raw, 42)
    assert str(event.client_ip) == "203.0.113.10"
    assert event.path == "/sitemap.xml" and event.method == "GET" and event.status == 200
    assert event.user_agent == "ClaudeBot/1.0"
    assert event.offset == 42 and event.end_offset == 42 + len(raw)
    encoded = event.model_dump_json()
    assert not any(value in encoded for value in ("198.51.100.17", "2001:db8::17", "untrusted"))
    result = check_format(tmp_path, raw)
    assert result["ok"] and result["checks"]["format"] == "combined"


@pytest.mark.parametrize(
    "suffix",
    [
        " 198.51.100.17",
        ' "-" "-"',
        ' "unfinished',
        ' "-" trailing',
        ' "bad "quote""',
    ],
)
def test_unsupported_or_damaged_tail_is_rejected_consistently(tmp_path, suffix):
    raw = (BASE + suffix + "\n").encode()
    with pytest.raises(ParseError):
        parse_line(raw, 0)
    result = check_format(tmp_path, raw)
    assert not result["ok"] and result["checks"]["format"] == "unsupported"
