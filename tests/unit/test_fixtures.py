import json
from pathlib import Path

from internal.crawler.evidence import parse_networks
from internal.logparse import parse_line


def test_documented_combined_samples_and_evidence():
    root = Path(__file__).resolve().parents[1] / "fixtures"
    events = [
        parse_line(line, 0)
        for line in (root / "combined.log").read_bytes().splitlines(keepends=True)
    ]
    assert [event.status for event in events] == [200, 404, 403]
    assert events[0].path == "/article"
    assert len(parse_networks(json.loads((root / "evidence.json").read_text()))) == 2
