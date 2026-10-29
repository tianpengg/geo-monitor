import secrets
import time
from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import HTTPException, Query, Request

from internal.config import ServerConfig
from internal.crawler.evidence import EvidenceStore
from internal.protocol import SourceMessage
from internal.server.security import token_hash
from internal.server.services import queries
from internal.server.services.filters import EventFilter
from internal.server.services.sitemap_sync import SitemapSync
from internal.storage.database import Database


def event_filter(
    days: Annotated[int, Query(ge=1, le=30)] = 7,
    start: str | None = None,
    end: str | None = None,
    crawler: str | None = None,
    q: str = "",
    status: str = "",
    verification: str = "",
    path: str | None = None,
):
    try:
        queries.bounds("UTC", days, start, end)
        return EventFilter(days, start, end, crawler, q, status, verification, path)
    except ValueError:
        raise HTTPException(400, "路径、状态码或核验筛选无效") from None


@dataclass
class ServerContext:
    config: ServerConfig
    database: Database
    evidence: EvidenceStore
    session: Callable
    site: Callable
    collector_site: Callable
    sitemap: SitemapSync


def create_context(config: ServerConfig) -> ServerContext:
    database = Database(config.database)
    evidence = EvidenceStore(database, config.evidence_ttl_seconds)

    def session(request: Request) -> dict:
        value = request.cookies.get("geo_session", "")
        with database.read() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_hash=? AND expires_at>?",
                (token_hash(value), time.time()),
            ).fetchone()
        if not row:
            raise HTTPException(401, "请先登录")
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("origin") not in {None, config.public_url}:
                raise HTTPException(403, "请求来源无效")
            if not secrets.compare_digest(
                request.headers.get("x-csrf-token", ""), row["csrf_token"]
            ):
                raise HTTPException(403, "请求校验失败，请刷新后重试")
        return dict(row)

    def site() -> dict:
        with database.read() as conn:
            row = conn.execute(
                "SELECT id,source_id,domain,timezone,client_ip_mode FROM site WHERE singleton=1"
            ).fetchone()
        if not row:
            raise HTTPException(404, "请先配置官网")
        return dict(row)

    def collector_site(message: SourceMessage, authorization: str | None) -> dict:
        token = (
            authorization.removeprefix("Bearer ")
            if authorization and authorization.startswith("Bearer ")
            else ""
        )
        with database.read() as conn:
            row = conn.execute(
                "SELECT * FROM site WHERE id=? AND source_id=?",
                (message.site_id, message.source_id),
            ).fetchone()
        if (
            not row
            or not row["token_hash"]
            or not secrets.compare_digest(token_hash(token), row["token_hash"])
        ):
            raise HTTPException(401, "采集凭据无效")
        return dict(row)

    return ServerContext(config, database, evidence, session, site, collector_site, SitemapSync(database))
