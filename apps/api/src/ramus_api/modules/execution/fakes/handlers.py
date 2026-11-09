"""Recording RunPurposeHandler for executor tests. Hooks let a test write or fail inside a call."""

import threading
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from ramus_api.modules.execution.domain.models import (
    ConversationContext,
    LlmMessage,
    LlmRequest,
    RunError,
    RunPurpose,
    RunView,
)

Hook = Callable[..., None]


class FakeRunPurposeHandler:
    """Builds a one-message request with the run's own credential unless ``credential_override`` is set.

    ``build_hook``, ``complete_hook`` and ``fail_hook`` run first with the call's arguments; if a hook
    raises, the call raises and nothing is recorded for it.
    """

    def __init__(
        self,
        purpose: RunPurpose = RunPurpose.WORK,
        *,
        credential_override: UUID | None = None,
        is_child: bool = False,
        build_hook: Hook | None = None,
        complete_hook: Hook | None = None,
        fail_hook: Hook | None = None,
    ) -> None:
        self.purpose = RunPurpose(purpose).value
        self._credential_override = credential_override
        self._is_child = is_child
        self._build_hook = build_hook
        self._complete_hook = complete_hook
        self._fail_hook = fail_hook
        self._lock = threading.Lock()
        self._built: tuple[tuple[RunView, ConversationContext], ...] = ()
        self._completed: tuple[tuple[RunView, Mapping[str, Any]], ...] = ()
        self._failed: tuple[tuple[RunView, RunError], ...] = ()

    @property
    def built(self) -> tuple[tuple[RunView, ConversationContext], ...]:
        return self._built

    @property
    def completed(self) -> tuple[tuple[RunView, Mapping[str, Any]], ...]:
        return self._completed

    @property
    def failed(self) -> tuple[tuple[RunView, RunError], ...]:
        return self._failed

    def build_request(self, session: object, run: RunView, context: ConversationContext) -> LlmRequest:
        if self._build_hook is not None:
            self._build_hook(session, run, context)
        with self._lock:
            self._built = (*self._built, (run, context))
        credential = self._credential_override or run.credential_account_id
        message = LlmMessage("user", "테스트 요청입니다.")
        return LlmRequest(run.purpose, (message,), credential, context, self._is_child)

    def complete(self, session: object, run: RunView, output: Mapping[str, Any]) -> None:
        if self._complete_hook is not None:
            self._complete_hook(session, run, output)
        with self._lock:
            self._completed = (*self._completed, (run, output))

    def fail(self, session: object, run: RunView, error: RunError) -> None:
        if self._fail_hook is not None:
            self._fail_hook(session, run, error)
        with self._lock:
            self._failed = (*self._failed, (run, error))
