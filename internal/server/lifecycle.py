import threading
from contextlib import asynccontextmanager

from internal.server.dependencies import ServerContext
from internal.server.security import password_hash, verify_password
from internal.server.services.ingest import purge


def build_lifespan(context: ServerContext, refresh_evidence: bool | None, refresh_sitemap: bool):
    database, config, evidence = context.database, context.config, context.evidence
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        database.migrate()
        evidence.rules.seed()
        with database.transaction() as conn:
            admin = conn.execute("SELECT * FROM admin WHERE id=1").fetchone()
            password = config.admin_password.get_secret_value()
            if (
                not admin
                or admin["username"] != config.admin_username
                or not verify_password(password, admin["password_hash"])
            ):
                conn.execute(
                    "INSERT OR REPLACE INTO admin VALUES(1,?,?)",
                    (config.admin_username, password_hash(password)),
                )
                conn.execute("DELETE FROM sessions")
        purge(database)
        worker = None
        if config.evidence_enabled if refresh_evidence is None else refresh_evidence:

            def maintenance():
                while not stop.is_set():
                    try:
                        evidence.refresh()
                        purge(database)
                    except Exception:
                        # Neither request bodies nor exception values belong in logs.
                        app.state.maintenance_error = True
                    stop.wait(config.evidence_refresh_seconds)

            worker = threading.Thread(target=maintenance, name="evidence-maintenance", daemon=True)
            worker.start()
        sitemap_worker = None
        if refresh_sitemap:
            context.sitemap.stop.clear()
            sitemap_worker = threading.Thread(
                target=context.sitemap.maintain, name="sitemap-maintenance", daemon=True,
            )
            sitemap_worker.start()
        try:
            yield
        finally:
            stop.set()
            context.sitemap.stop.set()
            context.sitemap.wake.set()
            if worker:
                await __import__("asyncio").to_thread(worker.join, 25)
            if sitemap_worker:
                await __import__("asyncio").to_thread(sitemap_worker.join, 65)

    return lifespan
