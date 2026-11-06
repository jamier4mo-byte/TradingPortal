"""Replay Journal API: strategies, trades, sessions, imports, screenshots, matcher, trash, summary."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from ..core.deps import AdminUser, CurrentUser, Db, ScopeParam, apply_scope, require_owner_or_admin
from ..models import Instrument, JournalSession, Screenshot, Strategy, Trade, User
from ..schemas.auth import OkOut, PublicUserOut
from ..schemas.journal import (
    BriefOut,
    CoverageOut,
    ImportPreviewOut,
    ImportResultOut,
    InstrumentIn,
    InstrumentOut,
    InstrumentUpdateIn,
    MatchIn,
    MatchOut,
    ScreenshotMoveIn,
    ScreenshotOut,
    SessionOut,
    SessionProgressOut,
    SessionUpdateIn,
    StatsOut,
    StrategyIn,
    StrategyOut,
    StrategyUpdateIn,
    SummaryOut,
    TradeIn,
    TradeOut,
    TradeUpdateIn,
    TrashOut,
    UndoOut,
)
from ..services import journal as svc
from ..services import journal_rules as rules
from ..services import matcher
from ..services import screenshots as shots_svc
from ..services.fxreplay import CsvFormatError
from ..services.journal import JournalError
from ..services.screenshots import ScreenshotError
from ..services.storage import get_storage

router = APIRouter(tags=["journal"])


def _err(exc: JournalError | ScreenshotError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


def _can_edit(record, user: User) -> bool:
    return user.is_admin or record.owner_id == user.id


def _owner(db, owner_id: int) -> PublicUserOut:
    return PublicUserOut.model_validate(db.get(User, owner_id))


def coverage_out(cov: rules.Coverage) -> CoverageOut:
    return CoverageOut(
        months=cov.months,
        covered_count=cov.covered_count,
        best_run=cov.best_run,
        current_run=cov.current_run,
        trade_count=cov.trade_count,
        unlocked=cov.unlocked,
        first_month=cov.first_month,
        last_month=cov.last_month,
        next_uncovered=cov.next_uncovered,
        progress=cov.progress,
        target_months=rules.COVERAGE_MONTHS,
        min_trades=rules.MIN_UNLOCK_TRADES,
    )


def strategy_out(db, strategy: Strategy, user: User) -> StrategyOut:
    card = svc.strategy_card(db, strategy)
    card["coverage"] = coverage_out(card["coverage"])
    card["backtest_stats"] = StatsOut(**card["backtest_stats"]) if card["backtest_stats"] else None
    return StrategyOut(
        **{
            k: getattr(strategy, k)
            for k in StrategyOut.model_fields
            if hasattr(strategy, k) and k not in card and k not in ("owner", "can_edit")
        },
        owner=_owner(db, strategy.owner_id),
        can_edit=_can_edit(strategy, user),
        **card,
    )


def screenshot_out(shot: Screenshot) -> ScreenshotOut:
    return ScreenshotOut(
        **{k: getattr(shot, k) for k in ScreenshotOut.model_fields if k not in ("full_url", "thumb_url")},
        full_url=f"/api/screenshots/{shot.id}/full",
        thumb_url=f"/api/screenshots/{shot.id}/thumb",
    )


def trade_out(db, trade: Trade, user: User) -> TradeOut:
    return TradeOut(
        **{
            k: getattr(trade, k)
            for k in TradeOut.model_fields
            if k not in ("owner", "tags", "screenshots", "can_edit")
        },
        owner=_owner(db, trade.owner_id),
        tags=[t for t in trade.tags],
        screenshots=[screenshot_out(s) for s in svc.live_screenshots(trade)],
        can_edit=_can_edit(trade, user),
    )


def session_out(db, session: JournalSession, user: User) -> SessionOut:
    trades = svc.session_trades(db, session)
    return SessionOut(
        **{
            k: getattr(session, k)
            for k in SessionOut.model_fields
            if k not in ("owner", "progress", "stats", "can_edit")
        },
        owner=_owner(db, session.owner_id),
        progress=SessionProgressOut(**svc.session_progress(db, session)),
        stats=StatsOut(**svc.headline_stats(trades)),
        can_edit=_can_edit(session, user),
    )


def _strategy(db, strategy_id: int) -> Strategy:
    try:
        return svc.get_strategy(db, strategy_id)
    except JournalError as exc:
        raise _err(exc) from exc


def _trade(db, trade_id: int) -> Trade:
    try:
        return svc.get_trade(db, trade_id)
    except JournalError as exc:
        raise _err(exc) from exc


def _session(db, session_id: int) -> JournalSession:
    try:
        return svc.get_session(db, session_id)
    except JournalError as exc:
        raise _err(exc) from exc


# ---- instruments ---------------------------------------------------------------------------


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(_: CurrentUser, db: Db) -> list[InstrumentOut]:
    from sqlalchemy import select

    return [
        InstrumentOut.model_validate(i) for i in db.scalars(select(Instrument).order_by(Instrument.symbol))
    ]


@router.post("/instruments", response_model=InstrumentOut, status_code=201)
def create_instrument(body: InstrumentIn, _: AdminUser, db: Db) -> InstrumentOut:
    from sqlalchemy import select

    symbol = body.symbol.strip().upper()
    if db.scalar(select(Instrument).where(Instrument.symbol == symbol)):
        raise HTTPException(409, f"{symbol} already exists.")
    inst = Instrument(**{**body.model_dump(), "symbol": symbol})
    db.add(inst)
    db.commit()
    return InstrumentOut.model_validate(inst)


@router.patch("/instruments/{instrument_id}", response_model=InstrumentOut)
def update_instrument(instrument_id: int, body: InstrumentUpdateIn, _: AdminUser, db: Db) -> InstrumentOut:
    inst = db.get(Instrument, instrument_id)
    if not inst:
        raise HTTPException(404, "No such instrument.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(inst, k, v)
    db.commit()
    return InstrumentOut.model_validate(inst)


# ---- strategies ----------------------------------------------------------------------------


@router.get("/strategies", response_model=list[StrategyOut])
def list_strategies(user: CurrentUser, db: Db, scope: ScopeParam = "everyone") -> list[StrategyOut]:
    from sqlalchemy import select

    stmt = select(Strategy).where(Strategy.deleted_at.is_(None)).order_by(Strategy.updated_at.desc())
    stmt = apply_scope(stmt, Strategy.owner_id, scope, user)
    return [strategy_out(db, s, user) for s in db.scalars(stmt)]


@router.post("/strategies", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyIn, user: CurrentUser, db: Db) -> StrategyOut:
    fields = body.model_dump()
    try:
        strategy = svc.create_strategy(db, user, **fields)
    except JournalError as exc:
        raise _err(exc) from exc
    return strategy_out(db, strategy, user)


@router.get("/strategies/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, user: CurrentUser, db: Db) -> StrategyOut:
    return strategy_out(db, _strategy(db, strategy_id), user)


@router.patch("/strategies/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyUpdateIn, user: CurrentUser, db: Db) -> StrategyOut:
    strategy = _strategy(db, strategy_id)
    try:
        svc.update_strategy(db, user, strategy, **body.model_dump(exclude_unset=True))
    except JournalError as exc:
        raise _err(exc) from exc
    return strategy_out(db, strategy, user)


@router.delete("/strategies/{strategy_id}", response_model=OkOut)
def delete_strategy(strategy_id: int, user: CurrentUser, db: Db) -> OkOut:
    svc.delete_strategy(db, user, _strategy(db, strategy_id))
    return OkOut(message="Strategy moved to Trash for 30 days.")


@router.post("/strategies/{strategy_id}/restore", response_model=StrategyOut)
def restore_strategy(strategy_id: int, user: CurrentUser, db: Db) -> StrategyOut:
    try:
        strategy = svc.get_strategy(db, strategy_id, include_deleted=True)
    except JournalError as exc:
        raise _err(exc) from exc
    svc.restore_strategy(db, user, strategy)
    return strategy_out(db, strategy, user)


@router.get("/strategies/{strategy_id}/profile")
def get_profile(strategy_id: int, _: CurrentUser, db: Db) -> dict | None:
    return svc.strategy_profile(db, _strategy(db, strategy_id))


@router.get("/strategies/{strategy_id}/brief", response_model=BriefOut)
def get_brief(strategy_id: int, user: CurrentUser, db: Db) -> BriefOut:
    """Pre-session brief (U7): profile, rules, the last 2 sessions' notes, the next month to replay."""
    strategy = _strategy(db, strategy_id)
    sessions = [s for s in svc.live_sessions(db, strategy) if s.improve_note.strip()][:2]
    cov = svc.strategy_coverage(db, strategy)
    return BriefOut(
        strategy=strategy_out(db, strategy, user),
        profile=svc.strategy_profile(db, strategy),
        rules=strategy.rules,
        recent_improve_notes=[
            {"session_id": s.id, "note": s.improve_note, "at": s.created_at, "kind": s.kind} for s in sessions
        ],
        next_uncovered=cov.next_uncovered,
    )


