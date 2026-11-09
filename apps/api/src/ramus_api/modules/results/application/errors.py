"""Result errors use the central code-to-message table, never stored sentences."""

from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.error_messages import message_for, register_error_messages
from ramus_api.shared.presentation.errors import INVALID_INPUT, INVALID_INPUT_MESSAGE, http_error_code

register_error_messages({
    "VERSION_CONFLICT": "다른 사람이 먼저 새 버전을 저장했습니다. 최신 내용을 확인한 뒤 다시 저장해 주세요.",
    "TASK_NOT_READY": "작업 응답이 완료된 뒤 결과를 정리할 수 있습니다.",
})


def rejected(code: str, *, details=None) -> BusinessError:
    if code == "NOT_FOUND":
        _, message = http_error_code(404)
        return BusinessError(code, message, status=404)
    if code == INVALID_INPUT:
        return BusinessError(INVALID_INPUT, INVALID_INPUT_MESSAGE, status=422)
    if code == "VERSION_CONFLICT":
        # Resources owns the same shared contract code and sentence.
        return BusinessError(code, message_for(code), status=409, details=details)
    return BusinessError(code, message_for(code), status=409, details=details)
