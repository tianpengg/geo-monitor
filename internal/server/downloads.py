import io
import tarfile
from pathlib import Path


def collector_archive(root: Path) -> bytes:
    root = root.resolve()
    allowed = [
        root / name
        for name in [
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "LICENSE",
            "cmd/server/main.py",
            "cmd/collector/main.py",
            "deploy/collector.Dockerfile",
            "deploy/collector.compose.yaml",
            "scripts/collector-control.sh",
        ]
    ] + sorted((root / "internal").rglob("*.py"))
    if any(not path.is_file() or not path.resolve().is_relative_to(root) for path in allowed):
        raise FileNotFoundError("collector bundle files are unavailable")
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w:gz") as archive:
        for path in allowed:
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(root).as_posix())
            info.size = len(data)
            info.mode = 0o755 if path.suffix == ".sh" else 0o644
            archive.addfile(info, io.BytesIO(data))
    return result.getvalue()
