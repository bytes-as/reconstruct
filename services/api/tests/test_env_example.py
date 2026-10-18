"""G017: .env.example names match config.ENV_KEYS."""

from pathlib import Path

from app.config import ENV_KEYS


def _example_keys() -> list[str]:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env.example"
        if candidate.is_file():
            text = candidate.read_text()
            break
    else:
        text = Path("/repo/.env.example").read_text()
    keys: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.append(stripped.split("=", 1)[0].strip())
    return keys


def test_env_example_matches_config() -> None:
    assert _example_keys() == list(ENV_KEYS)
