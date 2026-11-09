"""The development mailer writes the login code to the server log instead of sending mail."""

import logging

import pytest

from ramus_api.modules.access.application.ports import Mailer
from ramus_api.modules.access.infrastructure.mailer import DEV_MAIL_LOGGER, LoggingMailer


async def test_logging_mailer_logs_the_email_and_code(caplog: pytest.LogCaptureFixture) -> None:
    mailer: Mailer = LoggingMailer()
    with caplog.at_level(logging.INFO, logger=DEV_MAIL_LOGGER):
        await mailer.send_code("tester@example.test", "123456")
    [record] = [r for r in caplog.records if r.name == DEV_MAIL_LOGGER]
    assert record.levelno == logging.INFO
    message = record.getMessage()
    assert "tester@example.test" in message
    assert "123456" in message
    assert "DEV" in message.upper()


def test_logging_mailer_logger_emits_info_without_root_configuration() -> None:
    # uvicorn's default log config leaves the root logger at WARNING with no handler.
    LoggingMailer()
    logger = logging.getLogger(DEV_MAIL_LOGGER)
    assert logger.getEffectiveLevel() <= logging.INFO
    assert logger.handlers


def test_creating_many_mailers_does_not_duplicate_handlers() -> None:
    LoggingMailer()
    count = len(logging.getLogger(DEV_MAIL_LOGGER).handlers)
    LoggingMailer()
    LoggingMailer()
    assert len(logging.getLogger(DEV_MAIL_LOGGER).handlers) == count
