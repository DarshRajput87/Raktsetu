"""Array-based binary heaps written from scratch.

Both heaps store (key, item) pairs. Ties on the key are broken by insertion
order, so two entries with the same key come out in the order they went in.
"""

from typing import Any, Iterable

Entry = tuple[Any, int, Any]  # (key, insertion counter, item)


class _BinaryHeap:
    """Shared machinery. Subclasses only decide which of two entries goes first.

    The heap is a complete binary tree stored in a list: the children of the
    entry at index i live at 2i + 1 and 2i + 2, its parent at (i - 1) // 2.
    """

    def __init__(self, pairs: Iterable[tuple[Any, Any]] | None = None) -> None:
        self._data: list[Entry] = []
        self._counter = 0
        if pairs is not None:
            self.heapify(pairs)

    @staticmethod
    def _before(a: Entry, b: Entry) -> bool:
        """True if entry a must come out before entry b."""
        raise NotImplementedError

    def push(self, key: Any, item: Any) -> None:
        """Add an entry. O(log n): append at the end, then sift up."""
        self._data.append((key, self._counter, item))
        self._counter += 1
        self._sift_up(len(self._data) - 1)

    def pop(self) -> tuple[Any, Any]:
        """Remove and return the first (key, item). O(log n).

        Raises IndexError if the heap is empty.
        """
        if not self._data:
            raise IndexError("pop from an empty heap")
        top = self._data[0]
        last = self._data.pop()
        if self._data:
            self._data[0] = last
            self._sift_down(0)
        return top[0], top[2]

    def peek(self) -> tuple[Any, Any]:
        """Return the first (key, item) without removing it. O(1).

        Raises IndexError if the heap is empty.
        """
        if not self._data:
            raise IndexError("peek at an empty heap")
        return self._data[0][0], self._data[0][2]

    def heapify(self, pairs: Iterable[tuple[Any, Any]]) -> None:
        """Replace the contents with the given (key, item) pairs. O(n).

        Bottom-up build: sift down every non-leaf, starting from the last one.
        Most entries sit near the bottom and move very little, which is why the
        total work is O(n) instead of the O(n log n) of n separate pushes.
        """
        self._data = []
        for key, item in pairs:
            self._data.append((key, self._counter, item))
            self._counter += 1
        for i in range(len(self._data) // 2 - 1, -1, -1):
            self._sift_down(i)

    def items(self) -> list[tuple[Any, Any]]:
        """All (key, item) pairs in internal (not sorted) order. O(n)."""
        return [(key, item) for key, _, item in self._data]

    def is_empty(self) -> bool:
        """O(1)."""
        return not self._data

    def __len__(self) -> int:
        """O(1)."""
        return len(self._data)

    def _sift_up(self, i: int) -> None:
        """Move entry i up until its parent comes before it. O(log n)."""
        data = self._data
        entry = data[i]
        while i > 0:
            parent = (i - 1) // 2
            if not self._before(entry, data[parent]):
                break
            data[i] = data[parent]
            i = parent
        data[i] = entry

    def _sift_down(self, i: int) -> None:
        """Move entry i down until both children come after it. O(log n)."""
        data = self._data
        size = len(data)
        entry = data[i]
        while True:
            child = 2 * i + 1
            if child >= size:
                break
            right = child + 1
            if right < size and self._before(data[right], data[child]):
                child = right
            if not self._before(data[child], entry):
                break
            data[i] = data[child]
            i = child
        data[i] = entry


class MinHeap(_BinaryHeap):
    """Smallest key first; equal keys in insertion order.

    push O(log n), pop O(log n), peek O(1), heapify O(n), len O(1).
    """

    @staticmethod
    def _before(a: Entry, b: Entry) -> bool:
        return a[0] < b[0] or (a[0] == b[0] and a[1] < b[1])


class MaxHeap(_BinaryHeap):
    """Largest key first; equal keys in insertion order.

    Implemented directly (the comparison is reversed), so keys never need to be
    negated and any comparable key type works.
    push O(log n), pop O(log n), peek O(1), heapify O(n), len O(1).
    """

    @staticmethod
    def _before(a: Entry, b: Entry) -> bool:
        return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1])
