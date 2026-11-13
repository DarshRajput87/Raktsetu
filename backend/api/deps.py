"""Shared FastAPI dependencies: settings, clock, database, state and the logged-in user."""

from datetime import date, datetime, timedelta
from typing import Annotated, Callable

import bcrypt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.errors import ApiError
from config import Settings, get_settings
from db import repositories as repo
from db.mongo import get_db
from modules.dates import utcnow
from modules.state import AppState, get_state

ALGORITHM = "HS256"
ROLES = ("public", "donor", "hospital", "bank_admin", "admin")
bearer = HTTPBearer(auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
StateDep = Annotated[AppState, Depends(get_state)]


def get_today(settings: SettingsDep) -> date:
    return settings.today


TodayDep = Annotated[date, Depends(get_today)]


def create_token(user: dict, settings: Settings) -> str:
    """Signed JWT carrying the user id, role and expiry."""
    claims = {"sub": user["_id"], "role": user["role"],
              "exp": utcnow() + timedelta(minutes=settings.jwt_expiry_minutes)}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DbDep, settings: SettingsDep,
) -> dict | None:
    """The logged-in user, or None without a token. A bad token is always an error."""
    if credentials is None:
        return None
    try:
        claims = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise ApiError(401, "invalid_token", "Your session is invalid or has expired. Please log in again.")
    user = await repo.get_user(db, claims.get("sub", ""))
    if user is None:
        raise ApiError(401, "invalid_token", "This account no longer exists.")
    return user


async def get_current_user(user: Annotated[dict | None, Depends(get_optional_user)]) -> dict:
    if user is None:
        raise ApiError(401, "unauthorized", "Please log in to continue.")
    return user


UserDep = Annotated[dict, Depends(get_current_user)]


def require_role(*roles: str) -> Callable:
    """Dependency factory: the user must be logged in with one of the roles."""

    async def checker(user: UserDep) -> dict:
        if user["role"] not in roles:
            raise ApiError(403, "forbidden", f"This action needs the role: {' or '.join(roles)}.")
        return user

    return checker


def now() -> datetime:
    return utcnow()


def app_services(request: Request):
    """OTP store, contact limiter and SMS sender created at startup."""
    return request.app.state.services
