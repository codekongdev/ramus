"""Notification delivery port shared by the composition root and access module."""

from typing import Protocol


class MailDeliveryFailed(Exception):
    """A transport failed without retaining its recipient, code, or provider exception."""

    def __init__(self) -> None:
        super().__init__("Mail delivery unavailable")


class Mailer(Protocol):
    async def send_code(self, email: str, code: str) -> None: ...
