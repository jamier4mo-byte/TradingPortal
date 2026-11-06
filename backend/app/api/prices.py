"""Prices for the Hub: search, pins, quotes, sparklines, the credit meter. See docs/build/prompt4-api.md."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..core.deps import CurrentUser, Db
from ..schemas.prices import (
    OkOut,
    PinIn,
    PinOrderIn,
    PinOut,
    PinsOut,
    PriceSettingsIn,
    QuoteOut,
    QuotesOut,
    SearchOut,
    SparklineOut,
    UsageOut,
)
from ..services.prices import service as prices
from ..services.prices.service import PriceError

router = APIRouter(prefix="/prices", tags=["prices"])

Symbol = Annotated[str, Query(min_length=1, max_length=32)]


def _http(exc: PriceError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


@router.get("/search", response_model=SearchOut)
def search(user: CurrentUser, db: Db, q: Annotated[str, Query(min_length=1, max_length=40)]) -> SearchOut:
    return SearchOut.model_validate(prices.search(db, user, q))


@router.get("/pins", response_model=PinsOut)
def list_pins(user: CurrentUser, db: Db) -> PinsOut:
    return PinsOut.model_validate({"pins": prices.list_pins(db, user), "max": prices.MAX_PINS})


@router.post("/pins", response_model=PinOut, status_code=201)
def add_pin(body: PinIn, user: CurrentUser, db: Db) -> PinOut:
    try:
        return PinOut.model_validate(prices.add_pin(db, user, body.symbol))
    except PriceError as exc:
        raise _http(exc) from exc


@router.delete("/pins", response_model=OkOut)
def remove_pin(symbol: Symbol, user: CurrentUser, db: Db) -> OkOut:
    try:
        prices.remove_pin(db, user, symbol)
    except PriceError as exc:
        raise _http(exc) from exc
    return OkOut()


@router.put("/pins/order", response_model=PinsOut)
def reorder_pins(body: PinOrderIn, user: CurrentUser, db: Db) -> PinsOut:
    try:
        pins = prices.reorder_pins(db, user, body.symbols)
    except PriceError as exc:
        raise _http(exc) from exc
    return PinsOut.model_validate({"pins": pins, "max": prices.MAX_PINS})


@router.get("/quotes", response_model=QuotesOut)
def quotes(user: CurrentUser, db: Db) -> QuotesOut:
    items = prices.pinned_quotes(db, user)
    return QuotesOut.model_validate(
        {"quotes": items, "usage": prices.usage(db, user), "refresh_seconds": prices.REFRESH_SECONDS}
    )


@router.get("/quote", response_model=QuoteOut)
def quote(symbol: Symbol, user: CurrentUser, db: Db) -> QuoteOut:
    try:
        return QuoteOut.model_validate(prices.get_quote(db, user, symbol))
    except PriceError as exc:
        raise _http(exc) from exc


@router.get("/sparkline", response_model=SparklineOut)
def sparkline(symbol: Symbol, user: CurrentUser, db: Db) -> SparklineOut:
    try:
        return SparklineOut.model_validate(prices.get_sparkline(db, user, symbol))
    except PriceError as exc:
        raise _http(exc) from exc


@router.get("/usage", response_model=UsageOut)
def usage(user: CurrentUser, db: Db) -> UsageOut:
    return UsageOut.model_validate(prices.usage(db, user))


@router.patch("/settings", response_model=UsageOut)
def update_settings(body: PriceSettingsIn, user: CurrentUser, db: Db) -> UsageOut:
    return UsageOut.model_validate(
        prices.update_settings(
            db,
            user,
            allow_background_jobs=body.allow_background_jobs,
            background_daily_cap=body.background_daily_cap,
        )
    )
