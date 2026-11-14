"""Production safety settings."""

import pytest

from config import DEV_JWT_SECRET, Settings

STRONG = "x" * 40


def make(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_development_shows_the_otp_and_production_does_not():
    assert make(environment="development").otp_in_response
    assert not make(environment="production", jwt_secret=STRONG).otp_in_response


def test_show_otp_overrides_the_environment():
    assert make(environment="production", jwt_secret=STRONG, show_otp=True).otp_in_response
    assert not make(environment="development", show_otp=False).otp_in_response


@pytest.mark.parametrize("secret", [DEV_JWT_SECRET, "short"])
def test_production_refuses_a_weak_jwt_secret(secret):
    with pytest.raises(RuntimeError):
        make(environment="production", jwt_secret=secret).check_production()


def test_production_accepts_a_strong_secret_and_development_anything():
    make(environment="production", jwt_secret=STRONG).check_production()
    make(environment="development", jwt_secret=DEV_JWT_SECRET).check_production()


def test_empty_show_otp_means_unset(monkeypatch):
    monkeypatch.setenv("SHOW_OTP", "")
    assert Settings(_env_file=None).show_otp is None
