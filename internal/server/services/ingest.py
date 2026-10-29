import time

from internal.crawler.evidence import EvidenceStore, verify
from internal.crawler.rules import identify, mask_ip, unknown_hint
from internal.protocol import Batch, Heartbeat, event_identity
from internal.storage.database import Database


class PositionConflict(ValueError):
    pass


def ingest(database: Database, batch: Batch, mode: str, evidence: EvidenceStore) -> dict:
    now = time.time()
    snapshots = evidence.snapshot()
    rules = evidence.rules.snapshot()
    classified = []
    for event in batch.events:
        rule = identify(event.user_agent, rules)
        if rule:
            classified.append(
                (event, rule, verify(rule, str(event.client_ip), mode, snapshots, now))
            )
        else:
            classified.append((event, None, None))
    inserted = 0
    with database.transaction() as conn:
        generation = conn.execute(
            "SELECT acknowledged_offset FROM generations WHERE source_id=? AND generation=?",
            (batch.source_id, batch.generation),
        ).fetchone()
        acknowledged = generation[0] if generation else batch.start_offset
        if batch.start_offset > acknowledged:
            raise PositionConflict("non-contiguous source interval")
        if batch.end_offset <= acknowledged:
            return {
                "batch_id": batch.batch_id,
                "acknowledged_offset": batch.end_offset,
                "inserted": 0,
            }
        # Rebatching after a crash may include an already acknowledged prefix.
        boundaries = {batch.start_offset, batch.end_offset}
        boundaries.update(item.offset for item in [*batch.events, *batch.issues])
        if acknowledged not in boundaries:
            raise PositionConflict("acknowledged boundary is not aligned")
        for event, rule, verification in classified:
            if event.offset < acknowledged:
                continue
            if rule:
                values = dict(
                    id=event_identity(batch.source_id, batch.generation, event.offset),
                    site_id=batch.site_id,
                    occurred_at=event.occurred_at.timestamp(),
                    received_at=now,
                    path=event.path,
                    method=event.method,
                    status=event.status,
                    crawler=rule.token,
                    name=rule.name,
                    operator=rule.operator,
                    product_attribution=rule.attribution,
                    masked_ip=mask_ip(str(event.client_ip)),
                    rule_version=rule.version,
                    **verification,
                )
                keys = ",".join(values)
                placeholders = ",".join("?" for _ in values)
                inserted += conn.execute(
                    f"INSERT OR IGNORE INTO events ({keys}) VALUES ({placeholders})",
                    tuple(values.values()),
                ).rowcount
            else:
                hint = unknown_hint(event.user_agent)
                if hint:
                    conn.execute(
                        """INSERT INTO unknown_agents VALUES(?,?,1,?)
                        ON CONFLICT(fingerprint) DO UPDATE SET request_count=request_count+1,
                        last_seen_at=MAX(last_seen_at,excluded.last_seen_at)""",
                        (*hint, event.occurred_at.timestamp()),
                    )
        conn.execute(
            "INSERT INTO generations VALUES(?,?,?) ON CONFLICT(source_id,generation) DO UPDATE SET acknowledged_offset=excluded.acknowledged_offset",
            (batch.source_id, batch.generation, batch.end_offset),
        )
        conn.execute(
            "INSERT OR IGNORE INTO receipts VALUES(?,?,?,?,?)",
            (batch.batch_id, batch.source_id, batch.generation, batch.end_offset, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO collector_health(source_id) VALUES(?)", (batch.source_id,)
        )
        conn.execute(
            "UPDATE collector_health SET log_received_at=?,processed_at=? WHERE source_id=?",
            (now, now, batch.source_id),
        )
        conn.execute(
            "DELETE FROM unknown_agents WHERE fingerprint NOT IN (SELECT fingerprint FROM unknown_agents ORDER BY last_seen_at DESC LIMIT 100)"
        )
    return {
        "batch_id": batch.batch_id,
        "acknowledged_offset": batch.end_offset,
        "inserted": inserted,
    }


def heartbeat(database: Database, message: Heartbeat, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    with database.transaction() as conn:
        existing = conn.execute(
            "SELECT * FROM collector_health WHERE source_id=?", (message.source_id,)
        ).fetchone()
        if (
            existing
            and existing["instance_id"] == message.instance_id
            and existing["sequence"] >= message.sequence
        ):
            return {"accepted": True}
        conn.execute(
            "INSERT OR IGNORE INTO collector_health(source_id) VALUES(?)", (message.source_id,)
        )
        conn.execute(
            """UPDATE collector_health SET instance_id=?,sequence=?,heartbeat_at=?,baseline_at=?,
            last_read_at=?,state=?,error_code=?,read_offset=?,acknowledged_offset=?,pending_bytes=?,parse_errors=?
            WHERE source_id=?""",
            (
                message.instance_id,
                message.sequence,
                now,
                message.baseline_at.timestamp(),
                message.last_read_at.timestamp() if message.last_read_at else None,
                message.state,
                message.error_code,
                message.read_offset,
                message.acknowledged_offset,
                message.pending_bytes,
                message.parse_errors,
                message.source_id,
            ),
        )
        for gap in message.gaps:
            conn.execute(
                "INSERT OR IGNORE INTO gaps VALUES(?,?,?,?,?,?,?)",
                (
                    gap.id,
                    message.source_id,
                    gap.reason,
                    gap.detected_at.timestamp(),
                    gap.generation,
                    gap.start_offset,
                    gap.end_offset,
                ),
            )
    return {"accepted": True}


def purge(database: Database, now: float | None = None) -> int:
    now = time.time() if now is None else now
    with database.transaction() as conn:
        deleted = conn.execute(
            "DELETE FROM events WHERE occurred_at<?", (now - 30 * 86400,)
        ).rowcount
        conn.execute("DELETE FROM receipts WHERE received_at<?", (now - 30 * 86400,))
        conn.execute("DELETE FROM sessions WHERE expires_at<?", (now,))
    # Generation boundaries intentionally outlive event/receipt retention.
    return deleted
