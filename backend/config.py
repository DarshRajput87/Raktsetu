"""Application settings, read from environment variables or backend/.env."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
DEV_JWT_SECRET = "dev-only-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    db_name: str = "raktsetu"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expiry_minutes: int = 60 * 24
    search_radius_km: float = 25.0
    as_of_date: date | None = None
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"
    city_cache_capacity: int = 5
    contact_views_per_day: int = 20
    otp_ttl_seconds: int = 300
    request_dispatch_seconds: float = 3.0
    background_tasks: bool = True
    # Return the OTP in the /auth/otp/send response. On by default in development;
    # a public demo without an SMS provider sets SHOW_OTP=true in production too.
    show_otp: bool | None = None

    @field_validator("as_of_date", "show_otp", mode="before")
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

    @property
    def otp_in_response(self) -> bool:
        return self.is_dev if self.show_otp is None else self.show_otp

    def check_production(self) -> None:
        """Refuse to run in production with the development JWT secret."""
        if not self.is_dev and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise RuntimeError("Set JWT_SECRET to a random string of at least 32 characters in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
