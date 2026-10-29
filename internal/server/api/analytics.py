from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from internal.server.dependencies import ServerContext, event_filter
from internal.server.services import analytics, queries
from internal.server.services.filters import EventFilter


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config
    session = context.session
    site = context.site

    @router.get("/api/overview", dependencies=[Depends(session)])
    def get_overview(
        days: Annotated[int, Query(ge=1, le=30)] = 7,
        start: str | None = None,
        end: str | None = None,
    ):
        try:
            return queries.overview(database, site(), days, start, end, config.heartbeat_timeout)
        except ValueError:
            raise HTTPException(400, "日期范围无效") from None

    @router.get("/api/events", dependencies=[Depends(session)])
    def get_events(
        filters: Annotated[EventFilter, Depends(event_filter)],
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        try:
            return queries.details(
                database,
                site(),
                filters.days,
                filters.start,
                filters.end,
                filters.crawler,
                cursor,
                limit,
                filters,
            )
        except ValueError:
            raise HTTPException(400, "日期范围或分页游标无效") from None

    @router.get("/api/events/export", dependencies=[Depends(session)])
    def export_events(filters: Annotated[EventFilter, Depends(event_filter)]):
        try:
            content = analytics.export_events(database, site(), filters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="crawler-visits.csv"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/api/pages", dependencies=[Depends(session)])
    def pages(
        filters: Annotated[EventFilter, Depends(event_filter)],
        limit: Annotated[int, Query(ge=1, le=200)] = 20,
        offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    ):
        try:
            return analytics.page_list(database, site(), filters, limit, offset)
        except ValueError:
            raise HTTPException(400, "日期或筛选无效") from None

    @router.get("/api/pages/detail", dependencies=[Depends(session)])
    def page_detail(filters: Annotated[EventFilter, Depends(event_filter)]):
        if not filters.path:
            raise HTTPException(400, "请选择精确页面路径")
        try:
            return analytics.page_detail(
                database, site(), filters, filters.path, config.heartbeat_timeout
            )
        except ValueError:
            raise HTTPException(400, "日期或筛选无效") from None

    return router
