"""Case 4: what a blood bank admin does to the stock. Every change is logged
(LinkedList) and can be undone (Stack of inverse actions)."""

from datetime import date, datetime

from modules import donors as donor_ops
from modules.compatibility import BLOOD_GROUPS, COMPONENTS
from modules.eligibility import is_eligible
from modules.state import AppState


def readable(component: str) -> str:
    """whole_blood -> whole blood, for messages people read."""
    return component.replace("_", " ")


def add_unit(state: AppState, bank_id: str, group: str | None, component: str, actor_id: str,
             today: date, now: datetime, donor_id: str | None = None) -> dict:
    """Add one unit to a bank. With a donor_id it is recorded as that donor's
    donation (the unit takes the donor's blood group). Undo removes the unit and
    restores the donor's previous donation date."""
    if component not in COMPONENTS:
        raise ValueError(f"unknown component: {component}")
    if donor_id:
        donor = state.donors_by_id[donor_id]
        previous = donor["last_donation_date"]
        unit = donor_ops.record_donation(state, donor_id, bank_id, component, today)
    else:
        if group not in BLOOD_GROUPS:
            raise ValueError(f"unknown blood group: {group}")
        donor, previous = None, None
        unit = donor_ops.new_unit(state, bank_id, group, component, today)
        state.inventory.add_unit(unit)
    state.audit.record(bank_id, "added", [unit["_id"]], actor_id, now,
                       {"blood_group": unit["blood_group"], "component": component, "donor_id": donor_id})

    def inverse() -> dict:
        state.inventory.remove_unit(unit["_id"])
        if donor is not None:
            donor["donations"] = [d for d in donor["donations"] if d["unit_id"] != unit["_id"]]
            donor["last_donation_date"] = previous
            donor["eligible"] = is_eligible(donor, today)
        state.audit.record(bank_id, "removed", [unit["_id"]], actor_id, now, {"undo_of": "added"})
        return {"removed_unit_ids": [unit["_id"]], "donor": donor}

    state.undo.push(actor_id, f"add {unit['blood_group']} {readable(component)} unit", inverse)
    return unit


def issue_units(state: AppState, bank_id: str, group: str, component: str, count: int,
                actor_id: str, today: date, now: datetime) -> list[dict]:
    """Issue `count` units of exactly this group, soonest to expire first (FEFO).
    Raises ValueError if the bank does not have that many. Undo returns them to stock."""
    available = state.inventory.count_available(bank_id, [group], component, today)
    if count > available:
        raise ValueError(f"Only {available} {group} {readable(component)} unit(s) available")
    units = state.inventory.issue(bank_id, [group], component, count, today)
    unit_ids = [u["_id"] for u in units]
    state.audit.record(bank_id, "issued", unit_ids, actor_id, now,
                       {"blood_group": group, "component": component})

    def inverse() -> dict:
        for unit_id in unit_ids:
            state.inventory.set_status(unit_id, "available")
        state.audit.record(bank_id, "returned", unit_ids, actor_id, now, {"undo_of": "issued"})
        return {"returned_unit_ids": unit_ids}

    state.undo.push(actor_id, f"issue {count} {group} {readable(component)} unit(s)", inverse)
    return units


def purge_expired(state: AppState, today: date, now: datetime) -> list[dict]:
    """Mark expired units in every bank and log them, one entry per bank."""
    expired = state.inventory.purge_expired(today)
    by_bank: dict[str, list[str]] = {}
    for unit in expired:
        by_bank.setdefault(unit["bank_id"], []).append(unit["_id"])
    for bank_id, unit_ids in by_bank.items():
        state.audit.record(bank_id, "expired", unit_ids, None, now)
    return expired
