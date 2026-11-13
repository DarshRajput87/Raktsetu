"""Least-recently-used cache: a hash map plus a doubly linked list."""

from typing import Any, Hashable


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: Any = None, value: Any = None) -> None:
        self.key = key
        self.value = value
        self.prev: "_Node | None" = None
        self.next: "_Node | None" = None


class LRUCache:
    """Keeps at most `capacity` entries; adding one more evicts the entry that
    was used longest ago.

    The dict finds an entry's list node in O(1); the doubly linked list keeps
    the entries in order of use (most recent at the front) and lets a node be
    unlinked and moved to the front in O(1). So get and put are both O(1).
    Two sentinel nodes (head, tail) remove the empty-list special cases.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._map: dict[Hashable, _Node] = {}
        self._head = _Node()  # most recently used side
        self._tail = _Node()  # least recently used side
        self._head.next = self._tail
        self._tail.prev = self._head

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the value and mark it as just used. O(1)."""
        node = self._map.get(key)
        if node is None:
            return default
        self._unlink(node)
        self._push_front(node)
        return node.value

    def put(self, key: Hashable, value: Any) -> tuple[Hashable, Any] | None:
        """Insert or update. Returns the evicted (key, value), if any. O(1)."""
        node = self._map.get(key)
        if node is not None:
            node.value = value
            self._unlink(node)
            self._push_front(node)
            return None
        node = _Node(key, value)
        self._map[key] = node
        self._push_front(node)
        if len(self._map) <= self.capacity:
            return None
        oldest = self._tail.prev
        self._unlink(oldest)
        del self._map[oldest.key]
        return oldest.key, oldest.value

    def peek(self, key: Hashable, default: Any = None) -> Any:
        """Return the value without counting it as a use. O(1)."""
        node = self._map.get(key)
        return default if node is None else node.value

    def keys(self) -> list[Hashable]:
        """Keys from most to least recently used. O(n)."""
        keys, node = [], self._head.next
        while node is not self._tail:
            keys.append(node.key)
            node = node.next
        return keys

    def __contains__(self, key: Hashable) -> bool:
        """Membership test that does not count as a use. O(1)."""
        return key in self._map

    def __len__(self) -> int:
        """O(1)."""
        return len(self._map)

    def _unlink(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _push_front(self, node: _Node) -> None:
        node.next = self._head.next
        node.prev = self._head
        self._head.next.prev = node
        self._head.next = node
