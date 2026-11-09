"""Project identity, independent of persistence and HTTP."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProjectInfo:
    id: UUID
    name: str
    is_shared_sample: bool
