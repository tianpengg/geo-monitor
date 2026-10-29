import secrets

from fastapi import APIRouter, Depends, HTTPException

from internal.server.dependencies import ServerContext
from internal.server.schemas import SiteInput
from internal.server.security import token_hash


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config
    session = context.session
    site = context.site

    @router.get("/api/site", dependencies=[Depends(session)])
    def get_site():
        try:
            return site()
        except HTTPException:
            return None

    @router.put("/api/site", dependencies=[Depends(session)])
    def save_site(payload: SiteInput):
        with database.transaction() as conn:
            row = conn.execute("SELECT * FROM site WHERE singleton=1").fetchone()
            if row:
                conn.execute(
                    "UPDATE site SET domain=?,timezone=?,client_ip_mode=? WHERE singleton=1",
                    (payload.domain, payload.timezone, payload.client_ip_mode),
                )
            else:
                conn.execute(
                    "INSERT INTO site(id,source_id,domain,timezone,client_ip_mode) VALUES(?,?,?,?,?)",
                    (
                        secrets.token_hex(16),
                        secrets.token_hex(16),
                        payload.domain,
                        payload.timezone,
                        payload.client_ip_mode,
                    ),
                )
        return site()

    @router.post("/api/site/credentials", dependencies=[Depends(session)])
    def credentials():
        current_site = site()
        token = secrets.token_urlsafe(32)
        with database.transaction() as conn:
            conn.execute("UPDATE site SET token_hash=? WHERE singleton=1", (token_hash(token),))
        return {
            "site_id": current_site["id"],
            "source_id": current_site["source_id"],
            "token": token,
            "server_url": config.public_url,
        }

    return router
