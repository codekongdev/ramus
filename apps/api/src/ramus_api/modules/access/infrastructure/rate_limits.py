"""Database-wide limits: advisory locks serialize counters across API workers."""

from datetime import datetime

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from ramus_api.modules.access.application.rate_limits import RATE_WINDOW
from ramus_api.modules.access.infrastructure.models import AuthAttemptRow
from ramus_api.shared.domain import new_id

RATE_LOCK_NAMESPACE = 0x52414D02


class SqlAttemptStore:
    def reserve(
        self, transaction: Session, scope: str, limits: list[tuple[str, int]], now: datetime
    ) -> datetime | None:
        cutoff = now - RATE_WINDOW
        # A stable ordering prevents deadlocks when two requests share one subject.
        for digest, _ in sorted(limits):
            transaction.execute(
                text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:subject))"),
                {"namespace": RATE_LOCK_NAMESPACE, "subject": f"{scope}:{digest}"},
            )
        for digest, limit in limits:
            timestamps = transaction.scalars(
                select(AuthAttemptRow.created_at)
                .where(
                    AuthAttemptRow.scope == scope,
                    AuthAttemptRow.subject_hash == digest,
                    AuthAttemptRow.created_at > cutoff,
                )
                .order_by(AuthAttemptRow.created_at)
            ).all()
            if len(timestamps) >= limit:
                return timestamps[len(timestamps) - limit] + RATE_WINDOW
        for digest, _ in limits:
            transaction.execute(
                delete(AuthAttemptRow).where(
                    AuthAttemptRow.scope == scope,
                    AuthAttemptRow.subject_hash == digest,
                    AuthAttemptRow.created_at <= cutoff,
                )
            )
            transaction.add(AuthAttemptRow(id=new_id(), scope=scope, subject_hash=digest, created_at=now))
        return None
