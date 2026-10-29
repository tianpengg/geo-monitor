"""The fault harness must reject production targets and invalid measurements."""

import importlib.util
import io
from pathlib import Path

import pytest

from internal.logparse import parse_line

spec = importlib.util.spec_from_file_location(
    "isolation_acceptance", Path(__file__).parents[2] / "deployment/isolation.py"
)
isolation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(isolation)


@pytest.mark.parametrize(
    "project,label,service",
    [
        ("geo-monitor", "geo-monitor-installed", "collector"),
        ("geo-monitor-check-", "geo-monitor-check--installed", "collector"),
        ("geo-monitor-check-0123456789ab", "geo-monitor-collector", "collector"),
        ("geo-monitor-check-0123456789ab", "geo-monitor-check-0123456789ab-installed", "monitor"),
    ],
)
def test_isolation_faults_refuse_non_disposable_targets(project, label, service):
    inspection = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": label,
                "com.docker.compose.service": service,
            }
        }
    }
    with pytest.raises(ValueError):
        isolation.require_disposable(inspection, project)


def test_probe_summary_includes_errors_in_measured_latency():
    result = isolation.summarize([(0.001, True)] * 18 + [(0.5, False), (1.0, True)])
    assert result["requests"] == 20 and result["errors"] == 1
    assert result["error_rate"] == 0.05 and result["p95_ms"] == 500


@pytest.mark.parametrize("samples", [[], [(float("nan"), True)], [(-1, True)]])
def test_probe_summary_never_invents_successful_missing_measurements(samples):
    with pytest.raises(ValueError):
        isolation.summarize(samples)


@pytest.mark.parametrize("target", ["/", "/burst"])
def test_synthetic_origin_emits_complete_combined_without_claiming_crawler_identity(
    tmp_path, monkeypatch, target
):
    import http.server
    import sys

    class NoNetworkServer:
        def __init__(self, *_):
            pass

        def serve_forever(self):
            pass

    source = tmp_path / "synthetic.log"
    monkeypatch.setattr(sys, "argv", ["synthetic-origin", str(source)])
    monkeypatch.setattr(http.server, "ThreadingHTTPServer", NoNetworkServer)
    namespace = {}
    exec(compile(isolation.ORIGIN, "synthetic-origin", "exec"), namespace)
    handler_type = namespace["Handler"]
    handler = object.__new__(handler_type)
    handler.path = target
    handler.send_response = lambda *_: None
    handler.send_header = lambda *_: None
    handler.end_headers = lambda: None
    handler.wfile = io.BytesIO()
    handler.do_GET()
    rows = source.read_bytes().splitlines(keepends=True)
    assert rows and all(row.endswith(b"\n") for row in rows)
    event = parse_line(rows[0], 0)
    assert event.path == "/isolation-origin"
    assert event.user_agent == "GeoMonitor-Synthetic-Origin/1.0"
    assert handler.wfile.getvalue() == b"ok"
