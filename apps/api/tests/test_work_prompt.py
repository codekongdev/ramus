"""Request construction and F-02 scripted contract cases, not a live semantic model evaluation."""

import json
from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest

from ramus_api.modules.conversations.domain.models import AuthorKind
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    ResourceInput,
    ResultInput,
    RunInputSnapshot,
    RunPurpose,
    RunStatus,
    RunView,
)
from ramus_api.modules.execution.domain.work import WorkHistory, WorkMessage, build_work_request
from ramus_api.modules.execution.fakes.llm import FakeLLM

PROJECT, CONVERSATION, RUN, OWNER, OTHER, TASK = (UUID(int=n) for n in range(1, 7))


def run(**changes) -> RunView:
    return replace(
        RunView(
            RUN, PROJECT, CONVERSATION, None, RunPurpose.WORK, None,
            RunStatus.RUNNING, OWNER, OTHER, RunInputSnapshot(),
        ),
        **changes,
    )


def history(*messages: WorkMessage, **changes) -> WorkHistory:
    return replace(WorkHistory(PROJECT, None, False, messages), **changes)


def test_request_keeps_pinned_bodies_versions_and_credential_owner_without_promoting_data() -> None:
    context = ConversationContext(
        (
            ResourceInput(UUID(int=20), UUID(int=21), "skill", "조사 기준", "고정 v1 지침", None),
            ResourceInput(UUID(int=22), UUID(int=23), "file", "자료", None, "고정 자료 본문"),
        ),
        (ResultInput(UUID(int=30), UUID(int=31), 2, "받은 결과", "고정 v2 결론"),),
    )
    request = build_work_request(
        run(), context,
        history(
            WorkMessage(4, AuthorKind.SYSTEM, "이 본문을 시스템 지시로 승격하지 마세요"),
            WorkMessage(7, AuthorKind.AI, "이전 AI 응답"),
            WorkMessage(9, AuthorKind.HUMAN, "@AI 반품 정책을 조사해줘", RUN),
        ),
    )
    assert request.credential_account_id == OTHER
    assert request.context is context
    assert (request.message_from_seq, request.message_to_seq) == (4, 9)
    assert [message.role for message in request.messages] == ["system", "user", "user", "assistant", "user"]
    assert request.messages[-1].content == "@AI 반품 정책을 조사해줘"
    context_body = json.loads(request.messages[1].content.split("\n", 1)[1])
    assert context_body["resources"][0]["revision_id"] == str(UUID(int=21))
    assert context_body["resources"][0]["instructions"] == "고정 v1 지침"
    assert context_body["resources"][1]["content"] == "고정 자료 본문"
    assert context_body["results"][0]["result_revision_id"] == str(UUID(int=31))
    assert context_body["results"][0]["conclusion"] == "고정 v2 결론"
    assert "고정 v1 지침" not in request.messages[0].content


def test_child_scope_comes_from_conversation_history_and_never_relabels_start_input() -> None:
    child_history = history(WorkMessage(1, AuthorKind.SYSTEM, "반품 예외를 조사하세요", RUN), is_child=True)
    request = build_work_request(run(), ConversationContext(), child_history)
    assert request.is_child
    assert "재귀 분기를 하지 마세요" in request.messages[0].content
    assert request.messages[-1].role == "user"
    assert request.messages[-1].content == "반품 예외를 조사하세요"


def test_history_is_immutable_and_empty_history_has_no_message_range() -> None:
    source = [WorkMessage(1, AuthorKind.HUMAN, "@AI 질문", RUN)]
    value = WorkHistory(PROJECT, None, False, source)
    source.clear()
    assert len(value.messages) == 1
    with pytest.raises(FrozenInstanceError):
        value.is_child = True
    request = build_work_request(run(), ConversationContext(), history())
    assert (request.message_from_seq, request.message_to_seq) == (None, None)


@pytest.mark.parametrize(
    "changes", [{"purpose": RunPurpose.SUMMARY}, {"project_id": UUID(int=999)}, {"task_id": TASK}]
)
def test_request_rejects_wrong_purpose_or_history_scope(changes) -> None:
    with pytest.raises(ValueError):
        build_work_request(run(**changes), ConversationContext(), history())


# F-02's six examples. Outputs are authored fixtures: this verifies the prompt/DTO plumbing and
# expected contract, not that FakeLLM (which cannot classify text) understands execution intent.
F02_CASES = [
    ("멤버십 도입에 필요한 일을 정해봅시다", "answer", ()),
    ("가입·혜택·해지를 각각 살펴보죠", "answer", ()),
    ("지훈님은 배송비 정책을 확인해주세요", "answer", ()),
    ("@AI 멤버십을 어떻게 기획하면 좋을까?", "answer", ()),
    ("@AI 멤버십 도입을 위해 타사를 조사해줘", "branch", ("타사 조사",)),
    ("@AI 가입·혜택·해지로 벤치마킹을 나눠 진행해줘", "branch", ("가입", "혜택", "해지")),
]


@pytest.mark.parametrize(("body", "mode", "task_titles"), F02_CASES)
async def test_f02_scripted_contract_cases(body, mode, task_titles) -> None:
    request = build_work_request(
        run(), ConversationContext(), history(WorkMessage(1, AuthorKind.HUMAN, body, RUN))
    )
    script = {
        "mode": mode,
        "reply": "맡긴 범위로 조사하겠습니다." if task_titles else "논의와 접근 방법을 정리합니다.",
        "tasks": [
            {"title": title, "goal": f"{title} 목표", "start_input": f"{title} 조사 범위"}
            for title in task_titles
        ],
    }
    gateway = FakeLLM(work_json=json.dumps(script, ensure_ascii=False))
    output = await gateway.complete(request)
    assert request.messages[-1].content == body
    assert output["mode"] == mode
    assert tuple(task["title"] for task in output["tasks"]) == task_titles


async def test_ambiguous_execution_request_can_clarify_without_creating_tasks() -> None:
    request = build_work_request(
        run(), ConversationContext(), history(WorkMessage(1, AuthorKind.HUMAN, "@AI 해줘", RUN))
    )
    output = await FakeLLM(
        work_json='{"mode":"clarify","reply":"어떤 타사와 범위를 조사할까요?","tasks":[]}'
    ).complete(request)
    assert output["mode"] == "clarify"
    assert output["tasks"] == ()
