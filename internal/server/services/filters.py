"""Shared, validated event conditions for lists, aggregates and exports."""

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as day_time
from zoneinfo import ZoneInfo

VERIFICATIONS = {
    "verified",
    "ua_only",
    "ip_mismatch",
    "evidence_unavailable",
    "client_ip_unknown",
}


def bounds(timezone, days=7, start=None, end=None, now=None):
    if days not in {1, 7, 30}:
        raise ValueError("不支持的时间范围")
    start, end = start or None, end or None
    zone = ZoneInfo(timezone)
    today = datetime.fromtimestamp(time.time() if now is None else now, zone).date()
    if (start is None) != (end is None):
        raise ValueError("开始和结束日期需要同时填写")
    first = date.fromisoformat(start) if start else today - timedelta(days=days - 1)
    last = date.fromisoformat(end) if end else today
    if first > last or (last - first).days > 366:
        raise ValueError("日期范围无效或超过一年")
    return datetime.combine(first, day_time(), zone), datetime.combine(
        last + timedelta(days=1), day_time(), zone
    )


def literal_like(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@dataclass(frozen=True)
class EventFilter:
    days: int = 7
    start: str | None = None
    end: str | None = None
    crawler: str | None = None
    q: str = ""
    status: str = ""
    verification: str = ""
    path: str | None = None

    def __post_init__(self):
        if len(self.q) > 200 or (self.crawler and len(self.crawler) > 100):
            raise ValueError("筛选过长")
        if self.status and not re.fullmatch(r"[1-5](?:xx|[0-9]{2})", self.status):
            raise ValueError("状态码无效")
        if self.verification and self.verification not in VERIFICATIONS:
            raise ValueError("核验状态无效")
        if self.path is not None and (len(self.path) > 4096 or not self.path.startswith("/")):
            raise ValueError("页面路径无效")
        if any(ord(char) < 32 for char in self.q + (self.path or "")):
            raise ValueError("路径含控制字符")

    def where(self, site, alias=""):
        prefix = alias + "." if alias else ""
        first, stop = bounds(site["timezone"], self.days, self.start, self.end)
        clauses = [f"{prefix}site_id=?", f"{prefix}occurred_at>=?", f"{prefix}occurred_at<?"]
        values = [site["id"], first.timestamp(), stop.timestamp()]
        for field, value in (
            ("crawler", self.crawler),
            ("verification", self.verification),
            ("path", self.path),
        ):
            if value:
                clauses.append(f"{prefix}{field}=?")
                values.append(value)
        if self.q:
            clauses.append(f"{prefix}path LIKE ? ESCAPE '\\'")
            values.append(literal_like(self.q))
        if self.status.endswith("xx"):
            clauses.append(f"{prefix}status BETWEEN ? AND ?")
            values.extend([int(self.status[0]) * 100, int(self.status[0]) * 100 + 99])
        elif self.status:
            clauses.append(f"{prefix}status=?")
            values.append(int(self.status))
        return " AND ".join(clauses), values
