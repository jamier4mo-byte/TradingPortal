"""Trading Portal API. Serves the built front end from frontend/dist when it exists."""

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .api import api
from .core.csrf import CsrfMiddleware
from .core.settings import FRONTEND_DIST, get_settings
from .db import get_engine

log = logging.getLogger("trading_portal")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.require_secret_key()  # production refuses to start without TRADING_PORTAL_SECRET_KEY

    app = FastAPI(
        title="Trading Portal", version=__version__, docs_url=None if settings.is_production else "/api/docs"
    )
    app.add_middleware(CsrfMiddleware)
    app.include_router(api)

    @app.get("/api/health")
    def health() -> dict:
        with get_engine().connect() as conn:
            db_ok = conn.execute(text("select 1")).scalar() == 1
        return {
            "app": "Trading Portal",
            "version": __version__,
            "db_ok": db_ok,
            "frontend_built": (FRONTEND_DIST / "index.html").exists(),
        }

    @app.get("/api/{path:path}", include_in_schema=False)
    def api_not_found(path: str) -> JSONResponse:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Any non-API path returns a real file from dist if there is one, else index.html (never cached)."""
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return JSONResponse(
            {"detail": "Front end not built. Run `make build` (or `make dev` for the Vite dev server)."}
        )

    return app


app = create_app()
