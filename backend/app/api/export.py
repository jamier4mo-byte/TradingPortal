"""Admin "Export everything": a streamed zip of a consistent database snapshot plus every screenshot."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..core.deps import AdminUser, Db, heavy_endpoint
from ..services import audit
from ..services.export_all import export_filename, stream_everything

router = APIRouter(tags=["admin"])


@router.get("/admin/export", include_in_schema=False, dependencies=[Depends(heavy_endpoint)])
def export_everything(admin: AdminUser, db: Db) -> StreamingResponse:
    audit.record(db, "export.everything", actor=admin, target_type="app")
    db.commit()
    body = stream_everything(db, admin)
    return StreamingResponse(
        body,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename()}"',
            "Cache-Control": "no-store",
        },
    )
