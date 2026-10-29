"""Application assembly. Domain behavior lives in services and api modules."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from internal.config import ServerConfig
from internal.server.api import analytics, auth, collector, inventory, rules, site, system
from internal.server.dependencies import create_context
from internal.server.lifecycle import build_lifespan
from internal.server.middleware import BodyLimit, invalid_request


def create_app(config: ServerConfig, *, refresh_evidence: bool | None = None,
               refresh_sitemap: bool = True) -> FastAPI:
    context = create_context(config)
    app = FastAPI(
        title="geo-monitor", version="0.1.0",
        lifespan=build_lifespan(context, refresh_evidence, refresh_sitemap)
    )
    app.add_middleware(BodyLimit)
    app.add_exception_handler(RequestValidationError, invalid_request)
    app.state.database = context.database
    app.state.evidence = context.evidence
    app.state.sitemap = context.sitemap
    app.state.config = config
    app.state.maintenance_error = False
    for routes in (auth, site, collector, analytics, inventory, rules, system):
        app.include_router(routes.build_router(context))
    return app
