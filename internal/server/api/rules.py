import time

from fastapi import APIRouter, Depends, HTTPException

from internal.crawler.catalog import RuleConflict, RuleMissing
from internal.server.dependencies import ServerContext
from internal.server.schemas import CrawlerRuleInput


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter(dependencies=[Depends(context.session)])
    store = context.evidence.rules

    def describe(row, snapshots):
        snapshot = snapshots.get(row["token"])
        state = "not_configured"
        if row["evidence_url"]:
            state = "unavailable"
            if snapshot and snapshot["source"] == row["evidence_url"] and snapshot["available"]:
                state = "available" if snapshot["expires_at"] > time.time() else "expired"
        return dict(
            row,
            enabled=bool(row["enabled"]),
            evidence_state=state,
            evidence_fetched_at=snapshot["fetched_at"] if snapshot else None,
        )

    @router.get("/api/crawler-rules")
    def list_rules():
        snapshots = context.evidence.snapshot()
        return {"items": [describe(row, snapshots) for row in store.records()], "limit": 256}

    def save(payload, token=None):
        if token is not None and (payload.token != token or payload.revision is None):
            raise HTTPException(400, "规则标识不可修改，编辑需携带当前修订号")
        if token is None and payload.revision is not None:
            raise HTTPException(400, "新增规则不能指定修订号")
        try:
            row = store.save(payload.model_dump(exclude={"revision"}), payload.revision)
        except RuleConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except RuleMissing as exc:
            raise HTTPException(404, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return describe(row, context.evidence.snapshot())

    @router.post("/api/crawler-rules", status_code=201)
    def create_rule(payload: CrawlerRuleInput):
        return save(payload)

    @router.put("/api/crawler-rules/{token}")
    def update_rule(token: str, payload: CrawlerRuleInput):
        return save(payload, token)

    @router.post("/api/crawler-rules/{token}/refresh-evidence")
    def refresh_evidence(token: str):
        row = store.get(token)
        if not row:
            raise HTTPException(404, "规则不存在")
        if not row["enabled"] or not row["evidence_url"]:
            raise HTTPException(400, "请先启用规则并配置核验来源")
        context.evidence.refresh(token=token)
        return describe(store.get(token), context.evidence.snapshot())

    return router
