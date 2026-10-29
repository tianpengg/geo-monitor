import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("cpu,memory", [(None, None), ("0.5", "256m")])
def test_collector_compose_limits_and_mounts_without_an_engine(tmp_path, cpu, memory):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Compose CLI unavailable; this check does not require an engine")
    environment = os.environ.copy()
    for name in ("GEO_COLLECTOR_CPUS", "GEO_COLLECTOR_MEMORY_LIMIT"):
        environment.pop(name, None)
    environment.update(GEO_LOG_DIRECTORY=str(tmp_path), GEO_COLLECTOR_CONFIG=str(tmp_path / "collector.json"))
    if cpu:
        environment.update(GEO_COLLECTOR_CPUS=cpu, GEO_COLLECTOR_MEMORY_LIMIT=memory)
    result = subprocess.run(
        [docker, "compose", "-f", str(ROOT / "deploy/collector.compose.yaml"), "config", "--format", "json"],
        env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    service = json.loads(result.stdout)["services"]["collector"]
    assert float(service["cpus"]) == (0.5 if cpu else 0.25)
    assert int(service["mem_limit"]) == (256 if memory else 128) * 1024 * 1024
    assert service["pids_limit"] == 64 and service["read_only"]
    assert service["logging"] == {"driver": "json-file", "options": {"max-file": "2", "max-size": "5m"}}
    assert not service.get("privileged") and not service.get("ports")
    assert service.get("network_mode") != "host"
    mounts = {volume["target"]: volume for volume in service["volumes"]}
    assert set(mounts) == {"/logs", "/config/collector.json", "/state"}
    assert mounts["/logs"]["read_only"] and mounts["/config/collector.json"]["read_only"]
    assert mounts["/state"]["type"] == "volume" and not mounts["/state"].get("read_only", False)
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["tmpfs"] == ["/tmp:size=16777216,mode=1777,noexec,nosuid"]
