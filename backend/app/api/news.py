"""News Room API (docs/build/prompt4-api.md): calendar, today, next, week ahead, timeline, event detail,
prefs and the event-currency → instrument map."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import delete, select

from ..core.deps import AdminUser, CurrentUser, Db
from ..models import Instrument, NewsInstrumentMap, utcnow
from ..schemas.news import (
    EventDetailOut,
    EventsOut,
    InstrumentMapRow,
    NextOut,
    PrefsIn,
    PrefsOut,
    StatusOut,
    TimelineOut,
    TodayOut,
    WeekAheadOut,
)
from ..services import audit, market_prefs
from ..services.news import queries, tagging

router = APIRouter(prefix="/news", tags=["news"])

IMPACTS = {"high", "medium", "low", "holiday", "none"}


def _csv(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


@router.get("/status", response_model=StatusOut)
def get_status(_: CurrentUser, db: Db) -> dict:
    return queries.status(db, utcnow())


@router.get("/events", response_model=EventsOut)
def list_events(
    user: CurrentUser,
    db: Db,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    currencies: str | None = None,
    impacts: str | None = None,
    mine: bool = False,
) -> dict:
    wanted = [i.lower() for i in _csv(impacts)]
    if any(i not in IMPACTS for i in wanted):
        raise HTTPException(422, "impacts are high, medium, low, holiday or none.")
    if from_ and to and (to - from_).days > 62:
        raise HTTPException(422, "Ask for at most two months at a time.")
    return queries.list_events(
        db, user, utcnow(), start=from_, end=to, currencies=_csv(currencies), impacts=wanted, mine=mine
    )


@router.get("/events/{event_id}", response_model=EventDetailOut)
def get_event(event_id: int, user: CurrentUser, db: Db) -> dict:
    out = queries.detail(db, user, event_id, utcnow())
    if out is None:
        raise HTTPException(404, "That event doesn't exist.")
    return out


@router.get("/today", response_model=TodayOut)
def get_today(user: CurrentUser, db: Db) -> dict:
    return queries.today(db, user, utcnow())


@router.get("/next", response_model=NextOut)
def get_next(user: CurrentUser, db: Db, mine: bool = True) -> dict:
    return queries.next_event(db, user, utcnow(), mine=mine)


@router.get("/week-ahead", response_model=WeekAheadOut)
def get_week_ahead(user: CurrentUser, db: Db, start: date | None = None, mine: bool = False) -> dict:
    return queries.week_ahead(db, user, utcnow(), start=start, mine=mine)


@router.get("/timeline", response_model=TimelineOut)
def get_timeline(
    user: CurrentUser, db: Db, date_: Annotated[date | None, Query(alias="date")] = None, mine: bool = True
) -> dict:
    return queries.timeline(db, user, utcnow(), day=date_, mine=mine)


# ---- prefs and the instrument map ---------------------------------------------------------------


def _prefs_out(db, user) -> dict:
    prefs = market_prefs.get_prefs(db, user)
    available = db.execute(select(Instrument.symbol, Instrument.name).order_by(Instrument.symbol)).all()
    return {
        "instruments": list(prefs.instruments or []),
        "news_window_minutes": prefs.news_window_minutes,
        "available": [{"code": s, "name": n} for s, n in available],
    }


@router.get("/prefs", response_model=PrefsOut)
def get_prefs(user: CurrentUser, db: Db) -> dict:
    return _prefs_out(db, user)


@router.patch("/prefs", response_model=PrefsOut)
def update_prefs(body: PrefsIn, user: CurrentUser, db: Db) -> dict:
    if body.instruments is not None:
        known = set(db.scalars(select(Instrument.symbol)))
        unknown = [i for i in body.instruments if i not in known]
        if unknown:
            raise HTTPException(422, f"Unknown instrument: {', '.join(unknown)}.")
    market_prefs.save_prefs(
        db, user, instruments=body.instruments, news_window_minutes=body.news_window_minutes
    )
    tagging.retag(db, user_id=user.id)
    return _prefs_out(db, user)


@router.get("/instrument-map", response_model=list[InstrumentMapRow])
def get_instrument_map(_: CurrentUser, db: Db) -> list[dict]:
    rows = db.scalars(select(NewsInstrumentMap).order_by(NewsInstrumentMap.currency, NewsInstrumentMap.id))
    return [{"currency": r.currency, "instrument": r.instrument} for r in rows]


@router.put("/instrument-map", response_model=list[InstrumentMapRow])
def put_instrument_map(body: list[InstrumentMapRow], admin: AdminUser, db: Db) -> list[dict]:
    known = set(db.scalars(select(Instrument.symbol)))
    unknown = sorted({r.instrument for r in body if r.instrument not in known})
    if unknown:
        raise HTTPException(422, f"Unknown instrument: {', '.join(unknown)}.")
    pairs = list(dict.fromkeys((r.currency, r.instrument) for r in body))
    db.execute(delete(NewsInstrumentMap))
    db.add_all(NewsInstrumentMap(currency=c, instrument=i) for c, i in pairs)
    audit.record(db, "news.instrument_map", actor=admin, target_type="news", meta={"rows": len(pairs)})
    db.commit()
    tagging.retag(db)
    return get_instrument_map(admin, db)
