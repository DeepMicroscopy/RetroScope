"""FastAPI factory."""

from __future__ import annotations

from fastapi import FastAPI

from retroscope.api.context import ApiContext
from retroscope.api.routes import actions, captures, health


def create_api_app(context: ApiContext, *, docs_enabled: bool = True) -> FastAPI:
    app = FastAPI(
        title="RetroScope API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.state.retroscope_api_context = context
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(captures.router, prefix="/api/v1")
    app.include_router(actions.router, prefix="/api/v1")
    return app