# ---- trades --------------------------------------------------------------------------------


@router.get("/strategies/{strategy_id}/trades", response_model=list[TradeOut])
def list_trades(
    strategy_id: int,
    user: CurrentUser,
    db: Db,
    kind: Annotated[str | None, Query(pattern="^(ideal|backtest|missed)$")] = None,
) -> list[TradeOut]:
    strategy = _strategy(db, strategy_id)
    return [trade_out(db, t, user) for t in svc.live_trades(db, strategy, kind)]


@router.post("/strategies/{strategy_id}/trades", response_model=TradeOut, status_code=201)
def create_trade(strategy_id: int, body: TradeIn, user: CurrentUser, db: Db) -> TradeOut:
    strategy = _strategy(db, strategy_id)
    try:
        trade = svc.create_trade(db, user, strategy, **body.model_dump())
    except JournalError as exc:
        raise _err(exc) from exc
    return trade_out(db, trade, user)


@router.get("/trades/{trade_id}", response_model=TradeOut)
def get_trade(trade_id: int, user: CurrentUser, db: Db) -> TradeOut:
    return trade_out(db, _trade(db, trade_id), user)


@router.patch("/trades/{trade_id}", response_model=TradeOut)
def update_trade(trade_id: int, body: TradeUpdateIn, user: CurrentUser, db: Db) -> TradeOut:
    trade = _trade(db, trade_id)
    try:
        svc.update_trade(db, user, trade, **body.model_dump(exclude_unset=True))
    except JournalError as exc:
        raise _err(exc) from exc
    return trade_out(db, trade, user)


