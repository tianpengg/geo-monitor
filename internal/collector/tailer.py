"""Persistent byte cursors; source logs are the only durable event buffer."""

import hashlib
import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from internal.config import CollectorConfig
from internal.logparse import ParseError, parse_line
from internal.protocol import MAX_LINE_BYTES, Batch, batch_identity

READ_BUDGET = 256 * 1024


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def file_id(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_dev}:{stat.st_ino}"


def anchor(path: Path, length: int) -> str:
    with path.open("rb") as handle:
        return hashlib.sha256(handle.read(length)).hexdigest()


class Tailer:
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.lock = threading.RLock()
        self.pending: Batch | None = None
        self._saved_state: str | None = None
        self._oversized: dict[str, dict] = {}
        self.last_read_at: str | None = None
        if config.state_path.exists():
            self.state = json.loads(config.state_path.read_text(encoding="utf-8"))
            if (
                self.state.get("version") != 1
                or self.state.get("source_id") != config.source_id
                or self.state.get("site_id") != config.site_id
            ):
                raise ValueError("state belongs to another source or version")
            self._saved_state = json.dumps(self.state, separators=(",", ":"))
        else:
            candidates = self.candidates()
            current = config.log_path
            size = current.stat().st_size
            partial = False
            if size:
                with current.open("rb") as handle:
                    handle.seek(size - 1)
                    partial = handle.read(1) != b"\n"
            self.state = {
                "version": 1,
                "site_id": config.site_id,
                "source_id": config.source_id,
                "baseline_at": timestamp(),
                "generations": [],
                "gaps": [],
                "parse_errors": 0,
                "ignored": [file_id(path) for path in candidates if path != current],
            }
            self.register(current, size, partial)
            self.save()

    def candidates(self) -> list[Path]:
        root = self.config.log_path.parent.resolve()
        pattern = self.config.rotation_pattern or (self.config.log_path.name + "*")
        paths = [
            path
            for path in root.glob(pattern)
            if path.is_file()
            and path.resolve().is_relative_to(root)
            and path.suffix.lower() not in {".gz", ".zip", ".bz2", ".xz", ".zst"}
        ]
        if self.config.log_path.is_file() and self.config.log_path not in paths:
            paths.append(self.config.log_path)
        return sorted(
            paths,
            key=lambda path: (path == self.config.log_path, path.stat().st_mtime_ns, str(path)),
        )

    def save(self) -> None:
        serialized = json.dumps(self.state, separators=(",", ":"))
        if serialized == self._saved_state:
            return
        path = self.config.state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        if os.name == "posix":
            descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        self._saved_state = serialized

    def register(self, path: Path, offset: int = 0, partial: bool = False) -> dict:
        size = path.stat().st_size
        length = min(size, 128)
        entry = {
            "identity": file_id(path),
            "generation": uuid.uuid4().hex,
            "acknowledged": offset,
            "known_size": size,
            "anchor_length": length,
            "anchor": anchor(path, length),
            "initial_partial": partial,
            "retired": False,
            "was_primary": path == self.config.log_path,
        }
        self.state["generations"].append(entry)
        return entry

    def record_gap(self, entry: dict, reason: str) -> None:
        self.state["gaps"].append(
            {
                "id": uuid.uuid4().hex,
                "reason": reason,
                "detected_at": timestamp(),
                "generation": entry["generation"],
                "start_offset": entry["acknowledged"],
                "end_offset": max(entry["known_size"], entry["acknowledged"]),
            }
        )

    def discover(self) -> dict[str, Path]:
        candidates = self.candidates()
        by_identity = {file_id(path): path for path in candidates}
        primary_identity = file_id(self.config.log_path) if self.config.log_path.exists() else None
        self.state["ignored"] = [
            identity for identity in self.state["ignored"]
            if identity in by_identity and identity != primary_identity
        ]
        used = set(self.state["ignored"])
        for entry in self.state["generations"]:
            if entry["retired"]:
                continue
            path = by_identity.get(entry["identity"])
            if path is None:
                if entry["acknowledged"] < entry["known_size"] or entry.get("was_primary", True):
                    self.record_gap(entry, "file_missing")
                entry["retired"] = True
                continue
            entry["was_primary"] = path == self.config.log_path
            changed = (
                path.stat().st_size < entry["acknowledged"]
                or anchor(path, entry["anchor_length"]) != entry["anchor"]
            )
            if changed:
                self.record_gap(entry, "copytruncate_uncertain")
                # Recover the old unconfirmed tail from a copytruncate copy when available.
                copy = next(
                    (
                        candidate
                        for candidate in candidates
                        if file_id(candidate) != primary_identity
                        and file_id(candidate) not in used
                        and candidate.stat().st_size >= entry["acknowledged"]
                        and entry["anchor_length"] > 0
                        and anchor(candidate, entry["anchor_length"]) == entry["anchor"]
                    ),
                    None,
                )
                if copy:
                    entry["identity"] = file_id(copy)
                    entry["was_primary"] = False
                    entry["known_size"] = copy.stat().st_size
                    used.add(entry["identity"])
                else:
                    entry["retired"] = True
                continue
            used.add(entry["identity"])
            entry["known_size"] = path.stat().st_size
            if entry["anchor_length"] == 0 and entry["known_size"]:
                entry["anchor_length"] = min(entry["known_size"], 128)
                entry["anchor"] = anchor(path, entry["anchor_length"])
        for path in candidates:
            identity = file_id(path)
            if identity not in used:
                self.register(path)
                used.add(identity)
        self.state["generations"] = [
            entry for entry in self.state["generations"] if not entry["retired"]
        ]
        active = {entry["generation"]: entry for entry in self.state["generations"]}
        self._oversized = {
            generation: scan for generation, scan in self._oversized.items()
            if generation in active and scan["identity"] == active[generation]["identity"]
            and scan["cursor"] <= active[generation]["known_size"]
        }
        self.save()
        return by_identity

    @staticmethod
    def scan_oversized(handle, scan, budget):
        while budget:
            raw = handle.readline(min(MAX_LINE_BYTES + 1, budget))
            budget -= len(raw)
            scan["cursor"] = handle.tell()
            if not raw:
                break
            if raw.endswith(b"\n"):
                return True, budget
        return False, budget

    def next_batch(self) -> Batch | None:
        with self.lock:
            if self.pending:
                return self.pending
            paths = self.discover()
            budget = READ_BUDGET
            for entry in self.state["generations"]:
                if entry["retired"]:
                    continue
                path = paths.get(entry["identity"])
                if path is None:
                    continue
                events, issues = [], []
                start = end = entry["acknowledged"]
                scan = self._oversized.get(entry["generation"])
                if scan and scan["offset"] != start:
                    self._oversized.pop(entry["generation"], None)
                    scan = None
                with path.open("rb") as handle:
                    handle.seek(scan["cursor"] if scan else start)
                    for _ in range(self.config.batch_size):
                        if scan:
                            complete, budget = self.scan_oversized(handle, scan, budget)
                            if not complete:
                                break
                            end = handle.tell()
                            issues.append({"offset": scan["offset"], "end_offset": end,
                                           "reason": scan["reason"]})
                            self._oversized.pop(entry["generation"], None)
                            scan = None
                            continue
                        if budget < MAX_LINE_BYTES + 1:
                            break
                        offset = handle.tell()
                        raw = handle.readline(MAX_LINE_BYTES + 1)
                        budget -= len(raw)
                        if not raw:
                            break
                        too_long = len(raw) > MAX_LINE_BYTES
                        if too_long and not raw.endswith(b"\n"):
                            scan = {"offset": offset, "cursor": handle.tell(),
                                    "identity": entry["identity"],
                                    "reason": "initial_partial_line" if entry["initial_partial"]
                                    and offset == start else "line_too_long"}
                            self._oversized[entry["generation"]] = scan
                            complete, budget = self.scan_oversized(handle, scan, budget)
                            if not complete:
                                break
                            end = handle.tell()
                            issues.append({"offset": offset, "end_offset": end,
                                           "reason": scan["reason"]})
                            self._oversized.pop(entry["generation"], None)
                            scan = None
                            continue
                        if not raw or not raw.endswith(b"\n"):
                            break
                        end = handle.tell()
                        if entry["initial_partial"] and offset == start:
                            issues.append(
                                {
                                    "offset": offset,
                                    "end_offset": end,
                                    "reason": "initial_partial_line",
                                }
                            )
                        elif too_long:
                            issues.append(
                                {"offset": offset, "end_offset": end, "reason": "line_too_long"}
                            )
                        else:
                            try:
                                events.append(parse_line(raw, offset))
                            except ParseError:
                                issues.append(
                                    {"offset": offset, "end_offset": end, "reason": "invalid_line"}
                                )
                    self.last_read_at = timestamp()
                if end > start:
                    self.pending = Batch(
                        site_id=self.config.site_id,
                        source_id=self.config.source_id,
                        generation=entry["generation"],
                        start_offset=start,
                        end_offset=end,
                        batch_id=batch_identity(
                            self.config.source_id, entry["generation"], start, end
                        ),
                        events=events,
                        issues=issues,
                    )
                    return self.pending
                if not budget:
                    break
            return None

    def acknowledge(self, batch: Batch, response: dict) -> None:
        with self.lock:
            if (
                response.get("batch_id") != batch.batch_id
                or response.get("acknowledged_offset") != batch.end_offset
            ):
                raise ValueError("invalid acknowledgement")
            entry = next(
                item for item in self.state["generations"] if item["generation"] == batch.generation
            )
            previous = deepcopy(self.state)
            try:
                entry["acknowledged"] = batch.end_offset
                entry["initial_partial"] = False
                self.state["parse_errors"] += sum(
                    issue.reason != "initial_partial_line" for issue in batch.issues
                )
                self.save()
            except OSError:
                self.state = previous
                raise
            self.pending = None

    def report(self) -> dict:
        with self.lock:
            active = [entry for entry in self.state["generations"] if not entry["retired"]]
            pending_bytes = sum(
                max(0, entry["known_size"] - entry["acknowledged"]) for entry in active
            )
            acknowledged = sum(entry["acknowledged"] for entry in active)
            return {
                "baseline_at": self.state["baseline_at"],
                "read_offset": acknowledged
                + (self.pending.end_offset - self.pending.start_offset if self.pending else 0),
                "acknowledged_offset": acknowledged,
                "pending_bytes": pending_bytes,
                "parse_errors": self.state["parse_errors"],
                "last_read_at": self.last_read_at,
                "gaps": list(self.state["gaps"][:100]),
            }

    def acknowledge_gaps(self, ids: set[str]) -> None:
        with self.lock:
            self.state["gaps"] = [gap for gap in self.state["gaps"] if gap["id"] not in ids]
            self.save()
