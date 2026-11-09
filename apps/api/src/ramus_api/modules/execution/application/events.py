"""``run.updated`` events, published only after the transaction that changed the run commits."""

from datetime import datetime
from typing import Any

from ramus_api.modules.execution.application.branch_ports import TaskLifecycle
from ramus_api.modules.execution.application.config import Clock
from ramus_api.modules.execution.application.relay import EventRelay, LoopSignal
from ramus_api.modules.execution.application.runtime_ports import TransactionHooks
from ramus_api.modules.execution.domain.state import RunState
from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent


def run_updated_event(state: RunState, occurred_at: datetime) -> ProjectEvent:
    """Contract section 4 fields only; project routing goes in ``ProjectEvent.project_id``."""
    return ProjectEvent(
        project_id=state.project_id,
        name=EventName.RUN_UPDATED,
        occurred_at=occurred_at,
        data={
            "conversation_id": state.conversation_id,
            "run": {
                "id": state.id,
                "purpose": state.purpose.value,
                "status": state.status.value,
                "task_id": state.task_id,
                "requested_by": state.requested_by,
            },
        },
    )


class RunAnnouncer:
    """Schedules post-commit side effects of a run change on the given transaction."""

    def __init__(
        self,
        hooks: TransactionHooks[Any],
        relay: EventRelay,
        clock: Clock,
        wakeup: LoopSignal | None = None,
        task_lifecycle: TaskLifecycle[Any] | None = None,
    ) -> None:
        self._hooks = hooks
        self._relay = relay
        self._clock = clock
        self._wakeup = wakeup
        self._tasks = task_lifecycle

    def changed(self, session: Any, state: RunState) -> None:
        event = run_updated_event(state, self._clock())
        self._hooks.after_commit(session, lambda: self._relay.enqueue(event))
        if self._tasks is not None:
            task_event = self._tasks.project(session, state, self._clock())
            if task_event is not None:
                self._hooks.after_commit(session, lambda: self._relay.enqueue(task_event))

    def queued(self, session: Any) -> None:
        """Lets an idle worker claim a new pending run without waiting for the next poll."""
        if self._wakeup is not None:
            self._hooks.after_commit(session, self._wakeup.notify)
