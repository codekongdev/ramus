"""SMTP delivery tests replace both client factories; no sockets or real mail are used."""

import asyncio
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage

import pytest
from pydantic import SecretStr

from ramus_api.modules.access.infrastructure.smtp_mailer import SmtpMailer
from ramus_api.shared.application.notifications import MailDeliveryFailed


class SmtpClient:
    def __init__(self, *, failure=None, fail_on=None, refused=None):
        self.calls = []
        self.failure, self.fail_on, self.refused = failure, fail_on, refused or {}
        self.messages = []

    def record(self, operation, *arguments):
        self.calls.append((operation, *arguments))
        if operation == self.fail_on:
            raise self.failure

    def quit(self):
        self.record("quit")
        self.close()
        return 221, b"Bye"

    def close(self):
        self.record("close")

    def ehlo(self):
        self.record("ehlo")
        return 250, b"OK"

    def starttls(self, *, context):
        self.record("starttls", context)

    def login(self, username, password):
        self.record("login", username, password)

    def send_message(self, message, *, from_addr, to_addrs):
        self.record("send_message", from_addr, to_addrs)
        self.messages.append(message)
        return self.refused


def make_mailer(client, security="starttls", **overrides):
    constructor_calls = []

    def factory(*args, **kwargs):
        constructor_calls.append((args, kwargs, threading.get_ident()))
        return client

    def unexpected(*args, **kwargs):
        pytest.fail("The wrong SMTP security factory was selected")

    options = {
        "host": "smtp.example.com", "port": 587 if security == "starttls" else 465,
        "sender": "login@example.com", "security": security, "timeout": 7.5,
        "smtp_factory": factory if security == "starttls" else unexpected,
        "smtp_ssl_factory": factory if security == "tls" else unexpected,
    }
    options.update(overrides)
    return SmtpMailer(**options), constructor_calls


def test_direct_construction_rejects_unsecured_transport_without_exposing_the_value():
    with pytest.raises(ValueError) as caught:
        make_mailer(SmtpClient(), security="private-unsecured-mode")
    assert "private-unsecured-mode" not in str(caught.value)


async def test_starttls_is_verified_before_authentication_and_message_delivery():
    client = SmtpClient()
    mailer, constructors = make_mailer(client, username="smtp-account", password=SecretStr("synthetic-password"))
    caller_thread = threading.get_ident()
    await mailer.send_code("person@example.com", "031415")
    assert [call[0] for call in client.calls] == [
        "ehlo", "starttls", "ehlo", "login", "send_message", "quit", "close", "close",
    ]
    context = client.calls[1][1]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert constructors[0][0] == ("smtp.example.com", 587)
    assert constructors[0][1] == {"timeout": 7.5}
    assert constructors[0][2] != caller_thread
    assert client.calls[3] == ("login", "smtp-account", "synthetic-password")
    assert client.calls[4] == ("send_message", "login@example.com", ["person@example.com"])
    [message] = client.messages
    assert isinstance(message, EmailMessage)
    assert message["To"] == "person@example.com" and message["From"] == "login@example.com"
    assert "031415" in message.get_content() and "10분" in message.get_content()


