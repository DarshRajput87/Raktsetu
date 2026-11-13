"""Blood bank admin (Case 4). Every endpoint acts on the admin's own bank only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api import schemas
from api.convert import place_out, transaction_out, unit_out
from api.deps import DbDep, StateDep, TodayDep, now, require_role
from api.errors import ApiError, not_found
from api.services import flush_audit, save_request
from db import repositories as repo
from modules import requests as request_ops
from modules import stock
from modules.donors import NotEligible

router = APIRouter(prefix="/bank", tags=["bank admin"])
BankUser = Annotated[dict, Depends(require_role("bank_admin"))]
SOON_DAYS = 3


@router.get("/stock", response_model=schemas.StockOut)
async def get_stock(user: BankUser, state: StateDep, today: TodayDep) -> dict:
    """Stock by group and component, with the units that expire within 3 days."""
    bank_id = user["bank_id"]
    rows = state.inventory.stock_table(bank_id, today, SOON_DAYS)
    return {"bank": place_out(state.banks_by_id[bank_id]), "today": today,
            "total_units": sum(r["units"] for r in rows), "rows": rows,
            "expiring_soon": [unit_out(u) for u in state.inventory.expiring_within(bank_id, SOON_DAYS, today)]}


@router.post("/units", response_model=schemas.UnitOut, status_code=201)
async def add_unit(body: schemas.AddUnitIn, user: BankUser, state: StateDep, db: DbDep,
                   today: TodayDep) -> dict:
    """Add a unit. With donor_id it is recorded as that donor's donation: the
    donor must be eligible today, and becomes ineligible until the gap has passed."""
    if body.donor_id is None and body.blood_group is None:
        raise ApiError(400, "bad_request", "Give a blood_group, or a donor_id to record a donation.")
    if body.donor_id is not None and body.donor_id not in state.donors_by_id:
        raise not_found("Donor")
    try:
        unit = stock.add_unit(state, user["bank_id"], body.blood_group, body.component, user["_id"],
                              today, now(), body.donor_id)
    except NotEligible as exc:
        raise ApiError(409, "donor_not_eligible", str(exc))
    await repo.insert_unit(db, unit)
    if body.donor_id:
        donor = state.donors_by_id[body.donor_id]
        await repo.update_donor(db, donor["_id"], {"last_donation_date": donor["last_donation_date"],
                                                   "eligible": donor["eligible"],
                                                   "donations": donor["donations"]})
    await flush_audit(state, db)
    return unit_out(unit)


@router.post("/units/issue", response_model=schemas.IssueOut)
async def issue_units(body: schemas.IssueIn, user: BankUser, state: StateDep, db: DbDep,
                      today: TodayDep) -> dict:
    """Issue units of one group and component: the unit closest to expiry goes first (FEFO)."""
    try:
        units = stock.issue_units(state, user["bank_id"], body.group, body.component, body.count,
                                  user["_id"], today, now())
    except ValueError as exc:
        raise ApiError(409, "not_enough_stock", f"{exc}.")
    await repo.update_units_status(db, [u["_id"] for u in units], "issued")
    await flush_audit(state, db)
    return {"issued": [unit_out(u) for u in units]}


@router.get("/requests", response_model=list[schemas.BankRequestOut])
async def list_requests(user: BankUser, state: StateDep) -> list[dict]:
    """Hospital requests that reserved units at this bank: most urgent first, then oldest."""
    rows = []
    for request in state.requests_by_id.values():
        for allocation in request["allocations"]:
            if allocation["bank_id"] == user["bank_id"]:
                rows.append({"request_id": request["_id"], "hospital_name": request["hospital_name"],
                             "blood_group": request["blood_group"], "component": request["component"],
                             "patient_condition": request["patient_condition"],
                             "base_score": request["base_score"], "created_at": request["created_at"],
                             "units": allocation["units"], "distance_km": allocation["distance_km"],
                             "status": allocation["status"]})
    rows.sort(key=lambda r: (r["status"] != "pending", -r["base_score"], r["created_at"]))
    return rows


@router.patch("/requests/{request_id}", response_model=schemas.BankRequestOut)
async def decide_request(request_id: str, body: schemas.DecisionIn, user: BankUser, state: StateDep,
                         db: DbDep) -> dict:
    """Accept (the reserved units are issued) or reject (they return to stock and
    the request looks for the units at other banks)."""
    request = state.requests_by_id.get(request_id)
    if request is None:
        raise not_found("Request")
    try:
        request_ops.decide(state, request, user["bank_id"], body.action == "accept", user["_id"], now())
    except LookupError:
        raise ApiError(409, "nothing_pending", "This bank has no pending allocation for this request.")
    allocation = [a for a in request["allocations"] if a["bank_id"] == user["bank_id"]][-1]
    await repo.update_units_status(db, allocation["unit_ids"],
                                   "issued" if body.action == "accept" else "available")
    await save_request(db, request)
    await flush_audit(state, db)
    return {"request_id": request["_id"], "hospital_name": request["hospital_name"],
            "blood_group": request["blood_group"], "component": request["component"],
            "patient_condition": request["patient_condition"], "base_score": request["base_score"],
            "created_at": request["created_at"], "units": allocation["units"],
            "distance_km": allocation["distance_km"], "status": allocation["status"]}


@router.get("/transactions", response_model=list[schemas.TransactionOut])
async def transactions(user: BankUser, state: StateDep,
                       limit: Annotated[int, Query(ge=1, le=500)] = 50) -> list[dict]:
    """The bank's latest log entries (from the linked-list log), newest first."""
    return [transaction_out(e) for e in state.audit.recent(user["bank_id"], limit)]


@router.post("/undo", response_model=schemas.UndoOut)
async def undo(user: BankUser, state: StateDep, db: DbDep) -> dict:
    """Reverse this admin's most recent add or issue (a stack: last action first)."""
    try:
        description, result = state.undo.undo(user["_id"])
    except IndexError:
        raise ApiError(409, "nothing_to_undo", "There is nothing to undo.")
    for unit_id in result.get("removed_unit_ids", []):
        await repo.delete_unit(db, unit_id)
    await repo.update_units_status(db, result.get("returned_unit_ids", []), "available")
    donor = result.get("donor")
    if donor is not None:
        await repo.update_donor(db, donor["_id"], {"last_donation_date": donor["last_donation_date"],
                                                   "eligible": donor["eligible"],
                                                   "donations": donor["donations"]})
    await flush_audit(state, db)
    return {"undone": description, "can_undo_more": state.undo.can_undo(user["_id"])}
