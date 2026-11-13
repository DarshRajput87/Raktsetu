"""Append-only singly linked list, used as a transaction log."""

from typing import Any, Iterator


class _Node:
    __slots__ = ("value", "next")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.next: "_Node | None" = None


class LinkedList:
    """Items are only ever added at the tail, so the list keeps insertion order.

    append O(1), len O(1), iteration / to_list / last(n) O(n).
    """

    def __init__(self) -> None:
        self._head: _Node | None = None
        self._tail: _Node | None = None
        self._size = 0

    def append(self, item: Any) -> None:
        """Add at the tail. O(1) thanks to the tail pointer."""
        node = _Node(item)
        if self._tail is None:
            self._head = node
        else:
            self._tail.next = node
        self._tail = node
        self._size += 1

    def __iter__(self) -> Iterator[Any]:
        """Yield items oldest first. O(n) for a full pass."""
        node = self._head
        while node is not None:
            yield node.value
            node = node.next

    def to_list(self) -> list[Any]:
        """All items, oldest first. O(n)."""
        return list(self)

    def last(self, n: int) -> list[Any]:
        """The latest n items, oldest of them first. O(len).

        A singly linked list cannot walk backwards, so we skip the first
        len - n nodes and collect the rest.
        """
        if n <= 0:
            return []
        node = self._head
        for _ in range(max(0, self._size - n)):
            node = node.next  # type: ignore[union-attr]
        result = []
        while node is not None:
            result.append(node.value)
            node = node.next
        return result

    def __len__(self) -> int:
        """O(1)."""
        return self._size
