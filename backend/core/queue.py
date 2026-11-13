"""FIFO queue on a singly linked list."""

from typing import Any


class _Node:
    __slots__ = ("value", "next")

    def __init__(self, value: Any) -> None:
        self.value = value
        self.next: "_Node | None" = None


class Queue:
    """First in, first out. Items join at the tail and leave from the head.

    enqueue, dequeue, peek, len and is_empty are all O(1) because we keep
    pointers to both ends and a running size.
    """

    def __init__(self) -> None:
        self._head: _Node | None = None
        self._tail: _Node | None = None
        self._size = 0

    def enqueue(self, item: Any) -> None:
        """Add at the tail. O(1)."""
        node = _Node(item)
        if self._tail is None:
            self._head = node
        else:
            self._tail.next = node
        self._tail = node
        self._size += 1

    def dequeue(self) -> Any:
        """Remove and return the head. O(1). Raises IndexError if empty."""
        if self._head is None:
            raise IndexError("dequeue from an empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return node.value

    def peek(self) -> Any:
        """Return the head without removing it. O(1). Raises IndexError if empty."""
        if self._head is None:
            raise IndexError("peek at an empty queue")
        return self._head.value

    def is_empty(self) -> bool:
        """O(1)."""
        return self._size == 0

    def __len__(self) -> int:
        """O(1)."""
        return self._size
