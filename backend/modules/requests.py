"""Case 2: hospital requests, served most urgent first.

A request waits in a max-heap keyed on its effective priority and is then
fulfilled greedily from the nearest banks.
"""

from datetime import date, datetime

from core.heap import MaxHeap

URGENCY: dict[str, int] = {
    "accident": 100,
    "delivery_complication": 100,
    "dengue_low_platelets": 80,
    "thalassemia": 75,
    "cancer_treatment": 65,
    "planned_surgery": 40,
    "other": 20,
}
AGING_PER_MINUTE = 0.5
MAX_DONOR_SUGGESTIONS = 20


def base_score(patient_condition: str) -> int:
    """Hash-map lookup of the urgency. O(1)."""
    return URGENCY.get(patient_condition, URGENCY["other"])


def effective_priority(request: dict, now: datetime) -> float:
    """Urgency plus a bonus for every minute spent waiting (aging), so that a
    low-urgency request cannot be starved forever by newer urgent ones."""
    waited_min = max(0.0, (now - request["created_at"]).total_seconds() / 60)
    return request["base_score"] + AGING_PER_MINUTE * waited_min


class RequestQueue:
    """Waiting requests in our MaxHeap, keyed on (effective priority, age).

    Why re-key: a key in the heap is the priority at the moment it was
    computed. Waiting changes the priority, but a binary heap never looks at
    its entries again and has no way to update a key in place. So on a timer
    (and before every pop) all keys are recomputed and the heap is rebuilt with
    heapify, which is O(n): cheaper than n separate pushes, O(n log n).

    push O(log n), pop O(n) (re-key, then O(log n) removal), rekey O(n).
    """

    def __init__(self) -> None:
        self._heap = MaxHeap()

    @staticmethod
    def _key(request: dict, now: datetime) -> tuple[float, float]:
        # Second part: of two requests with the same priority, the older goes first.
        return effective_priority(request, now), -request["created_at"].timestamp()

    def push(self, request: dict, now: datetime | None = None) -> None:
        self._heap.push(self._key(request, now or request["created_at"]), request)

    def rekey(self, now: datetime) -> None:
        self._heap.heapify([(self._key(request, now), request) for _, request in self._heap.items()])

    def pop(self, now: datetime) -> dict:
        """The request with the highest effective priority right now. IndexError if empty."""
        self.rekey(now)
        return self._heap.pop()[1]

    def peek(self) -> dict:
        return self._heap.peek()[1]

    def waiting(self) -> list[dict]:
        """Waiting requests in no particular order. O(n)."""
        return [request for _, request in self._heap.items()]

    def is_empty(self) -> bool:
        return self._heap.is_empty()

    def __len__(self) -> int:
        return len(self._heap)


def new_request(request_id: str, hospital: dict, group: str, component: str, units_needed: int,
                patient_condition: str, now: datetime) -> dict:
    return {
        "_id": request_id, "hospital_id": hospital["_id"], "hospital_name": hospital["name"],
        "city_id": hospital["city_id"], "blood_group": group, "component": component,
        "units_needed": units_needed, "patient_condition": patient_condition,
        "base_score": base_score(patient_condition), "created_at": now, "status": "queued",
        "allocations": [], "donor_suggestions": [], "excluded_banks": [],
        "processed_at": None, "sequence": None,
    }


def units_allocated(request: dict) -> int:
    return sum(len(a["unit_ids"]) for a in request["allocations"] if a["status"] != "rejected")


def fulfil(state, request: dict, today: date, now: datetime, radius_km: float = 25.0) -> dict:
    """Allocate units for a request, nearest bank first (greedy).

    Runs the Case 1 search from the hospital, then walks the banks in distance
    order, reserving as many units as each can give (soonest to expire first)
    until the request is covered. Whatever is still missing is reported with a
    list of donors to contact. Cost: one search plus O(u log n) for u units.
    """
    from modules.search import search_blood  # here to avoid a circular import

    hospital = state.hospitals_by_id[request["hospital_id"]]
    remaining = request["units_needed"] - units_allocated(request)
    result = search_blood(state, hospital["lat"], hospital["lng"], request["blood_group"],
                          request["component"], radius_km, today, city_id=hospital["city_id"],
                          exclude_banks=request["excluded_banks"], always_list_donors=True)
    for hit in result.banks:
        if remaining <= 0:
            break
        units = state.inventory.reserve(hit.bank_id, result.compatible_groups, request["component"],
                                        remaining, today)
        if not units:
            continue
        remaining -= len(units)
        request["allocations"].append({
            "bank_id": hit.bank_id, "bank_name": hit.name, "distance_km": hit.distance_km,
            "unit_ids": [u["_id"] for u in units],
            "units": [{"unit_id": u["_id"], "blood_group": u["blood_group"],
                       "expires_on": u["expires_on"]} for u in units],
            "status": "pending",
        })
        state.audit.record(hit.bank_id, "reserved", [u["_id"] for u in units], request["hospital_id"],
                           now, {"request_id": request["_id"]})

    # Matching donors near the hospital are always listed, nearest first, so the
    # hospital can reach donors even while banks are still deciding.
    request["donor_suggestions"] = [
        {"donor_id": d.donor_id, "name": d.name, "blood_group": d.blood_group,
         "distance_km": d.distance_km} for d in result.donors[:MAX_DONOR_SUGGESTIONS]]
    state.request_sequence += 1
    request["sequence"] = state.request_sequence
    request["processed_at"] = now
    request["status"] = request_status(request)
    return request


def request_status(request: dict) -> str:
    """allocated: fully covered, waiting for banks; completed: every bank accepted;
    partial: some units found; unfulfilled: none found."""
    active = [a for a in request["allocations"] if a["status"] != "rejected"]
    covered = sum(len(a["unit_ids"]) for a in active)
    if covered == 0:
        return "unfulfilled"
    if covered < request["units_needed"]:
        return "partial"
    return "completed" if all(a["status"] == "accepted" for a in active) else "allocated"


def process_queue(state, today: date, now: datetime, radius_km: float = 25.0) -> list[dict]:
    """Serve every waiting request, highest effective priority first."""
    processed = []
    while not state.request_queue.is_empty():
        processed.append(fulfil(state, state.request_queue.pop(now), today, now, radius_km))
    return processed


def decide(state, request: dict, bank_id: str, accept: bool, actor_id: str, now: datetime) -> dict:
    """A bank accepts or rejects its share of a request.

    Accept: the reserved units are issued. Reject: they go back into stock and
    the request rejoins the queue to look for the units elsewhere (this bank is
    left out next time). Raises LookupError if the bank has nothing pending.
    """
    allocation = next((a for a in request["allocations"]
                       if a["bank_id"] == bank_id and a["status"] == "pending"), None)
    if allocation is None:
        raise LookupError("no pending allocation for this bank")
    if accept:
        allocation["status"] = "accepted"
        for unit_id in allocation["unit_ids"]:
            state.inventory.set_status(unit_id, "issued")
        state.audit.record(bank_id, "issued", allocation["unit_ids"], actor_id, now,
                           {"request_id": request["_id"]})
        request["status"] = request_status(request)
    else:
        allocation["status"] = "rejected"
        for unit_id in allocation["unit_ids"]:
            state.inventory.set_status(unit_id, "available")
        state.audit.record(bank_id, "released", allocation["unit_ids"], actor_id, now,
                           {"request_id": request["_id"]})
        request["excluded_banks"].append(bank_id)
        request["status"] = "queued"
        state.request_queue.push(request, now)
    allocation["decided_at"] = now
    return request
