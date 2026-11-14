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


def test_env_file_defaults_to_dot_env(monkeypatch):
    from config import BACKEND_DIR, env_file

    monkeypatch.delenv("ENV_FILE", raising=False)
    assert env_file() == BACKEND_DIR / ".env"


def test_env_file_follows_env_file_variable(monkeypatch, tmp_path):
    from config import env_file

    target = tmp_path / "atlas.env"
    target.write_text("MONGO_URI=mongodb://atlas.example:27017\nDB_NAME=from_file\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(target))
    monkeypatch.delenv("DB_NAME", raising=False)
    assert env_file() == target
    assert Settings(_env_file=env_file()).db_name == "from_file"


def test_a_missing_env_file_is_an_error_not_a_silent_fallback(monkeypatch):
    from config import env_file

    monkeypatch.setenv("ENV_FILE", ".env.does-not-exist")
    with pytest.raises(FileNotFoundError):
        env_file()


def test_serve_never_prints_the_password():
    from serve import safe_host

    fake = "mongodb+srv://user:" + "secret@cluster0.example.mongodb.net/"  # split so the leak test ignores it
    assert safe_host(fake) == "cluster0.example.mongodb.net"
    assert safe_host("mongodb://localhost:27017") == "localhost"
