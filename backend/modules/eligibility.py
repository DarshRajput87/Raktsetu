"""Donor eligibility rules. Checked at registration and before every donation."""

from datetime import date, timedelta

MIN_AGE, MAX_AGE = 18, 65
GAP_DAYS = {"M": 90, "F": 120}
HEALTH_FLAGS = ["recent_illness", "recent_surgery", "on_medication", "chronic_condition"]


def eligibility_reasons(donor: dict, today: date) -> list[str]:
    """Why a donor cannot donate today; an empty list means eligible. O(1)."""
    reasons = []
    age = donor.get("age")
    if age is None or not MIN_AGE <= age <= MAX_AGE:
        reasons.append(f"Age must be between {MIN_AGE} and {MAX_AGE}.")
    flags = [f for f, value in (donor.get("health_checklist") or {}).items() if value]
    if flags:
        reasons.append("Health checklist: " + ", ".join(f.replace("_", " ") for f in sorted(flags)) + ".")
    next_date = next_eligible_date(donor)
    if next_date is not None and today < next_date:
        reasons.append(f"Last donation was too recent; can donate again from {next_date.isoformat()}.")
    return reasons


def next_eligible_date(donor: dict) -> date | None:
    """The first day the gap since the last donation is long enough (None if never donated)."""
    last = donor.get("last_donation_date")
    if last is None:
        return None
    return last + timedelta(days=GAP_DAYS.get(donor.get("gender", "M"), 120))


def is_eligible(donor: dict, today: date) -> bool:
    """Age 18-65, no health flags, and at least 90 (M) / 120 (F) days since the last donation."""
    return not eligibility_reasons(donor, today)
