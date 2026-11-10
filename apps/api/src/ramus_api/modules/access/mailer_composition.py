"""Select explicit delivery at startup and keep development codes out of deployed logs."""

from ramus_api.modules.access.infrastructure.mailer import LoggingMailer
from ramus_api.modules.access.infrastructure.smtp_mailer import SmtpMailer
from ramus_api.settings import Settings
from ramus_api.shared.application.notifications import Mailer


class MailerConfigurationError(ValueError):
    """Safe, value-free startup error; never interpolate mail configuration or credentials."""


def build_mailer(settings: Settings, injected: Mailer | None = None) -> Mailer:
    deployed = settings.environment in {"staging", "production"}
    if injected is not None:
        if deployed and isinstance(injected, LoggingMailer):
            raise MailerConfigurationError("Logging mail delivery is unavailable in deployed environments.")
        return injected
    if settings.mailer_backend == "logging":
        if deployed:
            raise MailerConfigurationError("Deployed environments require SMTP mail delivery.")
        return LoggingMailer()
    if not settings.smtp_host or not settings.smtp_host.strip() or settings.smtp_from is None:
        raise MailerConfigurationError("SMTP mail delivery requires a host and sender address.")
    if any(char in settings.smtp_host for char in "\r\n\x00"):
        raise MailerConfigurationError("SMTP host is invalid.")
    password = settings.smtp_password.get_secret_value() if settings.smtp_password is not None else None
    if (settings.smtp_username is None) != (password is None) or password == "":
        raise MailerConfigurationError("SMTP credentials must include both username and password.")
    if deployed and settings.uses_ephemeral_auth_secret:
        raise MailerConfigurationError("Deployed SMTP delivery requires a stable authentication secret.")
    return SmtpMailer(
        host=settings.smtp_host.strip(), port=settings.smtp_port, security=settings.smtp_security,
        sender=str(settings.smtp_from), username=settings.smtp_username,
        password=settings.smtp_password, timeout=settings.smtp_timeout,
    )
