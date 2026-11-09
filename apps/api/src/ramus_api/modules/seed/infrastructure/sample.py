"""Transactional sample preparation. This command does not seed feature content or reset data."""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from ramus_api.modules.projects.infrastructure.sample import ensure_shared_sample_project
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.shared.infrastructure.database import Database

SHARED_SAMPLE_MARKER_KEY = "ramus:shared-sample:membership:project"
SHARED_SAMPLE_VERSION = 1


def prepare_shared_sample(database: Database) -> UUID:
    with database.transaction() as session:
        project_id = ensure_shared_sample_project(session)
        session.execute(
            insert(SeedMarkerRow)
            .values(key=SHARED_SAMPLE_MARKER_KEY, version=SHARED_SAMPLE_VERSION)
            .on_conflict_do_nothing(index_elements=[SeedMarkerRow.key])
        )
        marker = session.get(SeedMarkerRow, SHARED_SAMPLE_MARKER_KEY)
        if marker is None or marker.version != SHARED_SAMPLE_VERSION:
            raise RuntimeError("The shared sample seed version requires an explicit migration")
        return project_id
