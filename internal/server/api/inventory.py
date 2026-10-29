from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from internal.server.dependencies import ServerContext, event_filter
from internal.server.schemas import InventoryInput, SitemapInput
from internal.server.services import inventory
from internal.server.services.filters import EventFilter


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config
    session = context.session
    site = context.site

    @router.get("/api/inventory/sitemap", dependencies=[Depends(session)])
    def get_sitemap():
        return context.sitemap.status(site())

    @router.put("/api/inventory/sitemap", dependencies=[Depends(session)])
    def configure_sitemap(payload: SitemapInput):
        try:
            return context.sitemap.configure(site(), payload.url, payload.enabled)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.post("/api/inventory/sitemap/sync", dependencies=[Depends(session)], status_code=202)
    def sync_sitemap():
        try:
            return context.sitemap.request(site())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.post("/api/inventory/import", dependencies=[Depends(session)])
    def import_inventory(payload: InventoryInput):
        try:
            return inventory.import_pages(database, site(), payload.text, payload.format)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.delete("/api/inventory", dependencies=[Depends(session)])
    def remove_inventory(path: str):
        try:
            return inventory.remove_page(database, site(), path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @router.get("/api/inventory", dependencies=[Depends(session)])
    def get_inventory(
        filters: Annotated[EventFilter, Depends(event_filter)],
        state: Literal["", "observed", "unobserved"] = "",
        limit: Annotated[int, Query(ge=1, le=200)] = 20,
        offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    ):
        try:
            return inventory.inventory_list(
                database, site(), filters, state, limit, offset, config.heartbeat_timeout
            )
        except ValueError:
            raise HTTPException(400, "日期或筛选无效") from None

    return router
