"""Page queries and bounded exports over the same event population."""

import csv
import io
import time
from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from internal.server.services.filters import EventFilter, bounds
from internal.server.services.queries import ORIGIN_NOTE, health

EXPORT_ROWS = 10000
EXPORT_BYTES = 20 * 1024 * 1024


def observation(state, first, stop, now=None):
    now = time.time() if now is None else now
    baseline = state.get("baseline_at")
    if baseline is None or stop.timestamp() <= baseline or first.timestamp() > now:
        return {
            "state": "unobserved",
            "note": "所选范围尚未建立有效观测，不能据此判断页面没有访问。",
        }
    reasons = []
    if first.timestamp() < baseline:
        reasons.append("包含首次启用前的时段")
    if first.timestamp() < now - 30 * 86400:
        reasons.append("超出默认 30 天明细保留窗口")
    if state.get("gaps") or state.get("parse_errors"):
        reasons.append("存在采集缺口或解析异常")
    if state["overall"] != "healthy":
        reasons.append("采集尚未确认完整或正在补采")
    if (
        stop.timestamp()
        > (datetime.fromtimestamp(now, first.tzinfo) + timedelta(days=1))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    ):
        reasons.append("包含未来日期")
    return {
        "state": "incomplete" if reasons else "observed",
        "note": "；".join(reasons)
        if reasons
        else "当前来源未报告完整性异常；未观察仅指该范围和条件下无保留记录。",
    }


def page_list(database, site, filters: EventFilter, limit=20, offset=0):
    where, values = filters.where(site)
    with database.read() as conn:
        conn.execute("BEGIN")
        summary = dict(
            conn.execute(
                f"SELECT COUNT(*) requests, COUNT(DISTINCT path) pages, COALESCE(SUM(verification='verified'),0) verified FROM events WHERE {where}",
                values,
            ).fetchone()
        )
        rows = [
            dict(row)
            for row in conn.execute(
                f"""SELECT path,COUNT(*) requests,SUM(verification='verified') verified,
            SUM(status BETWEEN 200 AND 299) successful,COUNT(DISTINCT crawler) crawlers,
            MAX(occurred_at) last_visit FROM events WHERE {where}
            GROUP BY path ORDER BY requests DESC,path ASC LIMIT ? OFFSET ?""",
                (*values, limit, offset),
            )
        ]
    return {
        "items": rows,
        "total": summary["pages"],
        "summary": summary,
        "timezone": site["timezone"],
    }


def page_detail(database, site, filters: EventFilter, path, timeout=90):
    filters = replace(filters, path=path)
    where, values = filters.where(site)
    first, stop = bounds(site["timezone"], filters.days, filters.start, filters.end)
    state = health(database, site["source_id"], timeout)
    with database.read() as conn:
        conn.execute("BEGIN")
        summary = dict(
            conn.execute(
                f"SELECT COUNT(*) requests,COALESCE(SUM(verification='verified'),0) verified,MAX(occurred_at) last_visit FROM events WHERE {where}",
                values,
            ).fetchone()
        )
        crawlers = [
            dict(row)
            for row in conn.execute(
                f"SELECT crawler,COALESCE((SELECT r.name FROM crawler_rules r WHERE r.token=events.crawler),MIN(name)) name,COUNT(*) requests FROM events WHERE {where} GROUP BY crawler ORDER BY requests DESC,crawler",
                values,
            )
        ]
        statuses = [
            dict(row)
            for row in conn.execute(
                f"SELECT status,COUNT(*) requests FROM events WHERE {where} GROUP BY status ORDER BY status",
                values,
            )
        ]
        trend = []
        day = first
        while day < stop:
            next_day = day + timedelta(days=1)
            coverage = observation(state, day, next_day)["state"]
            count = conn.execute(
                f"SELECT COUNT(*) FROM events WHERE {where} AND occurred_at>=? AND occurred_at<?",
                (*values, day.timestamp(), next_day.timestamp()),
            ).fetchone()[0]
            trend.append(
                {
                    "date": day.date().isoformat(),
                    "requests": None if coverage == "unobserved" else count,
                    "coverage": coverage,
                }
            )
            day = next_day
    return {
        "path": path,
        "summary": summary,
        "crawlers": crawlers,
        "statuses": statuses,
        "trend": trend,
        "observation": observation(state, first, stop),
        "timezone": site["timezone"],
    }


def csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def export_events(database, site, filters):
    where, values = filters.where(site)
    fields = [
        "occurred_at",
        "path",
        "method",
        "status",
        "crawler",
        "name",
        "verification",
        "rule_version",
        "product_attribution",
        "evidence_source",
        "evidence_version",
        "evidence_fetched_at",
        "evidence_expires_at",
    ]
    with database.read() as conn:
        conn.execute("BEGIN")
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM events WHERE {where} ORDER BY occurred_at DESC,id DESC LIMIT ?",
            (*values, EXPORT_ROWS + 1),
        ).fetchall()
    if len(rows) > EXPORT_ROWS:
        raise ValueError("导出超过 10000 条，请缩小日期或筛选范围")
    output = [b"\xef\xbb\xbf"]
    size = 3

    def append(values):
        nonlocal size
        line = io.StringIO(newline="")
        csv.writer(line).writerow(values)
        encoded = line.getvalue().encode("utf-8")
        size += len(encoded)
        if size > EXPORT_BYTES:
            raise ValueError("导出超过 20 MiB，请缩小日期或筛选范围")
        output.append(encoded)

    append([*fields, "timezone", "origin_note"])
    for row in rows:
        values = list(row)
        for index, field in enumerate(fields):
            if (
                field in {"occurred_at", "evidence_fetched_at", "evidence_expires_at"}
                and values[index] is not None
            ):
                values[index] = datetime.fromtimestamp(
                    values[index], ZoneInfo(site["timezone"])
                ).isoformat()
        append([csv_cell(value) for value in [*values, site["timezone"], ORIGIN_NOTE]])
    return b"".join(output)
