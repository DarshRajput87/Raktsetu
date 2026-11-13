"""LIFO stack on a singly linked list."""

from typing import Any


class _Node:
    __slots__ = ("value", "below")

    def __init__(self, value: Any, below: "_Node | None") -> None:
        self.value = value
        self.below = below


class Stack:
    """Last in, first out. Every operation is O(1): we only touch the top node."""

    def __init__(self) -> None:
        self._top: _Node | None = None
        self._size = 0

    def push(self, item: Any) -> None:
        """Put an item on top. O(1)."""
        self._top = _Node(item, self._top)
        self._size += 1

    def pop(self) -> Any:
        """Remove and return the top item. O(1). Raises IndexError if empty."""
        if self._top is None:
            raise IndexError("pop from an empty stack")
        node = self._top
        self._top = node.below
        self._size -= 1
        return node.value

    def peek(self) -> Any:
        """Return the top item without removing it. O(1). Raises IndexError if empty."""
        if self._top is None:
            raise IndexError("peek at an empty stack")
        return self._top.value

    def is_empty(self) -> bool:
        """O(1)."""
        return self._size == 0

    def __len__(self) -> int:
        """O(1)."""
        return self._size
