"""Trading Portal API. Serves the built front end from frontend/dist when it exists."""

import asyncio
import logging
import math
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .api import api
from .core.csrf import CsrfMiddleware
from .core.settings import FRONTEND_DIST, get_settings
from .db import get_engine
from .services import scheduler

log = logging.getLogger("trading_portal")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the in-app scheduler (F7) on the always-on machine; a DB lease keeps it single-instance."""
    task = asyncio.create_task(scheduler.run_forever()) if scheduler.should_run() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    settings = get_settings()
    settings.require_secret_key()  # production refuses to start without TRADING_PORTAL_SECRET_KEY

    app = FastAPI(
        title="Trading Portal",
        version=__version__,
        docs_url=None if settings.is_production else "/api/docs",
        lifespan=lifespan,
    )
    app.add_middleware(CsrfMiddleware)
    app.include_router(api)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        """422 as usual, but never echo a non-finite input back (JSON can't carry Infinity or NaN)."""

        def clean(value):
            if isinstance(value, float) and not math.isfinite(value):
                return str(value)
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            if isinstance(value, list | tuple):
                return [clean(v) for v in value]
            return value

        return JSONResponse({"detail": clean(jsonable_encoder(exc.errors()))}, 422)

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
