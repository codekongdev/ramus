"""Monotonic pin decisions are independent of SQL and HTTP."""

import pytest

from ramus_api.modules.sharing.domain.records import ShareOutcome, share_outcome


@pytest.mark.parametrize("current,sent,expected", [
    (None, 1, ShareOutcome.LINKED), (1, 2, ShareOutcome.REPLACED),
    (2, 2, ShareOutcome.UNCHANGED), (3, 1, ShareOutcome.KEPT_NEWER),
])
def test_share_outcome(current, sent, expected):
    assert share_outcome(current, sent) == expected
