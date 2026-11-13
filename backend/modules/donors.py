"""Case 3: donor registration, availability and donations."""

import uuid
from datetime import date, timedelta

from modules.cities import snap_to_city
from modules.compatibility import BLOOD_GROUPS, COMPONENTS, SHELF_LIFE_DAYS
from modules.eligibility import HEALTH_FLAGS, eligibility_reasons, is_eligible
from modules.search import nearest_banks
from modules.state import AppState


class NotEligible(Exception):
    """The donor may not donate today."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(" ".join(reasons))
        self.reasons = reasons


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def snap(state: AppState, lat: float, lng: float, city_id: str | None = None) -> tuple[str, str]:
    """(city_id, node_id) of the nearest road junction of the location's city."""
    return snap_to_city(state.cities, lambda city: state.get_roads(city).index, lat, lng, city_id)


def register(state: AppState, data: dict, today: date) -> dict:
    """Create a donor: snap to the road network, compute eligibility, link a bank.

    The linked bank is the one the donor chose, or else the nearest by road
    (Dijkstra, stopping at the first bank reached).
    """
    if data["blood_group"] not in BLOOD_GROUPS:
        raise ValueError(f"unknown blood group: {data['blood_group']}")
    city_id, node_id = snap(state, data["lat"], data["lng"], data.get("city_id"))
    checklist = {flag: bool((data.get("health_checklist") or {}).get(flag, False)) for flag in HEALTH_FLAGS}
    donor = {
        "_id": data.get("_id") or new_id("D"), "city_id": city_id, "name": data["name"],
        "age": data["age"], "gender": data["gender"], "blood_group": data["blood_group"],
        "phone": data["phone"], "node_id": node_id, "lat": data["lat"], "lng": data["lng"],
        "linked_bank_id": None, "last_donation_date": data.get("last_donation_date"),
        "health_checklist": checklist, "eligible": False,
        "available": bool(data.get("available", True)),
        "contact_consent": bool(data.get("contact_consent", False)),
        "donations": [], "user_id": data.get("user_id"),
    }
    donor["linked_bank_id"] = _pick_bank(state, donor, data.get("linked_bank_id"))
    state.add_donor(donor)
    donor["eligible"] = is_eligible(donor, today)
    return donor


def _pick_bank(state: AppState, donor: dict, chosen: str | None) -> str | None:
    if chosen:
        if chosen not in state.banks_by_id:
            raise ValueError(f"unknown blood bank: {chosen}")
        return chosen
    nearest = nearest_banks(state, donor["lat"], donor["lng"], k=1, city_id=donor["city_id"])
    return nearest[0][0]["_id"] if nearest else None


def update(state: AppState, donor_id: str, changes: dict, today: date) -> dict:
    """Change a donor's details and recompute eligibility. O(1), except a moved
    location (one snap) or a changed blood group (O(donors of the old group))."""
    donor = state.donors_by_id[donor_id]
    if changes.get("linked_bank_id") and changes["linked_bank_id"] not in state.banks_by_id:
        raise ValueError(f"unknown blood bank: {changes['linked_bank_id']}")
    new_group = changes.get("blood_group")
    if new_group and new_group != donor["blood_group"]:
        if new_group not in BLOOD_GROUPS:
            raise ValueError(f"unknown blood group: {new_group}")
        groups = state.donors_by_group[donor["city_id"]]
        groups[donor["blood_group"]].remove(donor_id)
        groups.setdefault(new_group, []).append(donor_id)
    if changes.get("lat") is not None and changes.get("lng") is not None:
        city_id, node_id = snap(state, changes["lat"], changes["lng"])
        if city_id != donor["city_id"]:
            raise ValueError("moving a donor to another city is not supported; register again")
        donor["node_id"] = node_id
    for key in ("name", "age", "gender", "blood_group", "lat", "lng", "linked_bank_id",
                "available", "contact_consent", "health_checklist"):
        if changes.get(key) is not None:
            donor[key] = changes[key]
    donor["eligible"] = is_eligible(donor, today)
    return donor


def set_availability(state: AppState, donor_id: str, available: bool) -> dict:
    """O(1)."""
    donor = state.donors_by_id[donor_id]
    donor["available"] = available
    return donor


def record_donation(state: AppState, donor_id: str, bank_id: str, component: str, today: date) -> dict:
    """A donor gives blood at a bank: a new unit joins the bank's stock, the
    donor's last donation date moves to today and eligibility is recomputed
    (it turns false until the gap has passed). Returns the new unit.

    Raises NotEligible if the donor may not donate today. O(log n) for the heap push.
    """
    if component not in COMPONENTS:
        raise ValueError(f"unknown component: {component}")
    donor = state.donors_by_id[donor_id]
    reasons = eligibility_reasons(donor, today)
    if reasons:
        raise NotEligible(reasons)
    unit = new_unit(state, bank_id, donor["blood_group"], component, today, donor_id)
    state.inventory.add_unit(unit)
    donor.setdefault("donations", []).append(
        {"date": today, "bank_id": bank_id, "component": component, "unit_id": unit["_id"]})
    donor["last_donation_date"] = today
    donor["eligible"] = is_eligible(donor, today)
    return unit


def new_unit(state: AppState, bank_id: str, group: str, component: str, today: date,
             donor_id: str | None = None) -> dict:
    return {"_id": new_id("U"), "bank_id": bank_id, "city_id": state.banks_by_id[bank_id]["city_id"],
            "blood_group": group, "component": component, "collected_on": today,
            "expires_on": today + timedelta(days=SHELF_LIFE_DAYS[component]),
            "status": "available", "donor_id": donor_id}
