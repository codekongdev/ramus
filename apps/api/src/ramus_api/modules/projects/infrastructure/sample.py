"""Project-owned persistence entry point for shared sample preparation."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.projects.infrastructure.models import ProjectRow

SHARED_SAMPLE_SEED_KEY = "ramus:shared-sample:membership:project"
SHARED_SAMPLE_PROJECT_ID = uuid5(NAMESPACE_URL, SHARED_SAMPLE_SEED_KEY)
SHARED_SAMPLE_PROJECT_NAME = "쇼핑몰 멤버십 도입 · 공동 체험"
FOLLOWUP_SAMPLE_SEED_KEY = "ramus:shared-sample:membership:followup-project"
FOLLOWUP_SAMPLE_PROJECT_ID = uuid5(NAMESPACE_URL, FOLLOWUP_SAMPLE_SEED_KEY)
FOLLOWUP_SAMPLE_PROJECT_NAME = "멤버십 상세 기획 · 후속 체험"
_SAMPLE_PREPARATION_LOCK_KEY = "ramus:shared-sample:membership:content"


def lock_sample_preparation(session: Session, *, exclusive: bool = False) -> None:
    """Keep login membership commits and explicit sample installation in a consistent order."""
    query = (
        "SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"
        if exclusive else "SELECT pg_advisory_xact_lock_shared(hashtextextended(:key, 0))"
    )
    session.execute(text(query), {"key": _SAMPLE_PREPARATION_LOCK_KEY})


def ensure_shared_sample_project(session: Session) -> UUID:
    """Insert once, preserving existing names and all user data on subsequent calls."""
    lock_sample_preparation(session)
    # Both the primary key and seed_key are unique. Handle either index during racing inserts.
    session.execute(
        insert(ProjectRow)
        .values(
            id=SHARED_SAMPLE_PROJECT_ID,
            name=SHARED_SAMPLE_PROJECT_NAME,
            is_shared_sample=True,
            seed_key=SHARED_SAMPLE_SEED_KEY,
        )
        .on_conflict_do_nothing()
    )
    row = session.get(ProjectRow, SHARED_SAMPLE_PROJECT_ID)
    if row is None or row.seed_key != SHARED_SAMPLE_SEED_KEY or not row.is_shared_sample:
        raise RuntimeError("The shared sample identity is already used by another project")
    return row.id


def ensure_followup_sample_project(session: Session) -> UUID:
    """Explicit preparation only; login never creates the follow-up workspace."""
    session.execute(
        insert(ProjectRow)
        .values(
            id=FOLLOWUP_SAMPLE_PROJECT_ID,
            name=FOLLOWUP_SAMPLE_PROJECT_NAME,
            is_shared_sample=False,
            seed_key=FOLLOWUP_SAMPLE_SEED_KEY,
        )
        .on_conflict_do_nothing()
    )
    project_id = followup_sample_project_id(session)
    if project_id is None:
        raise RuntimeError("The follow-up sample identity is already used by another project")
    return project_id


def followup_sample_project_id(session: Session) -> UUID | None:
    """Returns the prepared follow-up project, preserving names changed by participants."""
    row = session.get(ProjectRow, FOLLOWUP_SAMPLE_PROJECT_ID)
    if row is None:
        return None
    if row.seed_key != FOLLOWUP_SAMPLE_SEED_KEY or row.is_shared_sample:
        raise RuntimeError("The follow-up sample identity is already used by another project")
    return row.id
