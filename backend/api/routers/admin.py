"""System admin: verify hospitals and banks, read misuse reports."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api import schemas
from api.convert import place_out
from api.deps import DbDep, StateDep, require_role
from api.errors import not_found
from db import repositories as repo

router = APIRouter(prefix="/admin", tags=["system admin"])
AdminUser = Annotated[dict, Depends(require_role("admin"))]


@router.get("/places", response_model=list[schemas.PlaceOut])
async def list_places(_: AdminUser, state: StateDep) -> list[dict]:
    """Every hospital and bank, unverified first."""
    places = [dict(place_out(h), kind="hospital") for h in state.hospitals_by_id.values()]
    places += [dict(place_out(b), kind="bank") for b in state.banks_by_id.values()]
    places.sort(key=lambda p: (p["verified"], p["kind"], p["name"]))
    return places


@router.patch("/hospitals/{hospital_id}/verify", response_model=schemas.PlaceOut)
async def verify_hospital(hospital_id: str, body: schemas.VerifyIn, _: AdminUser, state: StateDep,
                          db: DbDep) -> dict:
    hospital = state.hospitals_by_id.get(hospital_id)
    if hospital is None:
        raise not_found("Hospital")
    hospital["verified"] = body.verified
    await repo.update_hospital(db, hospital_id, {"verified": body.verified})
    return dict(place_out(hospital), kind="hospital")


@router.patch("/banks/{bank_id}/verify", response_model=schemas.PlaceOut)
async def verify_bank(bank_id: str, body: schemas.VerifyIn, _: AdminUser, state: StateDep,
                      db: DbDep) -> dict:
    """An unverified bank does not appear in search results and its admin cannot log in."""
    bank = state.banks_by_id.get(bank_id)
    if bank is None:
        raise not_found("Blood bank")
    bank["verified"] = body.verified
    await repo.update_bank(db, bank_id, {"verified": body.verified})
    return dict(place_out(bank), kind="bank")


@router.get("/reports", response_model=list[schemas.ReportOut])
async def list_reports(_: AdminUser, db: DbDep) -> list[dict]:
    """Misuse reports, newest first."""
    reports = await repo.list_misuse_reports(db)
    reports.sort(key=lambda r: r["at"], reverse=True)
    return [dict(r, id=r["_id"]) for r in reports]
