"""Outbound HTTP for the feeds, Twelve Data and Web Push.

Every outbound call goes through `client()`. Tests and CI never reach Twelve Data, JBlanked or
Forex Factory: under TRADING_PORTAL_ENV=test the default transport refuses every request, so a test
must pass a mock transport (httpx.MockTransport) or a fake provider explicitly.
"""

import httpx

from ..core.settings import get_settings

USER_AGENT = "TradingPortal/1.0"  # generic: never a personal email (Prompt 4 rule)
TIMEOUT = httpx.Timeout(15.0, connect=10.0)


class NetworkBlocked(RuntimeError):
    pass


def _refuse(request: httpx.Request) -> httpx.Response:
    raise NetworkBlocked(f"Real network call blocked in tests: {request.method} {request.url.host}")


def client(transport: httpx.BaseTransport | None = None, **kwargs) -> httpx.Client:
    if transport is None and get_settings().env == "test":
        transport = httpx.MockTransport(_refuse)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **kwargs.pop("headers", {})}
    return httpx.Client(
        transport=transport, timeout=kwargs.pop("timeout", TIMEOUT), headers=headers, **kwargs
    )
