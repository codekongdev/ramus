"""Project-owned persistence entry point for shared sample preparation."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.projects.infrastructure.models import ProjectRow

SHARED_SAMPLE_SEED_KEY = "ramus:shared-sample:membership:project"
SHARED_SAMPLE_PROJECT_ID = uuid5(NAMESPACE_URL, SHARED_SAMPLE_SEED_KEY)
SHARED_SAMPLE_PROJECT_NAME = "쇼핑몰 멤버십 도입 · 공동 체험"


def ensure_shared_sample_project(session: Session) -> UUID:
    """Insert once, preserving existing names and all user data on subsequent calls."""
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
