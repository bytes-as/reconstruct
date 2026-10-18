"""Process configuration. G004 expands this to every variable in .env.example."""

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    fixture_mode: bool = False
    version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        falkordb_host=os.environ.get("FALKORDB_HOST", "localhost"),
        falkordb_port=int(os.environ.get("FALKORDB_PORT", "6379")),
        falkordb_password=os.environ.get("FALKORDB_PASSWORD", ""),
        fixture_mode=os.environ.get("LANDFALL_FIXTURE_MODE", "0") == "1",
    )
