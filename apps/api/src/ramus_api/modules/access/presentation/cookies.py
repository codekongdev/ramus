"""The ``ramus_session`` cookie (docs/contracts.md 1.1)."""

from fastapi import Request, Response

from ramus_api.modules.access.domain.codes import SESSION_TTL

SESSION_COOKIE = "ramus_session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "lax"
SESSION_MAX_AGE_SECONDS = int(SESSION_TTL.total_seconds())


def read_session_token(request: Request) -> str | None:
    """Read from ``request.cookies`` so the cookie does not appear as an OpenAPI parameter."""
    return request.cookies.get(SESSION_COOKIE) or None


def set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE_SECONDS,
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
