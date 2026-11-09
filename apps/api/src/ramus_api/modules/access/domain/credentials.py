"""Private credential values. None of these values are API responses or event payloads."""

from dataclasses import dataclass, field
from datetime import datetime

from ramus_api.modules.access.domain.models import AIConnectionStatus


@dataclass(frozen=True)
class StoredCredential:
    ciphertext: str = field(repr=False)
    status: AIConnectionStatus
    verified_at: datetime
