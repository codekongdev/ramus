"""Executor message table entries and the errors built from them (roadmap 9.3)."""

from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.models import RunError
from ramus_api.modules.execution.domain.state import RunFailure
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import http_error_code

MESSAGES = {
    codes.AI_CONNECTION_REQUIRED: "AI 연결을 먼저 설정해 주세요.",
    codes.ACTIVE_RUN_EXISTS: "이미 진행 중인 AI 실행이 있습니다.",
    codes.RUN_NOT_CANCELLABLE: "이미 끝난 AI 실행은 중단할 수 없습니다.",
    codes.RUN_NOT_RETRYABLE: "실패했거나 중단한 AI 실행만 다시 시도할 수 있습니다.",
    codes.LLM_UNAVAILABLE: "AI 요청을 처리하지 못했습니다. 다시 시도해 주세요.",
    codes.LLM_OUTPUT_INVALID: "AI 응답 형식이 올바르지 않습니다. 다시 시도해 주세요.",
    codes.LLM_TIMEOUT: "AI 응답이 제한 시간 안에 오지 않았습니다. 다시 시도해 주세요.",
    codes.RUN_INTERRUPTED: "AI 실행이 중간에 끊겼습니다. 다시 시도해 주세요.",
    codes.RUN_TIMED_OUT: "AI 실행이 너무 오래 대기해 멈췄습니다. 다시 시도해 주세요.",
    codes.RUN_CREDENTIAL_MISMATCH: "요청한 계정의 AI 연결로만 실행할 수 있습니다.",
}

_STATUSES = {
    codes.AI_CONNECTION_REQUIRED: 409,
    codes.ACTIVE_RUN_EXISTS: 409,
    codes.RUN_NOT_CANCELLABLE: 409,
    codes.RUN_NOT_RETRYABLE: 409,
}
_HTTP_FALLBACKS = {codes.FORBIDDEN: 403, codes.NOT_FOUND: 404}

register_error_messages(MESSAGES)


def business_error(code: str) -> BusinessError:
    """A user-facing error for an executor code or one of the HTTP fallback codes."""
    if code in _HTTP_FALLBACKS:
        status = _HTTP_FALLBACKS[code]
        fallback_code, message = http_error_code(status)
        return BusinessError(fallback_code, message, status=status)
    return BusinessError(code, message_for(code), status=_STATUSES[code])


def _is_registered(code: str) -> bool:
    try:
        message_for(code)
    except KeyError:
        return False
    return True


def normalize_failure(failure: RunFailure) -> RunFailure:
    """Codes without a message (e.g. a provider-specific gateway code) are stored as LLM_UNAVAILABLE."""
    if _is_registered(failure.code):
        return failure
    return RunFailure(codes.LLM_UNAVAILABLE, retryable=failure.retryable)


def run_error(failure: RunFailure) -> RunError:
    return RunError(failure.code, message_for(failure.code), failure.retryable)
