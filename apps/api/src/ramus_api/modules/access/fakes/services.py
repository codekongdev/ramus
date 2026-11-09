"""Development/test substitutes. These never send mail or verify provider credentials."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from ramus_api.shared.domain.errors import BusinessError


@dataclass(frozen=True)
class CodeDelivery:
    email: str
    code: str = field(repr=False)


class FakeMailer:
    def __init__(self) -> None:
        self._deliveries: list[CodeDelivery] = []

    @property
    def deliveries(self) -> tuple[CodeDelivery, ...]:
        return tuple(self._deliveries)

    async def send_code(self, email: str, code: str) -> None:
        self._deliveries.append(CodeDelivery(email, code))


class FakeCredentialProvider:
    def __init__(self, credentials: Mapping[UUID, str] | None = None) -> None:
        self._credentials = dict(credentials or {})

    def get_api_key(self, account_id: UUID) -> str:
        try:
            return self._credentials[account_id]
        except KeyError:
            raise BusinessError(
                "AI_CONNECTION_REQUIRED", "AI 연결을 먼저 설정해 주세요.", status=409
            ) from None
