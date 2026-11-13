"""Endpoints that need no login: search, route, banks, cities."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Query

from api import schemas
from api.convert import place_out
from api.deps import DbDep, SettingsDep, StateDep, TodayDep
from api.errors import ApiError, not_found
from api.services import city_ready
from db.loaders import ensure_city_loaded
from modules.compatibility import BLOOD_GROUPS, COMPONENTS
from modules.requests import URGENCY
from modules.search import RouteResult, SearchResult, route_to_bank, search_blood

log = logging.getLogger("raktsetu")
router = APIRouter(tags=["public"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]


@router.get("/search", response_model=SearchResult, response_model_exclude_none=True)
async def search(state: StateDep, db: DbDep, today: TodayDep, settings: SettingsDep,
                 group: schemas.BloodGroup, component: schemas.Component, lat: Lat, lng: Lng,
                 radius: Annotated[float | None, Query(gt=0, le=100)] = None,
                 city: Annotated[str | None, Query(description="The city the user picked, if any.")] = None,
                 trace: Annotated[bool, Query(description="Also return Dijkstra's visit order.")] = False,
                 ) -> SearchResult:
    """Nearest blood banks with compatible, usable stock, with the route to the
    nearest one. If no bank within the radius has stock: matching donors (never
    with phone numbers; see GET /donors/{id}/contact)."""
    t0 = time.perf_counter()
    city_id = await city_ready(state, db, lat, lng, city)
    result = search_blood(state, lat, lng, group, component, radius or settings.search_radius_km,
                          today, city_id=city_id, trace=trace)
    log.info("search %s %s at (%.4f, %.4f) in %s: %d bank(s), %d donor(s), %d junctions, %.1f ms",
             group, component, lat, lng, city_id, len(result.banks), len(result.donors),
             result.junctions_visited, (time.perf_counter() - t0) * 1000)
    return result


@router.get("/route", response_model=RouteResult)
async def route(state: StateDep, db: DbDep, lat: Lat, lng: Lng, bank_id: str) -> RouteResult:
    """Shortest road route from a location to one bank."""
    bank = state.banks_by_id.get(bank_id)
    if bank is None:
        raise not_found("Blood bank")
    await ensure_city_loaded(state, db, bank["city_id"])
    result = route_to_bank(state, lat, lng, bank_id)
    if result is None:
        raise ApiError(404, "no_route", "No road route to this blood bank was found.")
    return result


@router.get("/banks", response_model=list[schemas.BankOut])
async def list_banks(state: StateDep, city: str | None = None) -> list[dict]:
    """Every verified blood bank (for the map pins)."""
    return [place_out(b) for b in state.banks_by_id.values()
            if b.get("verified", True) and (city is None or b["city_id"] == city)]


@router.get("/banks/{bank_id}", response_model=schemas.BankDetailOut)
async def get_bank(bank_id: str, state: StateDep, today: TodayDep) -> dict:
    bank = state.banks_by_id.get(bank_id)
    if bank is None:
        raise not_found("Blood bank")
    return dict(place_out(bank), stock=state.inventory.stock_table(bank_id, today))


@router.get("/cities", response_model=list[schemas.CityOut])
async def list_cities(state: StateDep) -> list[dict]:
    """The cities RaktSetu covers. Each bbox already includes the 25 km margin."""
    return [{"id": c["_id"], "name": c["name"], "center": c["center"], "bbox": c["bbox"],
             "notes": c.get("notes")} for c in state.cities.values()]


@router.get("/meta")
async def meta(settings: SettingsDep, today: TodayDep) -> dict:
    """Fixed lists the frontend needs for its forms."""
    return {"today": today, "radius_km": settings.search_radius_km, "blood_groups": BLOOD_GROUPS,
            "components": COMPONENTS, "patient_conditions": URGENCY,
            "attribution": "Road data (c) OpenStreetMap contributors"}
