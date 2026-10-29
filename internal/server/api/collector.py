from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from internal.crawler.rules import coverage
from internal.protocol import Batch, Heartbeat, SourceMessage
from internal.server.dependencies import ServerContext
from internal.server.services import queries
from internal.server.services.ingest import PositionConflict, heartbeat, ingest


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config
    evidence = context.evidence
    session = context.session
    site = context.site
    collector_site = context.collector_site

    @router.post("/api/collector/preflight")
    def preflight(payload: SourceMessage, authorization: Annotated[str | None, Header()] = None):
        current_site = collector_site(payload, authorization)
        return {"ok": True, "client_ip_mode": current_site["client_ip_mode"], "protocol_version": 1}

    @router.post("/api/collector/batches")
    def receive_batch(payload: Batch, authorization: Annotated[str | None, Header()] = None):
        current_site = collector_site(payload, authorization)
        try:
            return ingest(database, payload, current_site["client_ip_mode"], evidence)
        except PositionConflict:
            raise HTTPException(409, "来源位置不连续，请检查采集状态") from None

    @router.post("/api/collector/heartbeat")
    def receive_heartbeat(
        payload: Heartbeat, authorization: Annotated[str | None, Header()] = None
    ):
        collector_site(payload, authorization)
        return heartbeat(database, payload)

    @router.get("/api/collector/health", dependencies=[Depends(session)])
    def collector_health():
        return queries.health(database, site()["source_id"], config.heartbeat_timeout)

    @router.get("/api/crawlers", dependencies=[Depends(session)])
    def crawlers():
        return {"rules": coverage(context.evidence.rules.snapshot()), "rule_scope": "按启用规则识别完整 UA 词；核验状态独立展示；历史不回算"}

    @router.get("/api/unknown-agents", dependencies=[Depends(session)])
    def unknown_agents():
        with database.read() as conn:
            return {
                "items": [
                    dict(row)
                    for row in conn.execute(
                        "SELECT hint,request_count,last_seen_at FROM unknown_agents ORDER BY last_seen_at DESC LIMIT 100"
                    )
                ]
            }

    return router
