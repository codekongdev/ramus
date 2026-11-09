import pytest
from pydantic import ValidationError

from ramus_api.settings import DEFAULT_DATABASE_URL, Settings


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "RAMUS_API_PORT", "RAMUS_WEB_PORT"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_compose_database_and_dev_ports() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert "127.0.0.1:55432/ramus" in settings.database_url
    assert settings.api_port == 8000
    assert settings.web_port == 5173


def test_ports_are_read_from_ramus_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAMUS_API_PORT", "8010")
    monkeypatch.setenv("RAMUS_WEB_PORT", "5183")
    settings = Settings(_env_file=None)
    assert (settings.api_port, settings.web_port) == (8010, 5183)


def test_database_url_environment_overrides_env_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql+psycopg://from-file/db\nRAMUS_API_PORT=8020\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://from-env/db")
    settings = Settings(_env_file=env_file)
    assert settings.database_url == "postgresql+psycopg://from-env/db"
    assert settings.api_port == 8020


def test_missing_env_file_is_allowed(tmp_path) -> None:
    assert Settings(_env_file=tmp_path / "missing.env").api_port == 8000


@pytest.mark.parametrize("value", ["0", "65536", "-1", "abc", "80.5"])
@pytest.mark.parametrize("variable", ["RAMUS_API_PORT", "RAMUS_WEB_PORT"])
def test_invalid_ports_are_rejected(monkeypatch: pytest.MonkeyPatch, variable: str, value: str) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["1", "65535"])
def test_port_range_bounds_are_accepted(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("RAMUS_API_PORT", value)
    assert Settings(_env_file=None).api_port == int(value)


def test_settings_are_immutable() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(ValidationError):
        settings.api_port = 9000


@pytest.mark.parametrize("variable", ["RAMUS_API_PORT", "RAMUS_WEB_PORT"])
def test_empty_port_environment_value_falls_back_to_default(monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv(variable, "")
    settings = Settings(_env_file=None)
    assert (settings.api_port, settings.web_port) == (8000, 5173)


def test_empty_port_values_in_env_file_fall_back_to_defaults(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("RAMUS_API_PORT=\nRAMUS_WEB_PORT=\n")
    settings = Settings(_env_file=env_file)
    assert (settings.api_port, settings.web_port) == (8000, 5173)
