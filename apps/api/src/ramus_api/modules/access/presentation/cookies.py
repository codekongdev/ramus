"""The ``ramus_session`` cookie (docs/contracts.md 1.1)."""

from datetime import UTC, datetime

from fastapi import Request, Response

SESSION_COOKIE = "ramus_session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "lax"


def read_session_token(request: Request) -> str | None:
    """Read from ``request.cookies`` so the cookie does not appear as an OpenAPI parameter."""
    return request.cookies.get(SESSION_COOKIE) or None


def set_session_cookie(response: Response, token: str, *, expires_at: datetime, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max(0, int((expires_at - datetime.now(UTC)).total_seconds())),
        expires=expires_at,
        path=SESSION_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )


def clear_session_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path=SESSION_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
    )
