"""Sharing errors are rendered at the request boundary using central messages."""

from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import http_error_code

register_error_messages({"SHARE_TARGET_INVALID": "결론을 보낼 다른 대화를 선택해 주세요."})


def not_found() -> BusinessError:
    code, message = http_error_code(404)
    return BusinessError(code, message, status=404)


def invalid_target() -> BusinessError:
    return BusinessError("SHARE_TARGET_INVALID", message_for("SHARE_TARGET_INVALID"), status=422)
