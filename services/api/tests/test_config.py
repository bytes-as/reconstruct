"""G004: every .env.example variable, required secrets, openFDA warning."""

import logging
from pathlib import Path

import pytest

from app.config import ENV_KEYS, ConfigError, get_settings


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".env.example").is_file():
            return parent
    mounted = Path("/repo/.env.example")
    if mounted.is_file():
        return mounted.parent
    raise RuntimeError(".env.example not found")


ROOT = _repo_root()


def _example_keys() -> list[str]:
    keys: list[str] = []
    for line in (ROOT / ".env.example").read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.append(stripped.split("=", 1)[0].strip())
    return keys


def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()


def test_example_keys_match_config() -> None:
    assert _example_keys() == list(ENV_KEYS)


def test_defaults_and_types(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _isolate(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setenv("PUBLISHER_SALT", "salt")
    with caplog.at_level(logging.WARNING, logger="landfall.config"):
        settings = get_settings()
    assert settings.falkordb_host == "localhost"
    assert settings.falkordb_port == 6379
    assert settings.falkordb_password == ""
    assert settings.dailymed_base_url == "https://dailymed.nlm.nih.gov/dailymed"
    assert settings.openfda_base_url == "https://api.fda.gov"
    assert settings.dailymed_rps == 2
    assert settings.http_contact == "arunsin997@gmail.com"
    assert settings.cache_dir == ".cache"
    assert settings.grace_days == 30
    assert settings.as_of_override == ""
    assert settings.fixture_mode is False
    assert settings.llm_daily_budget_calls == 500
    assert settings.eval_baseline_models == []
    assert settings.cors_origins == ["http://localhost:3001", "https://your-app.vercel.app"]
    assert settings.watch_interval_minutes == 60
    assert settings.sandbox_ttl_minutes == 120
    assert settings.web_base_url == "http://localhost:3001"
    assert settings.next_public_api_url == "http://localhost:8000"
    assert "1,000" in caplog.text


def test_openfda_key_suppresses_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _isolate(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setenv("PUBLISHER_SALT", "salt")
    monkeypatch.setenv("OPENFDA_API_KEY", "test-key")
    with caplog.at_level(logging.WARNING, logger="landfall.config"):
        settings = get_settings()
    assert settings.openfda_api_key == "test-key"
    assert "test-key" not in caplog.text
    assert "1,000" not in caplog.text


@pytest.mark.parametrize("name", ["ADMIN_TOKEN", "PUBLISHER_SALT"])
@pytest.mark.parametrize("value", ["", "   "])
def test_missing_secret_fails(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    _isolate(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setenv("PUBLISHER_SALT", "salt")
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError, match=name):
        get_settings()


def test_typed_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate(monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    monkeypatch.setenv("PUBLISHER_SALT", "salt")
    monkeypatch.setenv("LANDFALL_FIXTURE_MODE", "1")
    monkeypatch.setenv("GRACE_DAYS", "14")
    monkeypatch.setenv("EVAL_BASELINE_MODELS", "a/b, c/d")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3001")
    settings = get_settings()
    assert settings.fixture_mode is True
    assert settings.grace_days == 14
    assert settings.eval_baseline_models == ["a/b", "c/d"]
    assert settings.cors_origins == ["http://localhost:3001"]
