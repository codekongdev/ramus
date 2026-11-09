"""Resource rule errors become the contract's error envelope; records become response DTOs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ramus_api.modules.resources.application.ports import (
    AppliedRecord,
    ResourceHistory,
    ResourceRecord,
    RevisionEntry,
    RevisionRecord,
)
from ramus_api.modules.resources.application.use_cases import SearchHit
from ramus_api.modules.resources.domain.models import ResourceKind
from ramus_api.modules.resources.domain.rules import ResourceRuleError, RevisionContent
from ramus_api.modules.resources.presentation.mapping import (
    applied_list,
    resource_detail,
    summary_list,
    to_business_error,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)


@pytest.mark.parametrize(
    ("code", "status"), [("INVALID_INPUT", 422), ("FILE_TYPE_UNSUPPORTED", 422), ("NOT_FOUND", 404)]
)
def test_rule_errors_map_to_contract_status_and_korean_message(code: str, status: int) -> None:
    error = to_business_error(ResourceRuleError(code, {"field": "name"}))
    assert (error.code, error.status) == (code, status)
    assert any("가" <= ch <= "힣" for ch in error.message)


def test_not_found_hides_details() -> None:
    assert to_business_error(ResourceRuleError("NOT_FOUND", {"why": "not a member"})).details is None


def test_invalid_input_keeps_details() -> None:
    assert to_business_error(ResourceRuleError("INVALID_INPUT", {"field": "name"})).details == {
        "field": "name"
    }


def _record(number: int = 1) -> ResourceRecord:
    resource_id = uuid4()
    revision = RevisionRecord(
        uuid4(), resource_id, number, RevisionContent("스킬", "설명", "지침", None, None), uuid4(), NOW
    )
    return ResourceRecord(resource_id, uuid4(), ResourceKind.SKILL, revision)


def test_resource_detail_defaults_to_latest_revision() -> None:
    record = _record()
    entry = RevisionEntry(record.latest.id, 1, "스킬", record.latest.created_by, NOW)
    detail = resource_detail(ResourceHistory(record, (entry,)))
    assert detail.kind == "skill"
    assert detail.latest_revision_id == record.latest.id
    assert detail.revision.instructions == "지침"
    assert [r.number for r in detail.revisions] == [1]


def test_summary_and_applied_lists() -> None:
    record = _record(number=2)
    applied = AppliedRecord(record.id, uuid4(), 1, "스킬", ResourceKind.SKILL)
    summaries = summary_list((SearchHit(record, applied), SearchHit(_record(), None)))
    first, second = summaries.items
    assert (first.latest.number, first.applied.number) == (2, 1)
    assert second.applied is None
    assert applied_list((applied,)).items[0].kind == "skill"
