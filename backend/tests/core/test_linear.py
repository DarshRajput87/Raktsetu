"""Tests for Queue, Stack and LinkedList."""

import pytest

from core.linked_list import LinkedList
from core.queue import Queue
from core.stack import Stack


def test_queue_is_fifo():
    q = Queue()
    for i in range(5):
        q.enqueue(i)
    assert len(q) == 5 and q.peek() == 0
    assert [q.dequeue() for _ in range(5)] == [0, 1, 2, 3, 4]
    assert q.is_empty() and len(q) == 0


def test_queue_reusable_after_emptying():
    q = Queue()
    q.enqueue("a")
    assert q.dequeue() == "a"
    q.enqueue("b")
    q.enqueue("c")
    assert q.dequeue() == "b" and q.peek() == "c" and len(q) == 1


def test_queue_empty_errors():
    q = Queue()
    with pytest.raises(IndexError):
        q.dequeue()
    with pytest.raises(IndexError):
        q.peek()


def test_stack_is_lifo():
    s = Stack()
    for i in range(5):
        s.push(i)
    assert len(s) == 5 and s.peek() == 4
    assert [s.pop() for _ in range(5)] == [4, 3, 2, 1, 0]
    assert s.is_empty() and len(s) == 0


def test_stack_empty_errors():
    s = Stack()
    with pytest.raises(IndexError):
        s.pop()
    with pytest.raises(IndexError):
        s.peek()


def test_linked_list_keeps_insertion_order():
    log = LinkedList()
    assert len(log) == 0 and log.to_list() == [] and log.last(3) == []
    for i in range(10):
        log.append(i)
    assert len(log) == 10
    assert list(log) == list(range(10)) == log.to_list()


def test_linked_list_last_n():
    log = LinkedList()
    for ch in "abcde":
        log.append(ch)
    assert log.last(2) == ["d", "e"]
    assert log.last(5) == list("abcde")
    assert log.last(99) == list("abcde")
    assert log.last(0) == [] and log.last(-1) == []
