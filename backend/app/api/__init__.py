from fastapi import APIRouter

from . import admin, auth, me, tags

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(me.router)
api.include_router(admin.router)
api.include_router(tags.router)
