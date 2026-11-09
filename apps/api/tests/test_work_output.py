"""A5 output guards reject duplicate work and text that PostgreSQL cannot store."""

import json
from dataclasses import replace
from uuid import UUID

import pytest

from ramus_api.modules.execution.application.output_schema import validate_output
from ramus_api.modules.execution.domain.models import LlmFailure, LlmMessage, LlmRequest, RunPurpose

WORK = LlmRequest(RunPurpose.WORK, (LlmMessage("user", "@AI 조사를 나눠 진행해줘"),), UUID(int=1))
TASK = {"title": "가입 조사", "goal": "Research signup", "start_input": "Compare signup policies"}


@pytest.mark.parametrize(
    "second",
    [
        TASK,
        {**TASK, "title": "다른 제목", "goal": "  research \n SIGNUP ", "start_input": "다른 입력"},
        {**TASK, "goal": "다른 목표", "start_input": "compare\t signup  POLICIES"},
    ],
)
def test_duplicate_goal_or_start_input_is_rejected_after_whitespace_and_case_normalization(second) -> None:
    raw = json.dumps({"mode": "branch", "reply": "조사를 진행합니다.", "tasks": [TASK, second]})
    with pytest.raises(LlmFailure) as caught:
        validate_output(WORK, raw)
    assert caught.value.code == "LLM_OUTPUT_INVALID"


def test_independent_tasks_can_share_a_title_without_sharing_goal_or_input() -> None:
    second = {**TASK, "goal": "Research cancellation", "start_input": "Compare cancellation policies"}
    output = validate_output(
        WORK, json.dumps({"mode": "branch", "reply": "조사를 진행합니다.", "tasks": [TASK, second]})
    )
    assert len(output["tasks"]) == 2


@pytest.mark.parametrize("bad_text", ["bad\x00text", "bad\ud800text", "bad\udffftext"])
@pytest.mark.parametrize("field", ["reply", "title", "goal", "start_input", "conclusion"])
def test_unsafe_text_is_rejected_at_each_model_output_boundary(bad_text, field) -> None:
    request = WORK
    if field == "conclusion":
        request = replace(WORK, purpose=RunPurpose.SUMMARY)
        value = {"conclusion": bad_text}
    else:
        task = {**TASK, **({field: bad_text} if field != "reply" else {})}
        value = {"mode": "branch", "reply": bad_text if field == "reply" else "진행합니다.", "tasks": [task]}
    with pytest.raises(LlmFailure) as caught:
        validate_output(request, json.dumps(value))
    assert caught.value.code == "LLM_OUTPUT_INVALID"
    assert bad_text not in str(caught.value)


def test_recursive_branch_is_rejected_by_child_output_schema() -> None:
    with pytest.raises(LlmFailure):
        validate_output(
            replace(WORK, is_child=True), json.dumps({"mode": "branch", "reply": "진행", "tasks": [TASK]})
        )
