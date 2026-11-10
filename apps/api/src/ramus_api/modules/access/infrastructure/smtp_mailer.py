"""Verified-TLS SMTP delivery; provider exceptions and message contents stay private."""

import asyncio
import re
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from typing import Literal

from pydantic import EmailStr, SecretStr, TypeAdapter

from ramus_api.modules.access.domain.codes import CODE_LENGTH, CODE_TTL
from ramus_api.shared.application.notifications import MailDeliveryFailed

_EMAIL = TypeAdapter(EmailStr)


class SmtpMailer:
    def __init__(
        self, *, host: str, port: int, security: Literal["starttls", "tls"], sender: str,
        username: str | None = None, password: SecretStr | None = None, timeout: float = 10.0,
        smtp_factory: Callable | None = None, smtp_ssl_factory: Callable | None = None,
    ) -> None:
        if security not in {"starttls", "tls"}:
            raise ValueError("Unsupported SMTP security mode.")
        self._host, self._port, self._security = host, port, security
        self._sender, self._username, self._password = sender, username, password
        self._timeout = timeout
        self._smtp_factory = smtp_factory or smtplib.SMTP
        self._smtp_ssl_factory = smtp_ssl_factory or smtplib.SMTP_SSL

    async def send_code(self, email: str, code: str) -> None:
        try:
            # Mailer is a public boundary even when used without the HTTP request schema.
            recipient = _EMAIL.validate_python(email)
            sender = _EMAIL.validate_python(self._sender)
            if not re.fullmatch(rf"[0-9]{{{CODE_LENGTH}}}", code):
                raise ValueError
            message = EmailMessage()
            message["From"], message["To"] = sender, recipient
            message["Subject"] = "Ramus 로그인 인증 코드"
            minutes = int(CODE_TTL.total_seconds() // 60)
            message.set_content(f"Ramus 로그인 인증 코드: {code}\n\n{minutes}분 안에 입력해 주세요.\n요청하지 않은 경우 이 메일을 무시해 주세요.\n")
            await asyncio.to_thread(self._send, message, sender, recipient)
        except Exception:
            # CancelledError is a BaseException and propagates to the caller. A running SMTP
            # thread may still finish; each socket operation remains bounded by the timeout.
            raise MailDeliveryFailed() from None

    def _send(self, message: EmailMessage, sender: str, recipient: str) -> None:
        context = ssl.create_default_context()
        if self._security == "tls":
            client = self._smtp_ssl_factory(self._host, self._port, timeout=self._timeout, context=context)
        else:
            client = self._smtp_factory(self._host, self._port, timeout=self._timeout)
        try:
            if client.ehlo()[0] != 250:
                raise MailDeliveryFailed()
            if self._security == "starttls":
                client.starttls(context=context)
                if client.ehlo()[0] != 250:
                    raise MailDeliveryFailed()
            if self._username is not None and self._password is not None:
                client.login(self._username, self._password.get_secret_value())
            refused = client.send_message(message, from_addr=sender, to_addrs=[recipient])
            if refused:
                raise MailDeliveryFailed()
        finally:
            # DATA acceptance is the delivery outcome. QUIT or socket cleanup failures must
            # neither invalidate an accepted code nor replace an earlier transport failure.
            try:
                client.quit()
            except Exception:
                pass
            finally:
                try:
                    client.close()
                except Exception:
                    pass
