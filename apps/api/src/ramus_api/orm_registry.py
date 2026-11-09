"""Imports every module's ORM models so ``metadata`` is complete for Alembic.

Add one import line here when a module gains ORM models.
"""

from ramus_api.shared.infrastructure.database import Base
from ramus_api.shared.infrastructure.receipts import RequestReceiptRow

metadata = Base.metadata

__all__ = ["RequestReceiptRow", "metadata"]
