"""Login: OTP for the public and donors, email + password for staff accounts."""

import logging
import uuid
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from api import schemas
from api.convert import user_out
from api.deps import (DbDep, SettingsDep, StateDep, UserDep, app_services, check_password, create_token, now)
from api.errors import ApiError
from api.services import Services
from db import repositories as repo
from modules.auth import OtpStore

log = logging.getLogger("raktsetu")
router = APIRouter(prefix="/auth", tags=["auth"])
ServicesDep = Annotated[Services, Depends(app_services)]

OTP_ERRORS = {
    OtpStore.WRONG: ("wrong_otp", "That code is not correct."),
    OtpStore.EXPIRED: ("otp_expired", "That code has expired. Please request a new one."),
    OtpStore.MISSING: ("otp_not_requested", "Request a code for this phone number first."),
    OtpStore.LOCKED: ("otp_locked", "Too many wrong attempts. Please request a new code."),
}


def otp_message(otp: str, frontend_origin: str) -> str:
    """The SMS text. Its last line, "@<site> #<code>", lets phones fill the code in by
    themselves (WebOTP in Chrome on Android; iOS also reads it)."""
    site = urlparse(frontend_origin.split(",")[0].strip()).hostname or "localhost"
    return f"Your RaktSetu login code is {otp}. It is valid for 5 minutes.\n\n@{site} #{otp}"


def normalise_phone(phone: str) -> str:
    return phone.replace(" ", "")


@router.post("/otp/send", response_model=schemas.OtpSendOut)
async def send_otp(body: schemas.OtpSendIn, services: ServicesDep, settings: SettingsDep) -> dict:
    """Send a 6-digit login code. In development (or with SHOW_OTP=true) the code
    is also returned, because no SMS provider is connected yet."""
    phone = normalise_phone(body.phone)
    otp = services.otp.issue(phone, now())
    services.sms.send(phone, otp_message(otp, settings.frontend_origin))
    return {"sent": True, "expires_in_seconds": settings.otp_ttl_seconds,
            "dev_otp": otp if settings.otp_in_response else None}


@router.post("/otp/verify", response_model=schemas.TokenOut)
async def verify_otp(body: schemas.OtpVerifyIn, services: ServicesDep, db: DbDep,
                     settings: SettingsDep) -> dict:
    """Check the code; a first login creates the account with the role 'public'."""
    phone = normalise_phone(body.phone)
    outcome = services.otp.verify(phone, body.otp, now())
    if outcome != OtpStore.OK:
        code, message = OTP_ERRORS[outcome]
        raise ApiError(400, code, message)
    user = await repo.get_user_by_phone(db, phone)
    if user is None:
        user = {"_id": f"U-{uuid.uuid4().hex[:12]}", "phone": phone, "role": "public", "created_at": now()}
        await repo.insert_user(db, user)
    return {"token": create_token(user, settings), "user": user_out(user)}


@router.post("/login", response_model=schemas.TokenOut)
async def login(body: schemas.LoginIn, db: DbDep, state: StateDep, settings: SettingsDep) -> dict:
    """Hospital, blood bank admin and system admin accounts. Hospitals and banks
    can only log in once a system admin has verified them."""
    user = await repo.get_user_by_email(db, body.email.strip().lower())
    if user is None or not user.get("password_hash") or not check_password(body.password, user["password_hash"]):
        raise ApiError(401, "invalid_credentials", "Wrong email or password.")
    place = None
    if user["role"] == "hospital":
        place = state.hospitals_by_id.get(user.get("hospital_id"))
    elif user["role"] == "bank_admin":
        place = state.banks_by_id.get(user.get("bank_id"))
    if user["role"] in ("hospital", "bank_admin") and (place is None or not place.get("verified", False)):
        raise ApiError(403, "not_verified", "This account is waiting for verification by the system admin.")
    return {"token": create_token(user, settings), "user": user_out(user)}


@router.get("/me", response_model=schemas.UserOut)
async def me(user: UserDep) -> dict:
    return user_out(user)
