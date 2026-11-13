"""In-memory documents -> response shapes."""

from datetime import date, datetime

from modules.eligibility import eligibility_reasons, next_eligible_date
from modules.requests import effective_priority, units_allocated
from modules.state import AppState


def user_out(user: dict) -> dict:
    return {"id": user["_id"], "role": user["role"], "name": user.get("name"), "phone": user.get("phone"),
            "email": user.get("email"), "donor_id": user.get("donor_id"), "bank_id": user.get("bank_id"),
            "hospital_id": user.get("hospital_id")}


def place_out(place: dict) -> dict:
    return {"id": place["_id"], "name": place["name"], "area": place.get("area", ""),
            "city_id": place["city_id"], "lat": place["lat"], "lng": place["lng"],
            "phone": place["phone"], "verified": place.get("verified", True)}


def unit_out(unit: dict) -> dict:
    return {"id": unit["_id"], "bank_id": unit["bank_id"], "blood_group": unit["blood_group"],
            "component": unit["component"], "collected_on": unit.get("collected_on"),
            "expires_on": unit["expires_on"], "status": unit["status"], "donor_id": unit.get("donor_id")}


def donor_out(state: AppState, donor: dict, today: date) -> dict:
    bank = state.banks_by_id.get(donor.get("linked_bank_id") or "")
    donations = [dict(d, bank_name=state.banks_by_id.get(d["bank_id"], {}).get("name"))
                 for d in donor.get("donations", [])]
    reasons = eligibility_reasons(donor, today)
    return {
        "id": donor["_id"], "name": donor["name"], "age": donor["age"], "gender": donor["gender"],
        "blood_group": donor["blood_group"], "phone": donor["phone"], "city_id": donor["city_id"],
        "lat": donor["lat"], "lng": donor["lng"], "linked_bank_id": donor.get("linked_bank_id"),
        "linked_bank_name": bank["name"] if bank else None,
        "last_donation_date": donor.get("last_donation_date"),
        "next_eligible_date": next_eligible_date(donor),
        "health_checklist": donor.get("health_checklist", {}),
        "eligible": not reasons, "eligibility_reasons": reasons,
        "available": donor.get("available", False), "contact_consent": donor.get("contact_consent", False),
        "donations": donations[::-1],
    }


def request_out(request: dict, now: datetime, banks: dict[str, dict] | None = None) -> dict:
    waiting = request["status"] == "queued"
    return {
        "id": request["_id"], "hospital_id": request["hospital_id"],
        "hospital_name": request["hospital_name"], "blood_group": request["blood_group"],
        "component": request["component"], "units_needed": request["units_needed"],
        "units_allocated": units_allocated(request), "patient_condition": request["patient_condition"],
        "base_score": request["base_score"],
        "priority": round(effective_priority(request, now) if waiting else request["base_score"], 1),
        "status": request["status"], "created_at": request["created_at"],
        "processed_at": request.get("processed_at"), "sequence": request.get("sequence"),
        "allocations": [{"bank_id": a["bank_id"], "bank_name": a["bank_name"],
                         "distance_km": a["distance_km"], "units": a["units"], "status": a["status"],
                         "bank_phone": (banks or {}).get(a["bank_id"], {}).get("phone")}
                        for a in request["allocations"]],
        "donor_suggestions": request.get("donor_suggestions", []),
    }


def transaction_out(entry: dict) -> dict:
    return {"id": entry["_id"], "action": entry["action"], "unit_ids": entry["unit_ids"],
            "actor_id": entry.get("actor_id"), "at": entry["at"], "details": entry.get("details", {})}
