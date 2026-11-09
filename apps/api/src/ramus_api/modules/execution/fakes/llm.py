"""Deterministic scripted model; it never calls a provider or reads credentials."""

from collections.abc import Mapping
from typing import Any

from ramus_api.modules.execution.application.output_schema import validate_output
from ramus_api.modules.execution.domain.models import LlmFailure, LlmRequest, RunPurpose


class FakeLLM:
    """Configure JSON to exercise answer, clarify, branch, summary, or invalid output.

    Script selection depends only on request purpose/child scope. Repeated calls return equal
    immutable values. ``failure_code`` simulates provider failure without retaining its payload.
    """

    def __init__(
        self,
        *,
        work_json: str = '{"mode":"answer","reply":"테스트 응답입니다.","tasks":[]}',
        child_work_json: str = '{"mode":"answer","reply":"테스트 작업 응답입니다."}',
        summary_json: str = '{"conclusion":"테스트 결론입니다."}',
        failure_code: str | None = None,
    ) -> None:
        self._work_json = work_json
        self._child_work_json = child_work_json
        self._summary_json = summary_json
        self._failure_code = failure_code
        self._calls: list[LlmRequest] = []

    @property
    def calls(self) -> tuple[LlmRequest, ...]:
        return tuple(self._calls)

    async def complete(self, request: LlmRequest) -> Mapping[str, Any]:
        self._calls.append(request)
        if self._failure_code:
            raise LlmFailure(self._failure_code)
        if request.purpose == RunPurpose.SUMMARY:
            raw_json = self._summary_json
        else:
            raw_json = self._child_work_json if request.is_child else self._work_json
        return validate_output(request, raw_json)