@router.delete("/trades/{trade_id}", response_model=OkOut)
def delete_trade(trade_id: int, user: CurrentUser, db: Db) -> OkOut:
    svc.delete_trade(db, user, _trade(db, trade_id))
    return OkOut(message="Trade moved to Trash for 30 days.")


@router.post("/trades/{trade_id}/restore", response_model=TradeOut)
def restore_trade(trade_id: int, user: CurrentUser, db: Db) -> TradeOut:
    try:
        trade = svc.get_trade(db, trade_id, include_deleted=True)
    except JournalError as exc:
        raise _err(exc) from exc
    svc.restore_trade(db, user, trade)
    return trade_out(db, trade, user)


# ---- imports -------------------------------------------------------------------------------


async def _read_csv(file: UploadFile) -> bytes:
    data = await file.read()
    if not data:
        raise HTTPException(400, "The file is empty.")
    return data


@router.post("/strategies/{strategy_id}/imports/preview", response_model=ImportPreviewOut)
async def preview_import(
    strategy_id: int,
    user: CurrentUser,
    db: Db,
    file: Annotated[UploadFile, File()],
    timezone: Annotated[str | None, Form()] = None,
) -> ImportPreviewOut:
    strategy = _strategy(db, strategy_id)
    data = await _read_csv(file)
    try:
        return ImportPreviewOut(
            **svc.preview_import(db, user, strategy, data, timezone=timezone, filename=file.filename or "")
        )
    except CsvFormatError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/strategies/{strategy_id}/imports", response_model=ImportResultOut, status_code=201)
