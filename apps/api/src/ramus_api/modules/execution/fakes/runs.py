"""Run registration fake. No worker, persistence, or transaction rollback is simulated."""

from collections.abc import Iterable
from uuid import UUID, uuid5

from ramus_api.modules.execution.domain.models import RunPurpose, RunRef, RunRequest, RunStatus
from ramus_api.shared.domain.errors import BusinessError

RUN_NAMESPACE = UUID("62666521-cc1c-51ed-aee1-72947c22b2aa")
ACTIVE_STATUSES = frozenset({RunStatus.PENDING, RunStatus.RUNNING})


class FakeRunRequester:
    def __init__(self, connected_accounts: Iterable[UUID] = ()) -> None:
        self._connected_accounts = set(connected_accounts)
        self._requests: dict[UUID, RunRequest] = {}
        self._refs: dict[UUID, RunRef] = {}

    @property
    def requests(self) -> tuple[RunRequest, ...]:
        return tuple(self._requests.values())

    def set_connected(self, account_id: UUID, connected: bool) -> None:
        if connected:
            self._connected_accounts.add(account_id)
        else:
            self._connected_accounts.discard(account_id)

    @staticmethod
    def _target(request: RunRequest) -> tuple[RunPurpose, UUID]:
        target = request.target_id if request.purpose == RunPurpose.SUMMARY else request.conversation_id
        assert target is not None
        return request.purpose, target

    def request(self, session: object, request: RunRequest) -> RunRef:
        if request.requested_by not in self._connected_accounts:
            raise BusinessError("AI_CONNECTION_REQUIRED", "AI 연결을 먼저 설정해 주세요.", status=409)
        for run_id, previous in self._requests.items():
            if (
                self._target(previous) == self._target(request)
                and self._refs[run_id].status in ACTIVE_STATUSES
            ):
                raise BusinessError("ACTIVE_RUN_EXISTS", "이미 진행 중인 AI 실행이 있습니다.", status=409)
        identity = ":".join(
            str(value)
            for value in (
                request.project_id,
                request.conversation_id,
                request.task_id,
                request.purpose,
                request.target_id,
                request.requested_by,
                len(self._requests),
            )
        )
        ref = RunRef(uuid5(RUN_NAMESPACE, identity), RunStatus.PENDING)
        self._requests[ref.run_id] = request
        self._refs[ref.run_id] = ref
        return ref

    def set_status(self, run_id: UUID, status: RunStatus) -> RunRef:
        """Test setup for worker outcomes, not a production transition state machine."""
        ref = RunRef(run_id, RunStatus(status))
        if run_id not in self._refs:
            raise KeyError(run_id)
        self._refs[run_id] = ref
        return ref
