"""Access-owned membership preparation; sample setup never rewrites accounts or credentials."""

from uuid import UUID

from sqlalchemy import Uuid, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ramus_api.modules.access.infrastructure.models import AccountRow, MembershipRow


def ensure_example_author(session: Session, account_id: UUID, key: str, label: str) -> None:
    """Create an explicitly fictional author, refusing identities owned by existing accounts."""
    email = f"{key}@sample.ramus.invalid"
    session.execute(
        insert(AccountRow)
        .values(id=account_id, email=email, display_name=label)
        .on_conflict_do_nothing()
    )
    row = session.get(AccountRow, account_id)
    if row is None or row.email != email or row.display_name != label:
        raise RuntimeError("The example author identity is already used by another account")


def grant_sample_followup_memberships(
    session: Session, shared_project_id: UUID, followup_project_id: UUID
) -> None:
    """Join existing shared participants once, inside the caller's preparation transaction."""
    session.execute(
        insert(MembershipRow)
        .from_select(
            ["account_id", "project_id", "role"],
            select(
                MembershipRow.account_id,
                literal(followup_project_id, type_=Uuid),
                literal("editor"),
            ).where(MembershipRow.project_id == shared_project_id),
        )
        .on_conflict_do_nothing(index_elements=[MembershipRow.account_id, MembershipRow.project_id])
    )
