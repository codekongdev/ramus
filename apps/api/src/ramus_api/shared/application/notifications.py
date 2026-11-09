"""Notification delivery port shared by the composition root and access module."""

from typing import Protocol


class Mailer(Protocol):
    async def send_code(self, email: str, code: str) -> None: ...
