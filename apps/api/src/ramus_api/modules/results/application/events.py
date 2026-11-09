"""Small, body-free notifications emitted only after the surrounding transaction commits."""

from ramus_api.modules.realtime.domain.events import EventName, ProjectEvent
from ramus_api.modules.results.domain.records import ResultRecord
from ramus_api.shared.domain.primitives import utc_now


def result_event(result: ResultRecord) -> ProjectEvent:
    return ProjectEvent(
        result.project_id, EventName.RESULT_UPDATED, utc_now(),
        {"result_id": str(result.id), "task_id": str(result.source_task_id),
         "draft_status": result.draft.status if result.draft else None,
         "latest_version": result.latest_version or None},
    )
