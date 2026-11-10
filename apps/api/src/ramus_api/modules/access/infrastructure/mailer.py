"""Development mailer: writes the login code to the API server log instead of sending mail.

Real delivery is decided in roadmap D3. uvicorn's default log config only configures its own
loggers, so INFO records from application loggers would be dropped by the unconfigured root logger.
This logger therefore gets its own stderr handler and INFO level, once per process.
"""

import logging

from ramus_api.modules.access.domain.codes import CODE_TTL

DEV_MAIL_LOGGER = "ramus_api.dev_mail"
_HANDLER_NAME = "ramus-dev-mail"
_LOG_FORMAT = "%(levelname)s:     %(message)s"  # Aligns with uvicorn's "INFO:     ..." lines.


def _dev_mail_logger() -> logging.Logger:
    logger = logging.getLogger(DEV_MAIL_LOGGER)
    if not any(handler.get_name() == _HANDLER_NAME for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    return logger


class LoggingMailer:
    """``Mailer`` for local development. Never use it where the log is visible to others."""

    def __init__(self) -> None:
        self._logger = _dev_mail_logger()

    async def send_code(self, email: str, code: str) -> None:
        minutes = int(CODE_TTL.total_seconds() // 60)
        self._logger.info(
            "[DEV MAIL - not sent] Ramus login code for %s: %s (valid for %d minutes)", email, code, minutes
        )


class DisabledMailer:
    """Password authentication needs no external mail provider."""

    async def send_code(self, email: str, code: str) -> None:
        from ramus_api.modules.access.application.errors import AUTH_METHOD_DISABLED, AccessRejected

        raise AccessRejected(AUTH_METHOD_DISABLED)
