"""Process configuration. Every name in .env.example is read here."""

import logging
import os
from functools import lru_cache

from pydantic import BaseModel

logger = logging.getLogger("landfall.config")

# Fixed demo tenants. Policy lives here, not in the graph (FLOWS F0).
TENANT_POLICIES: dict[str, dict[str, bool]] = {
    "bayview": {"strict": False},
    "northgate": {"strict": True},
}

# Names in .env.example order. G017 compares this set to that file.
ENV_KEYS: tuple[str, ...] = (
    "FALKORDB_HOST",
    "FALKORDB_PORT",
    "FALKORDB_PASSWORD",
    "OPENFDA_API_KEY",
    "DAILYMED_BASE_URL",
    "OPENFDA_BASE_URL",
    "DAILYMED_RPS",
    "HTTP_CONTACT",
    "CACHE_DIR",
    "GRACE_DAYS",
    "AS_OF_OVERRIDE",
    "LANDFALL_FIXTURE_MODE",
    "OPENROUTER_API_KEY",
    "LLM_MODEL",
    "LLM_DAILY_BUDGET_CALLS",
    "EVAL_BASELINE_MODELS",
    "ADMIN_TOKEN",
    "PUBLISHER_SALT",
    "CORS_ORIGINS",
    "WATCH_INTERVAL_MINUTES",
    "SANDBOX_TTL_MINUTES",
    "WEB_BASE_URL",
    "NEXT_PUBLIC_API_URL",
)


class ConfigError(RuntimeError):
    """Startup configuration is missing a required value."""


class Settings(BaseModel):
    falkordb_host: str
    falkordb_port: int
    falkordb_password: str
    openfda_api_key: str
    dailymed_base_url: str
    openfda_base_url: str
    dailymed_rps: int
    http_contact: str
    cache_dir: str
    grace_days: int
    as_of_override: str
    fixture_mode: bool
    openrouter_api_key: str
    llm_model: str
    llm_daily_budget_calls: int
    eval_baseline_models: list[str]
    admin_token: str
    publisher_salt: str
    cors_origins: list[str]
    watch_interval_minutes: int
    sandbox_ttl_minutes: int
    web_base_url: str
    next_public_api_url: str
    version: str = "0.1.0"


def _raw(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_settings() -> Settings:
    settings = Settings(
        falkordb_host=_raw("FALKORDB_HOST", "localhost"),
        falkordb_port=int(_raw("FALKORDB_PORT", "6379")),
        falkordb_password=_raw("FALKORDB_PASSWORD", ""),
        openfda_api_key=_raw("OPENFDA_API_KEY", "").strip(),
        dailymed_base_url=_raw("DAILYMED_BASE_URL", "https://dailymed.nlm.nih.gov/dailymed"),
        openfda_base_url=_raw("OPENFDA_BASE_URL", "https://api.fda.gov"),
        dailymed_rps=int(_raw("DAILYMED_RPS", "2")),
        http_contact=_raw("HTTP_CONTACT", "arunsin997@gmail.com"),
        cache_dir=_raw("CACHE_DIR", ".cache"),
        grace_days=int(_raw("GRACE_DAYS", "30")),
        as_of_override=_raw("AS_OF_OVERRIDE", "").strip(),
        fixture_mode=_raw("LANDFALL_FIXTURE_MODE", "0") == "1",
        openrouter_api_key=_raw("OPENROUTER_API_KEY", "").strip(),
        llm_model=_raw("LLM_MODEL", "").strip(),
        llm_daily_budget_calls=int(_raw("LLM_DAILY_BUDGET_CALLS", "500")),
        eval_baseline_models=_csv(_raw("EVAL_BASELINE_MODELS", "")),
        admin_token=_raw("ADMIN_TOKEN", "").strip(),
        publisher_salt=_raw("PUBLISHER_SALT", "").strip(),
        cors_origins=_csv(_raw("CORS_ORIGINS", "http://localhost:3001,https://your-app.vercel.app")),
        watch_interval_minutes=int(_raw("WATCH_INTERVAL_MINUTES", "60")),
        sandbox_ttl_minutes=int(_raw("SANDBOX_TTL_MINUTES", "120")),
        web_base_url=_raw("WEB_BASE_URL", "http://localhost:3001"),
        next_public_api_url=_raw("NEXT_PUBLIC_API_URL", "http://localhost:8000"),
    )
    if not settings.openfda_api_key:
        logger.warning("OPENFDA_API_KEY is unset; openFDA allows 1,000 requests/day per IP")
    missing = [
        name
        for name, value in (("ADMIN_TOKEN", settings.admin_token), ("PUBLISHER_SALT", settings.publisher_salt))
        if not value
    ]
    if missing:
        raise ConfigError("Missing required configuration: " + ", ".join(missing))
    return settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()