async def confirm_import(
    strategy_id: int,
    user: CurrentUser,
    db: Db,
    file: Annotated[UploadFile, File()],
    destination: Annotated[str, Form()],
    timezone: Annotated[str | None, Form()] = None,
) -> ImportResultOut:
    strategy = _strategy(db, strategy_id)
    data = await _read_csv(file)
    try:
        session, report = svc.confirm_import(
            db, user, strategy, data, destination=destination, timezone=timezone, filename=file.filename or ""
        )
    except CsvFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
    except JournalError as exc:
        raise _err(exc) from exc
    return ImportResultOut(
        session=session_out(db, session, user),
        report=report,
        trades=[trade_out(db, t, user) for t in svc.session_trades(db, session)],
    )


# ---- sessions ------------------------------------------------------------------------------


@router.get("/strategies/{strategy_id}/sessions", response_model=list[SessionOut])
def list_sessions(strategy_id: int, user: CurrentUser, db: Db) -> list[SessionOut]:
    return [session_out(db, s, user) for s in svc.live_sessions(db, _strategy(db, strategy_id))]


@router.post("/strategies/{strategy_id}/sessions", response_model=SessionOut, status_code=201)
def create_manual_session(strategy_id: int, user: CurrentUser, db: Db) -> SessionOut:
    """A manual session groups quick-logged trades so they get the same inbox and recap."""
    strategy = _strategy(db, strategy_id)
    require_owner_or_admin(strategy, user)
    session = JournalSession(
        owner_id=strategy.owner_id if user.is_admin and strategy.owner_id != user.id else user.id,
        strategy_id=strategy.id,
        kind="manual",
        csv_timezone=strategy.csv_timezone,
    )
    db.add(session)
    db.commit()
    return session_out(db, session, user)