async def test_implicit_tls_verifies_server_and_never_starts_plain_smtp():
    client = SmtpClient()
    mailer, constructors = make_mailer(client, security="tls")
    await mailer.send_code("person@example.com", "031415")
    assert [call[0] for call in client.calls] == ["ehlo", "send_message", "quit", "close", "close"]
    assert constructors[0][0] == ("smtp.example.com", 465)
    context = constructors[0][1]["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert constructors[0][1]["timeout"] == 7.5


@pytest.mark.parametrize("stage", ["ehlo", "starttls", "login", "send_message"])
async def test_provider_errors_are_safe_at_every_delivery_stage(stage, caplog):
    private = "person@example.com 031415 synthetic-password private-provider-response"
    client = SmtpClient(fail_on=stage, failure=smtplib.SMTPException(private))
    mailer, _ = make_mailer(client, username="smtp-account", password=SecretStr("synthetic-password"))
    with caplog.at_level(logging.DEBUG), pytest.raises(MailDeliveryFailed) as caught:
        await mailer.send_code("person@example.com", "031415")
    assert "person@example.com" not in str(caught.value)
    assert "031415" not in str(caught.value)
    assert "synthetic-password" not in str(caught.value)
    assert "private-provider-response" not in str(caught.value)
    assert caught.value.__suppress_context__
    assert not caplog.records
    assert any(call[0] == "quit" for call in client.calls)
    assert any(call[0] == "close" for call in client.calls)


@pytest.mark.parametrize("stage", ["quit", "close"])
async def test_cleanup_errors_after_acceptance_do_not_report_delivery_failure(stage, caplog):
    client = SmtpClient(fail_on=stage, failure=smtplib.SMTPException("private cleanup failure"))
    mailer, _ = make_mailer(client)
    with caplog.at_level(logging.DEBUG):
        await mailer.send_code("person@example.com", "031415")
    assert len(client.messages) == 1
    assert any(call[0] == "quit" for call in client.calls)
    assert client.calls[-1] == ("close",)
    assert not caplog.records


async def test_cleanup_failures_preserve_an_earlier_delivery_failure_and_attempt_close():
    class BrokenClient(SmtpClient):
        def quit(self):
            self.record("quit")
            raise smtplib.SMTPException("private quit error")

        def close(self):
            self.record("close")
            raise OSError("private close error")

    client = BrokenClient(fail_on="send_message", failure=smtplib.SMTPException("private send error"))
    mailer, _ = make_mailer(client)
    with pytest.raises(MailDeliveryFailed) as caught:
        await mailer.send_code("person@example.com", "031415")
    assert "private" not in str(caught.value)
    assert client.messages == []
    assert client.calls[-2:] == [("quit",), ("close",)]


async def test_refused_recipient_is_not_reported_as_success():
    client = SmtpClient(refused={"person@example.com": (550, b"rejected")})
    mailer, _ = make_mailer(client)
    with pytest.raises(MailDeliveryFailed):
        await mailer.send_code("person@example.com", "031415")


@pytest.mark.parametrize("failed_greeting", [1, 2])
async def test_failed_greeting_never_authenticates_or_delivers(failed_greeting):
    class RejectedGreeting(SmtpClient):
        def ehlo(self):
            super().ehlo()
            count = sum(call[0] == "ehlo" for call in self.calls)
            return (550, b"private response") if count == failed_greeting else (250, b"OK")

    client = RejectedGreeting()
    mailer, _ = make_mailer(client, username="smtp-account", password=SecretStr("synthetic-password"))
    with pytest.raises(MailDeliveryFailed):
        await mailer.send_code("person@example.com", "031415")
    assert not any(call[0] in {"login", "send_message"} for call in client.calls)


@pytest.mark.parametrize(("recipient", "code"), [
    ("person@example.com\r\nBcc: other@example.com", "031415"),
    ("not-an-address", "031415"),
    ("person@example.com", "031415\r\nBcc: other@example.com"),
    ("person@example.com", "12345"),
    ("person@example.com", "１２３４５６"),
])
async def test_invalid_delivery_input_never_opens_a_connection(recipient, code):
    client = SmtpClient()
    mailer, constructors = make_mailer(client)
    with pytest.raises(MailDeliveryFailed):
        await mailer.send_code(recipient, code)
    assert constructors == []
    assert client.messages == []


async def test_cancellation_propagates_while_the_bounded_smtp_thread_can_finish():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    class WaitingClient(SmtpClient):
        def send_message(self, message, *, from_addr, to_addrs):
            started.set()
            try:
                assert release.wait(2)
                return super().send_message(message, from_addr=from_addr, to_addrs=to_addrs)
            finally:
                finished.set()

    client = WaitingClient()
    mailer, _ = make_mailer(client)
    task = asyncio.create_task(mailer.send_code("person@example.com", "031415"))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not finished.is_set()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
