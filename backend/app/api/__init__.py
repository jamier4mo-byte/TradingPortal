from fastapi import APIRouter

from . import admin, alerts, analytics, auth, calendar, export, hub, journal, me, news, prices, tags

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(me.router)
api.include_router(admin.router)
api.include_router(export.router)
api.include_router(tags.router)
api.include_router(journal.router)
api.include_router(analytics.router)
api.include_router(news.router)
api.include_router(prices.router)
api.include_router(alerts.router)
api.include_router(calendar.router)
api.include_router(hub.router)