@router.get("/journal/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user: CurrentUser, db: Db) -> SessionOut:
    return session_out(db, _session(db, session_id), user)


@router.get("/journal/sessions/{session_id}/trades", response_model=list[TradeOut])
def get_session_trades(session_id: int, user: CurrentUser, db: Db) -> list[TradeOut]:
    return [trade_out(db, t, user) for t in svc.session_trades(db, _session(db, session_id))]


@router.patch("/journal/sessions/{session_id}", response_model=SessionOut)
def update_session(session_id: int, body: SessionUpdateIn, user: CurrentUser, db: Db) -> SessionOut:
    session = _session(db, session_id)
    svc.update_session(db, user, session, improve_note=body.improve_note)
    return session_out(db, session, user)


@router.delete("/journal/sessions/{session_id}", response_model=UndoOut)
def undo_session(session_id: int, user: CurrentUser, db: Db) -> UndoOut:
    session = _session(db, session_id)
    n = svc.undo_session(db, user, session)
    return UndoOut(trades=n, session_id=session.id)


@router.post("/journal/sessions/{session_id}/restore", response_model=UndoOut)
def restore_session(session_id: int, user: CurrentUser, db: Db) -> UndoOut:
    try:
        session = svc.get_session(db, session_id, include_deleted=True)
    except JournalError as exc:
        raise _err(exc) from exc
    n = svc.restore_session(db, user, session)
    return UndoOut(trades=n, session_id=session.id)


@router.post("/journal/sessions/{session_id}/match", response_model=list[MatchOut])
def match_screenshots(session_id: int, body: MatchIn, user: CurrentUser, db: Db) -> list[MatchOut]:
    """Pair dropped files with trades × (Entry, Exit). Nothing is uploaded here; the browser follows up."""
    session = _session(db, session_id)
    trades = svc.session_trades(db, session)
    refs = []
    for i, t in enumerate(trades, start=1):
        live = {s.slot for s in t.screenshots if s.deleted_at is None}
        refs.append(
            matcher.TradeRef(
                id=t.id,
                index=i,
                opened_at=t.opened_at,
                closed_at=t.closed_at,
                filled=tuple(sorted(live & set(matcher.LABELLED))),
            )
        )
    files = [
        matcher.FileRef(name=f.name, captured_at=f.captured_at, time_source=f.time_source) for f in body.files
    ]
    result = matcher.match_files(refs, files, timezone=session.csv_timezone)
    return [MatchOut(**m.__dict__) for m in result.matches]


# ---- screenshots ---------------------------------------------------------------------------


@router.post("/trades/{trade_id}/screenshots", response_model=TradeOut, status_code=201)
async def upload_screenshot(
    trade_id: int,
    user: CurrentUser,
    db: Db,
    file: Annotated[UploadFile, File()],
    slot: Annotated[str, Form()] = "extra",
    thumb: Annotated[UploadFile | None, File()] = None,
    captured_at: Annotated[datetime | None, Form()] = None,
    original_filename: Annotated[str | None, Form()] = None,
) -> TradeOut:
    trade = _trade(db, trade_id)
    data = await file.read()
    thumb_bytes = await thumb.read() if thumb else None
    try:
        shots_svc.add_screenshot(
            db,
            user,
            trade,
            data,
            slot=slot,
            thumb=thumb_bytes or None,
            captured_at=captured_at,
            original_filename=original_filename or file.filename,
        )
    except ScreenshotError as exc:
        raise _err(exc) from exc
    return trade_out(db, trade, user)


def _serve(key: str, content_type: str) -> Response:
    storage = get_storage()
    path = storage.path(key)
    headers = {"Cache-Control": "private, max-age=31536000, immutable"}
    if path:
        return FileResponse(path, media_type=content_type, headers=headers)
    return Response(storage.get(key), media_type=content_type, headers=headers)


@router.get("/screenshots/{shot_id}/full", include_in_schema=False)
def screenshot_full(shot_id: int, _: CurrentUser, db: Db) -> Response:
    try:
        shot = shots_svc.get_screenshot(db, shot_id)
    except ScreenshotError as exc:
        raise _err(exc) from exc
    return _serve(shot.full_key, shot.content_type)


@router.get("/screenshots/{shot_id}/thumb", include_in_schema=False)
def screenshot_thumb(shot_id: int, _: CurrentUser, db: Db) -> Response:
    try:
        shot = shots_svc.get_screenshot(db, shot_id)
    except ScreenshotError as exc:
        raise _err(exc) from exc
    return _serve(shot.thumb_key, "image/webp")


@router.patch("/screenshots/{shot_id}", response_model=ScreenshotOut)
def move_screenshot(shot_id: int, body: ScreenshotMoveIn, user: CurrentUser, db: Db) -> ScreenshotOut:
    try:
        shot = shots_svc.get_screenshot(db, shot_id)
        trade = _trade(db, body.trade_id)
        shots_svc.move_screenshot(db, user, shot, trade=trade, slot=body.slot)
    except ScreenshotError as exc:
        raise _err(exc) from exc
    return screenshot_out(shot)


@router.delete("/screenshots/{shot_id}", response_model=OkOut)
def delete_screenshot(shot_id: int, user: CurrentUser, db: Db) -> OkOut:
    try:
        shots_svc.delete_screenshot(db, user, shots_svc.get_screenshot(db, shot_id))
    except ScreenshotError as exc:
        raise _err(exc) from exc
    return OkOut()


# ---- trash and summary ---------------------------------------------------------------------


@router.get("/journal/trash", response_model=TrashOut)
def get_trash(user: CurrentUser, db: Db) -> TrashOut:
    t = svc.trash(db, user)
    return TrashOut(
        days=t["days"],
        strategies=[strategy_out(db, s, user) for s in t["strategies"]],
        sessions=[session_out(db, s, user) for s in t["sessions"]],
        trades=[trade_out(db, tr, user) for tr in t["trades"]],
    )


@router.get("/journal/summary", response_model=SummaryOut)
def get_summary(user: CurrentUser, db: Db) -> SummaryOut:
    s = svc.summary(db, user)
    return SummaryOut(
        strategies=s["strategies"],
        trades=s["trades"],
        unlocked=s["unlocked"],
        last_session=session_out(db, s["last_session"], user) if s["last_session"] else None,
        my_last_session=session_out(db, s["my_last_session"], user) if s["my_last_session"] else None,
    )
