"""Application settings, read from environment variables or backend/.env."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    db_name: str = "raktsetu"
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expiry_minutes: int = 60 * 24
    search_radius_km: float = 25.0
    as_of_date: date | None = None
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"
    city_cache_capacity: int = 5
    contact_views_per_day: int = 20
    otp_ttl_seconds: int = 300

    @field_validator("as_of_date", mode="before")
    @classmethod
    def _empty_date_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def today(self) -> date:
        """The date the system treats as today (AS_OF_DATE, or the real date)."""
        return self.as_of_date or date.today()

    @property
    def is_dev(self) -> bool:
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
