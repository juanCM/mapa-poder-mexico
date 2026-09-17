from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mapa de Poder México API"
    environment: str = "development"
    database_url: Optional[str] = None
    public_web_origin: str = "http://localhost:3000"
    admin_api_token: Optional[str] = None
    seed_path: Path = Path(__file__).resolve().parents[3] / "packages/contracts/data/mvp.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
