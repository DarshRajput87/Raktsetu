"""Hospital requests (Case 2)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from api import schemas
from api.convert import request_out
from api.deps import DbDep, StateDep, now, require_role
from api.errors import not_found
from db import repositories as repo
from modules.requests import new_request

router = APIRouter(prefix="/hospital", tags=["hospital"])
HospitalUser = Annotated[dict, Depends(require_role("hospital"))]


@router.post("/requests", response_model=schemas.RequestOut, status_code=201)
async def create_request(body: schemas.RequestIn, user: HospitalUser, state: StateDep, db: DbDep) -> dict:
    """Raise a request. It joins the priority queue (urgency from the patient
    condition, plus aging) and is allocated from the nearest banks within a few
    seconds; poll GET /hospital/requests/{id} for the result."""
    hospital = state.hospitals_by_id[user["hospital_id"]]
    at = now()
    request = new_request(f"R-{uuid.uuid4().hex[:10].upper()}", hospital, body.group, body.component,
                          body.units_needed, body.patient_condition, at)
    state.requests_by_id[request["_id"]] = request
    state.request_queue.push(request, at)
    await repo.insert_request(db, request)
    return request_out(request, at)


@router.get("/requests", response_model=list[schemas.RequestOut])
async def list_requests(user: HospitalUser, state: StateDep) -> list[dict]:
    """This hospital's requests, newest first."""
    at = now()
    mine = [r for r in state.requests_by_id.values() if r["hospital_id"] == user["hospital_id"]]
    mine.sort(key=lambda r: r["created_at"], reverse=True)
    return [request_out(r, at) for r in mine]


@router.get("/requests/{request_id}", response_model=schemas.RequestOut)
async def get_request(request_id: str, user: HospitalUser, state: StateDep) -> dict:
    request = state.requests_by_id.get(request_id)
    if request is None or request["hospital_id"] != user["hospital_id"]:
        raise not_found("Request")
    return request_out(request, now())
