"""The use case owns the atomic boundary for preparation and operator resets."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from ramus_api.modules.seed.domain.content import sample_id

T = TypeVar("T")
CONTENT_VERSION = 1


class SampleStore(Protocol[T]):
    def lock(self, transaction: T, *, resetting: bool) -> None: ...
    def ensure_base(self, transaction: T) -> UUID: ...
    def content_version(self, transaction: T) -> int | None: ...
    def install(self, transaction: T) -> None: ...
    def mark_content(self, transaction: T, version: int) -> None: ...
    def grant_participants(self, transaction: T) -> None: ...
    def require_idle(self, transaction: T) -> None: ...
    def clear(self, transaction: T) -> None: ...


@dataclass(frozen=True)
class PrepareSample(Generic[T]):
    transaction: Callable[[], AbstractContextManager[T]]
    store: SampleStore[T]

    def __call__(self, *, reset_project_id: UUID | None = None, work_preserved: bool = False) -> UUID:
        resetting = reset_project_id is not None
        if resetting and (reset_project_id != sample_id("project") or not work_preserved):
            raise ValueError("Reset requires the exact shared project ID and --work-preserved")
        with self.transaction() as transaction:
            self.store.lock(transaction, resetting=resetting)
            project_id = self.store.ensure_base(transaction)
            version = self.store.content_version(transaction)
            if version is not None and version != CONTENT_VERSION:
                raise RuntimeError("The sample content version requires an explicit migration")
            if resetting:
                self.store.require_idle(transaction)
                self.store.clear(transaction)
            if version is None or resetting:
                self.store.install(transaction)
                self.store.mark_content(transaction, CONTENT_VERSION)
            self.store.grant_participants(transaction)
            return project_id
