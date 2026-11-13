"""Donor registration and self-service, plus the guarded donor-contact endpoint."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api import schemas
from api.convert import donor_out, place_out, user_out
from api.deps import (DbDep, SettingsDep, StateDep, TodayDep, UserDep, app_services, create_token, now,
                      require_role)
from api.errors import ApiError, not_found
from api.services import Services, city_ready
from db import repositories as repo
from modules import donors as donor_ops
from modules.search import nearest_banks

router = APIRouter(prefix="/donors", tags=["donors"])
ServicesDep = Annotated[Services, Depends(app_services)]
DonorUser = Annotated[dict, Depends(require_role("donor"))]


def own_donor(state, user: dict) -> dict:
    donor = state.donors_by_id.get(user.get("donor_id") or "")
    if donor is None:
        raise not_found("Donor profile")
    return donor


@router.post("/register", response_model=schemas.DonorRegisterOut, status_code=201)
async def register(body: schemas.DonorRegisterIn, user: UserDep, state: StateDep, db: DbDep,
                   today: TodayDep, settings: SettingsDep) -> dict:
    """Become a donor. Needs an OTP login: the verified phone number is the
    donor's contact number. The location is snapped to the nearest road junction
    and, unless a bank is chosen, the nearest bank by road is linked."""
    if user["role"] not in ("public", "donor") or not user.get("phone"):
        raise ApiError(403, "forbidden", "Log in with your phone number to register as a donor.")
    if user.get("donor_id") in state.donors_by_id:
        raise ApiError(409, "already_registered", "This phone number is already registered as a donor.")
    await city_ready(state, db, body.lat, body.lng)
    data = body.model_dump()
    data.update(phone=user["phone"], user_id=user["_id"])
    try:
        donor = donor_ops.register(state, data, today)
    except ValueError as exc:
        raise ApiError(400, "bad_request", str(exc))
    await repo.insert_donor(db, donor)
    user.update(role="donor", donor_id=donor["_id"], name=donor["name"])
    await repo.update_user(db, user["_id"], {"role": "donor", "donor_id": donor["_id"], "name": donor["name"]})
    return {"donor": donor_out(state, donor, today), "token": create_token(user, settings),
            "user": user_out(user)}


@router.get("/me", response_model=schemas.DonorOut)
async def get_me(user: DonorUser, state: StateDep, today: TodayDep) -> dict:
    return donor_out(state, own_donor(state, user), today)


@router.patch("/me", response_model=schemas.DonorOut)
async def update_me(body: schemas.DonorUpdateIn, user: DonorUser, state: StateDep, db: DbDep,
                    today: TodayDep) -> dict:
    """Change availability, details or the linked bank."""
    donor = own_donor(state, user)
    changes = body.model_dump(exclude_unset=True)
    try:
        donor_ops.update(state, donor["_id"], changes, today)
    except ValueError as exc:
        raise ApiError(400, "bad_request", str(exc))
    saved = {k: donor[k] for k in ("name", "age", "gender", "lat", "lng", "node_id", "linked_bank_id",
                                   "available", "contact_consent", "health_checklist", "eligible")}
    await repo.update_donor(db, donor["_id"], saved)
    return donor_out(state, donor, today)


@router.get("/me/suggested-banks", response_model=list[schemas.SuggestedBank])
async def suggested_banks(user: UserDep, state: StateDep, db: DbDep,
                          lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
                          lng: Annotated[float | None, Query(ge=-180, le=180)] = None) -> list[dict]:
    """The 5 nearest banks by road distance: from the given location (while
    registering) or else from the donor's saved location."""
    if lat is None or lng is None:
        donor = own_donor(state, user)
        lat, lng = donor["lat"], donor["lng"]
    city_id = await city_ready(state, db, lat, lng)
    return [dict(place_out(bank), distance_km=km)
            for bank, km in nearest_banks(state, lat, lng, k=5, city_id=city_id)]


@router.get("/{donor_id}/contact", response_model=schemas.ContactOut)
async def contact(donor_id: str, user: UserDep, state: StateDep, db: DbDep,
                  services: ServicesDep) -> dict:
    """A donor's phone number. Login required; only donors who consented and are
    available; limited per user per day; every view is logged."""
    donor = state.donors_by_id.get(donor_id)
    if donor is None:
        raise not_found("Donor")
    if not (donor.get("contact_consent") and donor.get("available")):
        raise ApiError(403, "contact_not_shared", "This donor is not sharing contact details right now.")
    at = now()
    if not services.contact_limiter.allow(user["_id"], at.date()):
        raise ApiError(429, "rate_limited",
                       f"You have reached today's limit of {services.contact_limiter.limit} donor contacts. "
                       "Please try again tomorrow.")
    await repo.insert_access_log(db, {"_id": f"A-{uuid.uuid4().hex[:12]}", "viewer_id": user["_id"],
                                      "viewer_role": user["role"], "donor_id": donor_id, "at": at})
    return {"donor_id": donor_id, "name": donor["name"], "blood_group": donor["blood_group"],
            "phone": donor["phone"],
            "views_left_today": services.contact_limiter.remaining(user["_id"], at.date())}


@router.post("/{donor_id}/report", response_model=schemas.ReportOut, status_code=201)
async def report(donor_id: str, body: schemas.ReportIn, user: UserDep, state: StateDep, db: DbDep) -> dict:
    """Report misuse: a donor reporting unwanted contact, or a user reporting a donor entry."""
    if donor_id not in state.donors_by_id:
        raise not_found("Donor")
    entry = {"_id": f"M-{uuid.uuid4().hex[:12]}", "donor_id": donor_id, "reporter_id": user["_id"],
             "reporter_role": user["role"], "reason": body.reason, "status": "open", "at": now()}
    await repo.insert_misuse_report(db, entry)
    return dict(entry, id=entry["_id"])
