"""Imports every module's ORM models so ``metadata`` is complete for Alembic.

Add one import line here when a module gains ORM models.
"""

from ramus_api.modules.access.infrastructure.models import (
    AccountRow,
    AIConnectionRow,
    AuthAttemptRow,
    EmailCodeDeliveryRow,
    EmailCodeRow,
    MembershipRow,
    SessionRow,
)
from ramus_api.modules.conversations.infrastructure.models import ConversationRow, MessageRow
from ramus_api.modules.execution.infrastructure.models import RunRow, TaskRow
from ramus_api.modules.projects.infrastructure.models import ProjectRow
from ramus_api.modules.resources.infrastructure.models import (
    ConversationResourceRow,
    ResourceRevisionRow,
    ResourceRow,
)
from ramus_api.modules.results.infrastructure.models import ResultDraftRow, ResultRevisionRow, ResultRow
from ramus_api.modules.seed.infrastructure.models import SeedMarkerRow
from ramus_api.modules.sharing.infrastructure.models import ConversationInputRow, ShareRow
from ramus_api.shared.infrastructure.database import Base
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

metadata = Base.metadata

__all__ = [
    "AccountRow",
    "AuthAttemptRow",
    "MembershipRow",
    "EmailCodeRow",
    "EmailCodeDeliveryRow",
    "SessionRow",
    "AIConnectionRow",
    "ProjectRow",
    "ConversationRow",
    "MessageRow",
    "RunRow",
    "TaskRow",
    "ResourceRow",
    "ResourceRevisionRow",
    "ConversationResourceRow",
    "ResultRow",
    "ResultDraftRow",
    "ResultRevisionRow",
    "ShareRow",
    "ConversationInputRow",
    "SeedMarkerRow",
    "RequestReceiptRow",
    "metadata",
]
