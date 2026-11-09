"""Pure executor rules: transitions, failure mapping, snapshot serialization, messages, events."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from ramus_api.modules.execution.application import errors as execution_errors
from ramus_api.modules.execution.application.config import ExecutorConfig
from ramus_api.modules.execution.application.events import run_updated_event
from ramus_api.modules.execution.domain import errors as codes
from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmFailure,
    LlmMessage,
    LlmRequest,
    ResourceInput,
    ResultInput,
    RunInputSnapshot,
    RunPurpose,
    RunRequest,
    RunStatus,
)
from ramus_api.modules.execution.domain.snapshot import (
    EMPTY_SNAPSHOT,
    snapshot_from_context,
    snapshot_from_json,
    snapshot_to_json,
)
from ramus_api.modules.execution.domain.state import (
    RunFailure,
    RunState,
    cancel_denial,
    credential_failure,
    failure_from_exception,
    retry_denial,
)
from ramus_api.modules.execution.fakes.runs import FakeRunRequester
from ramus_api.modules.realtime.application.schemas import validate_event
from ramus_api.modules.realtime.domain.events import EventName
from ramus_api.shared.domain.errors import BusinessError
from ramus_api.shared.presentation.error_messages import message_for

PROJECT, CONVERSATION, TASK, OWNER, OTHER, RUN, TARGET = (UUID(int=n) for n in range(1, 8))
NOW = datetime(2026, 11, 9, 4, 0, tzinfo=UTC)


def run_state(**changes) -> RunState:
    base = RunState(
        id=RUN,
        project_id=PROJECT,
        conversation_id=CONVERSATION,
        task_id=None,
        purpose=RunPurpose.WORK,
        target_id=None,
        status=RunStatus.PENDING,
        requested_by=OWNER,
        credential_account_id=OWNER,
        input_snapshot=EMPTY_SNAPSHOT,
        attempt=1,
        error_code=None,
        error_params=None,
        heartbeat_at=None,
        started_at=None,
        finished_at=None,
        created_at=NOW,
    )
    return replace(base, **changes)


# --- snapshot -------------------------------------------------------------------------------------


def test_snapshot_from_context_keeps_revision_ids_in_context_order_without_bodies() -> None:
    resources = (
        ResourceInput(UUID(int=20), UUID(int=21), "skill", "스킬", "지침 본문", None),
        ResourceInput(UUID(int=22), UUID(int=23), "text", "자료", None, "자료 본문"),
    )
    results = (ResultInput(UUID(int=30), UUID(int=31), 2, "결과", "결론 본문"),)
    snapshot = snapshot_from_context(ConversationContext(resources, results))
    assert snapshot == RunInputSnapshot(None, None, (UUID(int=21), UUID(int=23)), (UUID(int=31),))
    serialized = snapshot_to_json(snapshot)
    assert serialized == {
        "message_from_seq": None,
        "message_to_seq": None,
        "resource_revision_ids": [str(UUID(int=21)), str(UUID(int=23))],
        "input_result_revision_ids": [str(UUID(int=31))],
    }
    assert "본문" not in repr(serialized)


@pytest.mark.parametrize(
    "snapshot",
    [EMPTY_SNAPSHOT, RunInputSnapshot(1, 4, (UUID(int=5),), (UUID(int=6), UUID(int=7)))],
)
def test_snapshot_round_trips(snapshot: RunInputSnapshot) -> None:
    assert snapshot_from_json(snapshot_to_json(snapshot)) == snapshot


@pytest.mark.parametrize(
    "value",
    [
        {},
        [],
        {"message_from_seq": None, "message_to_seq": None, "resource_revision_ids": []},
        {
            "message_from_seq": None,
            "message_to_seq": None,
            "resource_revision_ids": "not-a-list",
            "input_result_revision_ids": [],
        },
        {
            "message_from_seq": None,
            "message_to_seq": None,
            "resource_revision_ids": ["not-a-uuid"],
            "input_result_revision_ids": [],
        },
        {
            "message_from_seq": "1",
            "message_to_seq": 2,
            "resource_revision_ids": [],
            "input_result_revision_ids": [],
        },
        {
            "message_from_seq": 3,
            "message_to_seq": 2,
            "resource_revision_ids": [],
            "input_result_revision_ids": [],
        },
        {
            "message_from_seq": True,
            "message_to_seq": 2,
            "resource_revision_ids": [],
            "input_result_revision_ids": [],
        },
    ],
)
def test_snapshot_from_json_rejects_malformed_values(value) -> None:
    with pytest.raises(ValueError):
        snapshot_from_json(value)


# --- transitions -----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.RUNNING])
def test_requester_can_cancel_active_runs(status: RunStatus) -> None:
    assert cancel_denial(run_state(status=status), OWNER) is None


@pytest.mark.parametrize("status", [RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED])
def test_finished_runs_are_not_cancellable(status: RunStatus) -> None:
    assert cancel_denial(run_state(status=status), OWNER) == codes.RUN_NOT_CANCELLABLE


@pytest.mark.parametrize("status", list(RunStatus))
def test_only_the_requester_may_cancel_or_retry(status: RunStatus) -> None:
    assert cancel_denial(run_state(status=status), OTHER) == codes.FORBIDDEN
    assert retry_denial(run_state(status=status), OTHER) == codes.FORBIDDEN


@pytest.mark.parametrize("status", [RunStatus.FAILED, RunStatus.CANCELLED])
def test_requester_can_retry_failed_or_cancelled_runs(status: RunStatus) -> None:
    assert retry_denial(run_state(status=status), OWNER) is None


@pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.SUCCEEDED])
def test_other_states_are_not_retryable(status: RunStatus) -> None:
    assert retry_denial(run_state(status=status), OWNER) == codes.RUN_NOT_RETRYABLE


def test_run_state_view_exposes_only_the_contract_fields() -> None:
    state = run_state(task_id=TASK, status=RunStatus.RUNNING, attempt=3)
    view = state.view
    assert (view.id, view.task_id, view.status, view.credential_account_id) == (
        RUN,
        TASK,
        RunStatus.RUNNING,
        OWNER,
    )
    assert not hasattr(view, "attempt")


def test_run_state_normalizes_enum_values() -> None:
    state = run_state(purpose="summary", target_id=TARGET, status="running")
    assert state.purpose is RunPurpose.SUMMARY
    assert state.status is RunStatus.RUNNING


# --- failures --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (LlmFailure("LLM_OUTPUT_INVALID"), RunFailure(codes.LLM_OUTPUT_INVALID, retryable=True)),
        (LlmFailure("AI_KEY_INVALID", retryable=False), RunFailure("AI_KEY_INVALID", retryable=False)),
        (LlmFailure(), RunFailure(codes.LLM_UNAVAILABLE, retryable=True)),
        (TimeoutError(), RunFailure(codes.LLM_TIMEOUT, retryable=True)),
        (RuntimeError("provider said sk-secret"), RunFailure(codes.LLM_UNAVAILABLE, retryable=True)),
        (ValueError("raw model output"), RunFailure(codes.LLM_UNAVAILABLE, retryable=True)),
    ],
)
def test_failure_mapping_keeps_only_codes(error: BaseException, expected: RunFailure) -> None:
    failure = failure_from_exception(error)
    assert failure == expected
    assert "secret" not in repr(failure)
    assert "raw model output" not in repr(failure)


def test_credential_must_belong_to_the_requester() -> None:
    view = run_state().view
    good = LlmRequest(RunPurpose.WORK, (LlmMessage("user", "질문"),), OWNER)
    assert credential_failure(view, good) is None
    bad = replace(good, credential_account_id=OTHER)
    assert credential_failure(view, bad) == RunFailure(codes.RUN_CREDENTIAL_MISMATCH, retryable=False)


# --- error messages --------------------------------------------------------------------------------

EXECUTION_CODES = [
    codes.AI_CONNECTION_REQUIRED,
    codes.ACTIVE_RUN_EXISTS,
    codes.RUN_NOT_CANCELLABLE,
    codes.RUN_NOT_RETRYABLE,
    codes.LLM_UNAVAILABLE,
    codes.LLM_OUTPUT_INVALID,
    codes.LLM_TIMEOUT,
    codes.SUMMARY_LIMIT_EXCEEDED,
    codes.RUN_INTERRUPTED,
    codes.RUN_TIMED_OUT,
    codes.RUN_CREDENTIAL_MISMATCH,
]


@pytest.mark.parametrize("code", EXECUTION_CODES)
def test_every_execution_code_has_a_registered_korean_message(code: str) -> None:
    message = message_for(code)
    assert message and any("가" <= char <= "힣" for char in message)


def test_messages_match_the_existing_fakes_and_gateway_failure() -> None:
    fake = FakeRunRequester()
    with pytest.raises(BusinessError) as caught:
        fake.request(None, _work_request())
    assert caught.value.message == message_for(codes.AI_CONNECTION_REQUIRED)
    assert message_for(codes.ACTIVE_RUN_EXISTS) == "이미 진행 중인 AI 실행이 있습니다."
    assert message_for(codes.LLM_UNAVAILABLE) == str(LlmFailure())


def _work_request() -> RunRequest:
    return RunRequest(PROJECT, CONVERSATION, None, RunPurpose.WORK, None, OWNER)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (codes.AI_CONNECTION_REQUIRED, 409),
        (codes.ACTIVE_RUN_EXISTS, 409),
        (codes.RUN_NOT_CANCELLABLE, 409),
        (codes.RUN_NOT_RETRYABLE, 409),
        (codes.FORBIDDEN, 403),
        (codes.NOT_FOUND, 404),
    ],
)
def test_business_errors_use_the_message_table(code: str, status: int) -> None:
    error = execution_errors.business_error(code)
    assert (error.code, error.status) == (code, status)
    assert error.message


def test_unknown_gateway_codes_are_normalized_before_storage() -> None:
    unknown = RunFailure("PROVIDER_SPECIFIC_CODE", retryable=False)
    assert execution_errors.normalize_failure(unknown) == RunFailure(codes.LLM_UNAVAILABLE, retryable=False)
    known = RunFailure(codes.LLM_OUTPUT_INVALID)
    assert execution_errors.normalize_failure(known) is known
    error = execution_errors.run_error(known)
    assert (error.code, error.message, error.retryable) == (
        codes.LLM_OUTPUT_INVALID,
        message_for(codes.LLM_OUTPUT_INVALID),
        True,
    )


# --- events ----------------------------------------------------------------------------------------


def test_run_updated_event_carries_only_contract_fields_and_validates() -> None:
    state = run_state(task_id=TASK, status=RunStatus.RUNNING, error_code="LLM_TIMEOUT")
    event = run_updated_event(state, NOW)
    assert event.project_id == PROJECT
    assert event.name == EventName.RUN_UPDATED
    assert set(event.data) == {"conversation_id", "run"}
    assert set(event.data["run"]) == {"id", "purpose", "status", "task_id", "requested_by"}
    assert event.data["run"]["status"] == "running"
    valid = validate_event(event)
    assert valid.data["run"]["id"] == RUN


# --- config ----------------------------------------------------------------------------------------


def test_config_defaults_are_positive_and_validated() -> None:
    config = ExecutorConfig()
    assert config.heartbeat_interval < config.stale_after
    with pytest.raises(ValueError):
        ExecutorConfig(heartbeat_interval=timedelta(seconds=30), stale_after=timedelta(seconds=10))
    with pytest.raises(ValueError):
        ExecutorConfig(poll_interval=timedelta(0))
    with pytest.raises(ValueError):
        ExecutorConfig(concurrency=0)
