"""Transaction log per bank (our LinkedList) and undo per admin (our Stack)."""

from datetime import datetime
from typing import Callable

from core.linked_list import LinkedList
from core.stack import Stack

ACTIONS = {"added", "issued", "expired", "transferred", "reserved", "released", "removed", "returned"}


class AuditLog:
    """Append-only log of what happened to each bank's stock.

    record O(1) (dict lookup + linked-list append); recent(n) O(length of that
    bank's log), since a singly linked list is walked from the head.
    """

    def __init__(self) -> None:
        self._logs: dict[str, LinkedList] = {}
        self._count = 0
        self.unsaved: list[dict] = []  # recorded in memory, not yet written to MongoDB

    def record(self, bank_id: str, action: str, unit_ids: list[str], actor_id: str | None,
               at: datetime, details: dict | None = None) -> dict:
        if action not in ACTIONS:
            raise ValueError(f"unknown action: {action}")
        self._count += 1
        entry = {"_id": f"T{at.strftime('%Y%m%d%H%M%S')}-{self._count:06d}", "bank_id": bank_id,
                 "action": action, "unit_ids": list(unit_ids), "actor_id": actor_id, "at": at,
                 "details": details or {}}
        self._logs.setdefault(bank_id, LinkedList()).append(entry)
        self.unsaved.append(entry)
        return entry

    def restore(self, entry: dict) -> None:
        """Put back an entry loaded from MongoDB at startup."""
        self._count += 1
        self._logs.setdefault(entry["bank_id"], LinkedList()).append(entry)

    def recent(self, bank_id: str, limit: int = 50) -> list[dict]:
        """The latest entries of a bank, newest first."""
        log = self._logs.get(bank_id)
        return [] if log is None else log.last(limit)[::-1]

    def take_unsaved(self) -> list[dict]:
        entries, self.unsaved = self.unsaved, []
        return entries

    def __len__(self) -> int:
        return self._count


class UndoManager:
    """One Stack of inverse actions per admin (command pattern).

    Every stock change pushes the function that reverses it; undo pops the most
    recent one and runs it. push and pop are O(1).
    """

    def __init__(self) -> None:
        self._stacks: dict[str, Stack] = {}

    def push(self, admin_id: str, description: str, inverse: Callable[[], object]) -> None:
        self._stacks.setdefault(admin_id, Stack()).push((description, inverse))

    def can_undo(self, admin_id: str) -> bool:
        stack = self._stacks.get(admin_id)
        return stack is not None and not stack.is_empty()

    def undo(self, admin_id: str) -> tuple[str, object]:
        """Reverse the admin's latest action. Returns (what was undone, the
        inverse action's result). Raises IndexError if there is nothing to undo."""
        stack = self._stacks.get(admin_id)
        if stack is None or stack.is_empty():
            raise IndexError("nothing to undo")
        description, inverse = stack.pop()
        return description, inverse()
