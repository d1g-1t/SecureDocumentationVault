from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    _HEADERS: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "0",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Content-Security-Policy": (
            "default-src 'none'; "
            "script-src 'none'; "
            "style-src 'unsafe-inline'; "
            "img-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        ),
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }

    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        for header, value in self._HEADERS.items():
            response.headers[header] = value
        return response
