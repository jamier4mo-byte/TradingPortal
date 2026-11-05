"""Trading Portal API. Serves the built front end from frontend/dist when it exists."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from . import __version__
from .config import FRONTEND_DIST
from .db import engine

app = FastAPI(title="Trading Portal", version=__version__)


@app.get("/api/health")
def health() -> dict:
    with engine.connect() as conn:
        db_ok = conn.execute(text("select 1")).scalar() == 1
    return {
        "app": "Trading Portal",
        "version": __version__,
        "db_ok": db_ok,
        "frontend_built": (FRONTEND_DIST / "index.html").exists(),
    }


if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    """Any non-API path returns a real file from dist if there is one, else index.html."""
    if path.startswith("api/"):
        return {"detail": "Not Found"}
    candidate = (FRONTEND_DIST / path).resolve()
    if path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"detail": "Front end not built. Run `make build` (or `make dev` for the Vite dev server)."}
