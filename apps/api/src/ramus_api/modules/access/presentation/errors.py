"""Maps access rejections to the shared error envelope (docs/contracts.md 1.2)."""

from collections.abc import Iterator
from contextlib import contextmanager

from ramus_api.modules.access.application.errors import (
    AUTH_CODE_EXPIRED,
    AUTH_CODE_INVALID,
    AUTH_RATE_LIMITED,
    AccessRejected,
)
from ramus_api.shared.domain import BusinessError
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import http_error_code

UNAUTHORIZED_STATUS = 401

register_error_messages(
    {
        AUTH_CODE_INVALID: "인증 코드가 올바르지 않습니다. 다시 확인해 주세요.",
        AUTH_CODE_EXPIRED: "인증 코드가 만료되었습니다. 코드를 다시 요청해 주세요.",
        AUTH_RATE_LIMITED: "인증 코드를 너무 자주 요청했습니다. 잠시 후 다시 시도해 주세요.",
    }
)

_STATUSES: dict[str, int] = {
    AUTH_CODE_INVALID: 422,
    AUTH_CODE_EXPIRED: 422,
    AUTH_RATE_LIMITED: 429,
}


def to_business_error(rejection: AccessRejected) -> BusinessError:
    return BusinessError(
        rejection.code, message_for(rejection.code), _STATUSES[rejection.code], rejection.details
    )


@contextmanager
def access_errors() -> Iterator[None]:
    """Re-raises ``AccessRejected`` as the matching ``BusinessError``."""
    try:
        yield
    except AccessRejected as rejection:
        raise to_business_error(rejection) from None


def unauthorized() -> BusinessError:
    code, message = http_error_code(UNAUTHORIZED_STATUS)
    return BusinessError(code, message, UNAUTHORIZED_STATUS)
