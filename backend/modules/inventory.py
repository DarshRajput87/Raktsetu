"""Expiry-aware blood stock: first expired, first out (FEFO).

One MinHeap per (bank, blood group, component), keyed by expiry date, so the
unit that expires soonest is always on top.

Units leave a heap in the middle when they are reserved, removed or undone.
Our heap cannot delete from the middle, so those entries are left in place and
skipped when they reach the top ("lazy deletion"): an entry is live only if it
carries the unit's current ticket and the unit is still available.

n = units in one heap, K = heaps of one bank (at most 8 groups x 4 components).
"""

from datetime import date, timedelta

from core.heap import MinHeap
from modules.dates import to_date

HeapKey = tuple[str, str, str]  # (bank_id, blood_group, component)


class Inventory:
    def __init__(self) -> None:
        self._heaps: dict[HeapKey, MinHeap] = {}
        self._keys_by_bank: dict[str, list[HeapKey]] = {}
        self._units: dict[str, dict] = {}
        self._ticket: dict[str, int] = {}
        self._next_ticket = 0
        self._expired_backlog: list[dict] = []  # found expired while issuing

    # --- adding and reading ----------------------------------------------------

    def add_unit(self, unit: dict) -> None:
        """Record a unit; available ones go into their heap. O(log n)."""
        unit["collected_on"] = to_date(unit.get("collected_on"))
        unit["expires_on"] = to_date(unit["expires_on"])
        self._units[unit["_id"]] = unit
        if unit["status"] == "available":
            self._push(unit)

    def get(self, unit_id: str) -> dict | None:
        """O(1)."""
        return self._units.get(unit_id)

    def __len__(self) -> int:
        """Number of units known, in any status. O(1)."""
        return len(self._units)

    def _push(self, unit: dict) -> None:
        key = (unit["bank_id"], unit["blood_group"], unit["component"])
        heap = self._heaps.get(key)
        if heap is None:
            heap = self._heaps[key] = MinHeap()
            self._keys_by_bank.setdefault(unit["bank_id"], []).append(key)
        self._next_ticket += 1
        self._ticket[unit["_id"]] = self._next_ticket
        heap.push(unit["expires_on"], (unit["_id"], self._next_ticket))

    def _is_live(self, entry: tuple[str, int]) -> bool:
        unit_id, ticket = entry
        unit = self._units.get(unit_id)
        return unit is not None and unit["status"] == "available" and self._ticket.get(unit_id) == ticket

    def _live_top(self, heap: MinHeap) -> dict | None:
        """The soonest-expiring live unit of a heap, dropping stale entries above it."""
        while not heap.is_empty():
            _, entry = heap.peek()
            if self._is_live(entry):
                return self._units[entry[0]]
            heap.pop()
        return None

    def _live_units(self, key: HeapKey, today: date | None) -> list[dict]:
        """Live, non-expired units of one heap, in no particular order. O(n)."""
        heap = self._heaps.get(key)
        if heap is None:
            return []
        return [self._units[entry[0]] for expires_on, entry in heap.items()
                if self._is_live(entry) and (today is None or expires_on >= today)]

    # --- issuing ---------------------------------------------------------------

    def issue(self, bank_id: str, groups: list[str], component: str, count: int,
              today: date | None = None, new_status: str = "issued") -> list[dict]:
        """Take up to `count` units out of a bank, soonest to expire first.

        Groups are tried in the given order (exact match first), and within a
        group the earliest expiry always goes first. Units already past expiry
        are never issued. Returns the units taken, which may be fewer than
        asked for. O(count * log n), plus the stale entries dropped on the way.
        Expired units met on the way are marked and reported by the next purge_expired.
        """
        taken: list[dict] = []
        for group in groups:
            heap = self._heaps.get((bank_id, group, component))
            if heap is None:
                continue
            while len(taken) < count:
                unit = self._live_top(heap)
                if unit is None:
                    break
                heap.pop()
                if today is not None and unit["expires_on"] < today:
                    unit["status"] = "expired"
                    self._expired_backlog.append(unit)
                    continue
                unit["status"] = new_status
                taken.append(unit)
            if len(taken) == count:
                break
        return taken

    def reserve(self, bank_id: str, groups: list[str], component: str, count: int,
                today: date | None = None) -> list[dict]:
        """Like issue, but the units are held for a hospital request. O(count * log n)."""
        return self.issue(bank_id, groups, component, count, today, new_status="reserved")

    def set_status(self, unit_id: str, status: str) -> dict:
        """Change a unit's status; making it available again puts it back in its heap. O(log n)."""
        unit = self._units[unit_id]
        unit["status"] = status
        if status == "available":
            self._push(unit)
        return unit

    def remove_unit(self, unit_id: str) -> dict:
        """Forget a unit completely (undo of add_unit). O(1): its heap entry goes stale."""
        self._ticket.pop(unit_id, None)
        return self._units.pop(unit_id)

    # --- counting --------------------------------------------------------------

    def available_by_group(self, bank_id: str, groups: list[str], component: str,
                           today: date | None = None) -> dict[str, int]:
        """Usable units per group, leaving out groups with none. O(sum of heap sizes)."""
        result = {}
        for group in groups:
            n = len(self._live_units((bank_id, group, component), today))
            if n:
                result[group] = n
        return result

    def available_units(self, bank_id: str, group: str, component: str,
                        today: date | None = None) -> list[dict]:
        """Usable units of one (bank, group, component), in no particular order. O(n).

        Used by the simulator's "traditional" method, where a bank hands out a
        random unit instead of the soonest to expire.
        """
        return self._live_units((bank_id, group, component), today)

    def count_available(self, bank_id: str, groups: list[str], component: str,
                        today: date | None = None) -> int:
        """Usable (available, not expired) units of any of the groups. O(sum of heap sizes)."""
        return sum(self.available_by_group(bank_id, groups, component, today).values())

    def stock_table(self, bank_id: str, today: date, soon_days: int = 3) -> list[dict]:
        """One row per (group, component) with stock: units, earliest expiry, how many
        expire within soon_days. O(units of the bank)."""
        rows = []
        limit = today + timedelta(days=soon_days)
        for key in self._keys_by_bank.get(bank_id, []):
            units = self._live_units(key, today)
            if units:
                rows.append({
                    "blood_group": key[1], "component": key[2], "units": len(units),
                    "earliest_expiry": min(u["expires_on"] for u in units),
                    "expiring_soon": sum(1 for u in units if u["expires_on"] <= limit),
                })
        return rows

    def expiring_within(self, bank_id: str, days: int, today: date) -> list[dict]:
        """Available units of a bank that expire within `days`, soonest first.

        Collects the matches (O(units of the bank)) and orders them with a
        MinHeap (O(m log m) for m matches).
        """
        limit = today + timedelta(days=days)
        soon = MinHeap()
        for key in self._keys_by_bank.get(bank_id, []):
            for unit in self._live_units(key, today):
                if unit["expires_on"] <= limit:
                    soon.push(unit["expires_on"], unit)
        return [soon.pop()[1] for _ in range(len(soon))]

    def purge_expired(self, today: date) -> list[dict]:
        """Mark every available unit past its expiry as expired and return them.

        Each heap is popped only while its top has expired, so the cost is
        O(H + x log n) for H heaps and x expired units: heaps with nothing
        expired cost a single peek.
        """
        expired, self._expired_backlog = self._expired_backlog, []
        for heap in self._heaps.values():
            while True:
                unit = self._live_top(heap)
                if unit is None or unit["expires_on"] >= today:
                    break
                heap.pop()
                unit["status"] = "expired"
                expired.append(unit)
        return expired
