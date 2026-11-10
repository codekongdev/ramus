"""Delivery configuration fails at startup before any socket or message side effect."""

import pytest
from pydantic import ValidationError

from ramus_api.modules.access.fakes.services import FakeMailer
from ramus_api.modules.access.infrastructure.mailer import LoggingMailer
from ramus_api.modules.access.infrastructure.smtp_mailer import SmtpMailer
from ramus_api.modules.access.mailer_composition import MailerConfigurationError, build_mailer
from ramus_api.settings import Settings


def settings(**values):
    values.setdefault("RAMUS_AUTH_SECRET", "synthetic-stable-auth-secret-32-characters")
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def isolated_mail_environment(monkeypatch):
    for name in (
        "RAMUS_ENV", "RAMUS_MAILER", "RAMUS_SMTP_HOST", "RAMUS_SMTP_PORT", "RAMUS_SMTP_SECURITY",
        "RAMUS_SMTP_USERNAME", "RAMUS_SMTP_PASSWORD", "RAMUS_SMTP_FROM", "RAMUS_SMTP_TIMEOUT", "RAMUS_AUTH_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("environment", ["development", "test"])
def test_local_logging_and_explicit_injection_remain_available(environment):
    config = settings(RAMUS_ENV=environment)
    assert isinstance(build_mailer(config), LoggingMailer)
    fake = FakeMailer()
    assert build_mailer(config, fake) is fake


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_environment_rejects_implicit_and_injected_logging(environment):
    config = settings(RAMUS_ENV=environment)
    with pytest.raises(MailerConfigurationError):
        build_mailer(config)
    with pytest.raises(MailerConfigurationError):
        build_mailer(config, LoggingMailer())
    fake = FakeMailer()
    assert build_mailer(config, fake) is fake


@pytest.mark.parametrize("environment", ["development", "test", "staging", "production"])
def test_complete_smtp_configuration_constructs_without_a_network_call(environment, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Startup must not connect to SMTP")

    monkeypatch.setattr("smtplib.SMTP", unexpected)
    monkeypatch.setattr("smtplib.SMTP_SSL", unexpected)
    config = settings(
        RAMUS_ENV=environment, RAMUS_MAILER="smtp", RAMUS_SMTP_HOST="smtp.example.com",
        RAMUS_SMTP_FROM="login@example.com", RAMUS_SMTP_USERNAME="smtp-account",
        RAMUS_SMTP_PASSWORD="synthetic-password",
    )
    assert isinstance(build_mailer(config), SmtpMailer)
    assert "synthetic-password" not in repr(config)
    assert "synthetic-password" not in config.model_dump_json()


@pytest.mark.parametrize("values", [
    {}, {"RAMUS_SMTP_HOST": "smtp.example.com"}, {"RAMUS_SMTP_FROM": "login@example.com"},
    {"RAMUS_SMTP_HOST": " "}, {"RAMUS_SMTP_HOST": "smtp.example.com\r\nprivate"},
    {"RAMUS_SMTP_USERNAME": "smtp-account"}, {"RAMUS_SMTP_PASSWORD": "synthetic-password"},
])
def test_missing_or_unsafe_smtp_configuration_has_value_free_startup_errors(values):
    config_values = {"RAMUS_MAILER": "smtp"}
    if "RAMUS_SMTP_USERNAME" in values or "RAMUS_SMTP_PASSWORD" in values:
        config_values.update(RAMUS_SMTP_HOST="smtp.example.com", RAMUS_SMTP_FROM="login@example.com")
    config_values.update(values)
    with pytest.raises(MailerConfigurationError) as caught:
        build_mailer(settings(**config_values))
    assert "synthetic-password" not in str(caught.value)
    assert "smtp.example.com" not in str(caught.value)
    assert "login@example.com" not in str(caught.value)


@pytest.mark.parametrize(("variable", "value"), [
    ("RAMUS_ENV", "prodution"), ("RAMUS_MAILER", "unknown"), ("RAMUS_SMTP_SECURITY", "none"),
    ("RAMUS_SMTP_PORT", "0"), ("RAMUS_SMTP_PORT", "65536"),
    ("RAMUS_SMTP_TIMEOUT", "0"), ("RAMUS_SMTP_TIMEOUT", "31"), ("RAMUS_SMTP_TIMEOUT", "nan"),
    ("RAMUS_SMTP_FROM", "login@example.com\r\nBcc: other@example.com"),
])
def test_environment_schema_rejects_insecure_or_unbounded_delivery_configuration(variable, value):
    with pytest.raises(ValidationError):
        settings(**{variable: value})


def test_environment_values_select_tls_and_smtp_timeout(monkeypatch):
    monkeypatch.setenv("RAMUS_MAILER", "smtp")
    monkeypatch.setenv("RAMUS_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("RAMUS_SMTP_FROM", "login@example.com")
    monkeypatch.setenv("RAMUS_SMTP_SECURITY", "tls")
    monkeypatch.setenv("RAMUS_SMTP_PORT", "465")
    monkeypatch.setenv("RAMUS_SMTP_TIMEOUT", "4.5")
    config = settings()
    assert config.mailer_backend == "smtp" and config.smtp_security == "tls"
    assert config.smtp_port == 465 and config.smtp_timeout == 4.5
    assert isinstance(build_mailer(config), SmtpMailer)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_smtp_requires_a_stable_authentication_secret(environment):
    config = Settings(
        _env_file=None, RAMUS_ENV=environment, RAMUS_MAILER="smtp",
        RAMUS_SMTP_HOST="smtp.example.com", RAMUS_SMTP_FROM="login@example.com",
    )
    assert config.uses_ephemeral_auth_secret
    with pytest.raises(MailerConfigurationError, match="stable authentication secret"):
        build_mailer(config)
