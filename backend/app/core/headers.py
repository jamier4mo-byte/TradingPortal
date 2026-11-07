"""Security headers and a request-body size cap, as two pure-ASGI middlewares (no body buffering).

SecurityHeadersMiddleware adds, to every response:
  Content-Security-Policy      see CSP below. `script-src 'self'` only: the built SPA has no inline
                               script (Vite 8 emits module tags + modulepreload links, no polyfill).
                               `style-src` keeps 'unsafe-inline' because React, `motion` and FullCalendar
                               set `style=` attributes; accepted trade-off (styles can't run code, and
                               script injection is what the policy is for).
  Strict-Transport-Security    production only (Fly terminates TLS and `force_https` redirects).
  Referrer-Policy, X-Content-Type-Options, X-Frame-Options, Permissions-Policy,
  Cross-Origin-Opener-Policy.
  Cache-Control                `no-store` for /api/auth, /api/me and /api/admin answers that don't set
                               their own; `public, immutable` for the hashed /assets; `no-cache` for
                               /sw.js and /index.html. A handler's own Cache-Control always wins.

BodyLimitMiddleware refuses a request body over the route's cap with 413 before the handler reads it:
2 MB for JSON, more for the two multipart upload routes (screenshots 14 MB, CSV imports 6 MB). The
Content-Length header is checked first; a chunked body is counted as it streams and cut off when it
passes the cap.
"""

import re
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .settings import get_settings

CSP_DIRECTIVES = (
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",  # FullCalendar's icon font and Vite-inlined small subsets are data: URIs
    "connect-src 'self'",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
)
CSP = "; ".join(CSP_DIRECTIVES)
CSP_PRODUCTION = CSP + "; upgrade-insecure-requests"
HSTS = "max-age=63072000; includeSubDomains"
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"

NO_STORE_PREFIXES = ("/api/auth/", "/api/me", "/api/admin/")
NO_CACHE_PATHS = ("/sw.js", "/index.html")

DEFAULT_BODY_LIMIT = 2 * 1024 * 1024
# (path regex, cap in bytes). The first match wins; everything else gets DEFAULT_BODY_LIMIT.
BODY_LIMITS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"^/api/trades/\d+/screenshots$"), 14 * 1024 * 1024),  # 12 MB image + 1 MB thumb + form
    (re.compile(r"^/api/strategies/\d+/imports(/preview)?$"), 6 * 1024 * 1024),  # 5 MB CSV + form
)


def body_limit_for(path: str) -> int:
    for pattern, cap in BODY_LIMITS:
        if pattern.match(path):
            return cap
    return DEFAULT_BODY_LIMIT


def security_headers(path: str, *, production: bool) -> list[tuple[bytes, bytes]]:
    headers = [
        (b"content-security-policy", (CSP_PRODUCTION if production else CSP).encode()),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"permissions-policy", PERMISSIONS_POLICY.encode()),
        (b"cross-origin-opener-policy", b"same-origin"),
    ]
    if production:
        headers.append((b"strict-transport-security", HSTS.encode()))
    return headers


def cache_control_for(path: str) -> bytes | None:
    """The default Cache-Control for a path, or None to leave it to the handler."""
    if path.startswith(NO_STORE_PREFIXES):
        return b"no-store"
    if path.startswith("/assets/"):
        return b"public, max-age=31536000, immutable"
    if path in NO_CACHE_PATHS:
        return b"no-cache"
    return None


def _has(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> bool:
    return any(k.lower() == name for k, _ in headers)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        production = get_settings().is_production

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for name, value in security_headers(path, production=production):
                    if not _has(headers, name):
                        headers.append((name, value))
                cache = cache_control_for(path)
                if cache is not None and not _has(headers, b"cache-control"):
                    headers.append((b"cache-control", cache))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        limit = body_limit_for(path)
        declared = next((v for k, v in scope.get("headers", []) if k == b"content-length"), None)
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _reject(send, limit)
            return

        received = 0
        response_started = False
        rejected = False

        async def counting_receive() -> Message:
            """Count the body as it streams; past the cap, answer 413 and hand the app a disconnect.

            (Raising here wouldn't do: FastAPI turns any error while reading the body into a 400.)
            """
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit and not rejected:
                    rejected = True
                    if not response_started:
                        await _reject(send, limit)
                    return {"type": "http.disconnect"}
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if rejected:
                return  # the 413 has already gone out; drop whatever the app says about the disconnect
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, counting_receive, tracking_send)


async def _reject(send: Send, limit: int) -> None:
    mb = limit // (1024 * 1024)
    body = f'{{"detail": "That request is too large (the limit for this endpoint is {mb} MB)."}}'.encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
