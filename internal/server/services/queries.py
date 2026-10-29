import math
import re
import time
from datetime import timedelta

from internal.server.services.filters import EventFilter, bounds
from internal.storage.database import Database

ORIGIN_NOTE = "数据来自源站日志，可能不包含 CDN 缓存命中或边缘拦截请求。"


def health(database: Database, source_id: str, timeout: int = 90, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    with database.read() as conn:
        row = conn.execute(
            "SELECT * FROM collector_health WHERE source_id=?", (source_id,)
        ).fetchone()
        gaps = [
            dict(item)
            for item in conn.execute(
                "SELECT * FROM gaps WHERE source_id=? ORDER BY detected_at DESC", (source_id,)
            )
        ]
    result = dict(row) if row else {"source_id": source_id}
    heartbeat_at = result.get("heartbeat_at")
    state = result.get("state")
    if heartbeat_at is None:
        overall, message = "not_installed", "待安装或尚未收到首次心跳"
    elif now - heartbeat_at > timeout:
        overall, message = "disconnected", "采集器断连"
    elif state in {"read_error", "auth_error", "protocol_error"}:
        overall, message = "error", "采集异常，请检查错误原因"
    elif state in {"retrying", "backlog"} or result.get("pending_bytes", 0):
        overall, message = "backlog", "正在重试或补采"
    elif gaps or result.get("parse_errors", 0):
        overall, message = "degraded", "存在已知缺口、解析异常或完整性限制"
    else:
        overall, message = "healthy", "采集正常"
    result.update(overall=overall, message=message, gaps=gaps, origin_note=ORIGIN_NOTE)
    return result


def details(
    database: Database,
    site: dict,
    days: int,
    start: str | None,
    end: str | None,
    crawler: str | None,
    cursor: str | None,
    limit: int,
    filters: EventFilter | None = None,
) -> dict:
    where, values = (filters or EventFilter(days, start, end, crawler)).where(site)
    if cursor:
        try:
            timestamp, identity = cursor.split("|", 1)
            timestamp = float(timestamp)
            if not math.isfinite(timestamp) or not re.fullmatch(r"[a-f0-9]{64}", identity):
                raise ValueError("invalid cursor")
        except (ValueError, TypeError):
            raise ValueError("分页游标无效") from None
        where += " AND (occurred_at<? OR (occurred_at=? AND id<?))"
        values.extend([timestamp, timestamp, identity])
    with database.read() as conn:
        items = [
            dict(row)
            for row in conn.execute(
                f"SELECT * FROM events WHERE {where} ORDER BY occurred_at DESC,id DESC LIMIT ?",
                (*values, limit + 1),
            )
        ]
    more = len(items) > limit
    items = items[:limit]
    next_cursor = f"{items[-1]['occurred_at']}|{items[-1]['id']}" if more else None
    return {
        "items": items,
        "next_cursor": next_cursor,
        "timezone": site["timezone"],
        "origin_note": ORIGIN_NOTE,
    }


def overview(
    database: Database, site: dict, days: int, start: str | None, end: str | None, timeout: int
) -> dict:
    first, stop = bounds(site["timezone"], days, start, end)
    parameters = (site["id"], first.timestamp(), stop.timestamp())
    where = "site_id=? AND occurred_at>=? AND occurred_at<?"
    state = health(database, site["source_id"], timeout)
    with database.read() as conn:
        summary = dict(
            conn.execute(
                f"SELECT COUNT(*) requests,COUNT(DISTINCT path) pages,MAX(occurred_at) last_visit FROM events WHERE {where}",
                parameters,
            ).fetchone()
        )
        crawlers = [
            dict(row)
            for row in conn.execute(
                f"SELECT crawler,COALESCE((SELECT r.name FROM crawler_rules r WHERE r.token=events.crawler),MIN(name)) name,COUNT(*) requests,COUNT(DISTINCT path) pages,MAX(occurred_at) last_visit FROM events WHERE {where} GROUP BY crawler ORDER BY requests DESC,crawler",
                parameters,
            )
        ]
        verification = {
            row[0]: row[1]
            for row in conn.execute(
                f"SELECT verification,COUNT(*) FROM events WHERE {where} GROUP BY verification",
                parameters,
            )
        }
        trend = []
        day = first
        while day < stop:
            next_day = day + timedelta(days=1)
            baseline = state.get("baseline_at")
            if baseline is None or next_day.timestamp() <= baseline:
                coverage = "unobserved"
            elif day.timestamp() < baseline or state["gaps"] or state.get("parse_errors", 0):
                coverage = "incomplete"
            elif state["overall"] in {
                "disconnected",
                "error",
                "backlog",
            } and next_day.timestamp() > (state.get("heartbeat_at") or 0):
                coverage = "incomplete"
            else:
                coverage = "observed"
            requests = conn.execute(
                "SELECT COUNT(*) FROM events WHERE site_id=? AND occurred_at>=? AND occurred_at<?",
                (site["id"], day.timestamp(), next_day.timestamp()),
            ).fetchone()[0]
            trend.append(
                {
                    "date": day.date().isoformat(),
                    "requests": None if coverage == "unobserved" else requests,
                    "coverage": coverage,
                }
            )
            day = next_day
    message = None
    if summary["requests"] == 0:
        message = (
            "未观察到可识别的 AI 爬虫访问"
            if state["overall"] == "healthy"
            else "当前无匹配记录，请结合采集状态和观测覆盖判断"
        )
    return {
        "summary": summary,
        "crawlers": crawlers,
        "verification": verification,
        "trend": trend,
        "health": state,
        "empty_message": message,
        "timezone": site["timezone"],
        "origin_note": ORIGIN_NOTE,
    }
