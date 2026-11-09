"""Project identity, independent of persistence and HTTP."""

from dataclasses import dataclass
from uuid import UUID

MAX_PROJECT_NAME_LENGTH = 100


def validate_project_name(name: str) -> str:
    """Preserves the submitted name while rejecting blank or unpersistable text."""
    if not name.strip() or len(name) > MAX_PROJECT_NAME_LENGTH or "\x00" in name:
        raise ValueError("Project name must be nonblank and at most 100 characters")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Project name must be valid UTF-8") from None
    return name


@dataclass(frozen=True)
class ProjectInfo:
    id: UUID
    name: str
    is_shared_sample: bool
