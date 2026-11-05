"""Double-submit CSRF: a readable cookie must match the X-CSRF-Token header on every unsafe /api call."""

import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .deps import CSRF_COOKIE, CSRF_HEADER
from .settings import get_settings

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def issue_csrf_cookie(response: Response, token: str | None = None) -> str:
    token = token or secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=get_settings().session_days * 86400,
        httponly=False,  # the client reads it and echoes it in the header
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )
    return token


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE and request.url.path.startswith("/api/"):
            cookie = request.cookies.get(CSRF_COOKIE)
            header = request.headers.get(CSRF_HEADER)
            if not cookie or not header or not secrets.compare_digest(cookie, header):
                return JSONResponse(
                    {"detail": "CSRF check failed. Reload the page and try again."}, status_code=403
                )
        response = await call_next(request)
        if (
            request.method == "GET"
            and request.url.path.startswith("/api/")
            and CSRF_COOKIE not in request.cookies
        ):
            issue_csrf_cookie(response)
        return response
