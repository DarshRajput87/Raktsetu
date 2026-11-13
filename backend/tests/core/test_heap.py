import random

import pytest

from core.heap import MaxHeap, MinHeap


def drain(heap):
    out = []
    while not heap.is_empty():
        out.append(heap.pop())
    return out


def test_min_heap_random_matches_sorted():
    rng = random.Random(1)
    keys = [rng.randint(0, 10_000) for _ in range(1000)]
    heap = MinHeap()
    for k in keys:
        heap.push(k, f"item{k}")
    assert len(heap) == 1000
    assert [k for k, _ in drain(heap)] == sorted(keys)


def test_max_heap_random_matches_sorted():
    rng = random.Random(2)
    keys = [rng.random() for _ in range(1000)]
    heap = MaxHeap()
    for k in keys:
        heap.push(k, None)
    assert [k for k, _ in drain(heap)] == sorted(keys, reverse=True)


def test_interleaved_push_pop_matches_reference():
    rng = random.Random(3)
    heap, reference = MinHeap(), []
    for _ in range(2000):
        if reference and rng.random() < 0.4:
            reference.sort()
            assert heap.pop()[0] == reference.pop(0)
        else:
            k = rng.randint(0, 500)
            heap.push(k, None)
            reference.append(k)
        assert len(heap) == len(reference)


@pytest.mark.parametrize("heap_cls", [MinHeap, MaxHeap])
def test_equal_keys_come_out_in_insertion_order(heap_cls):
    heap = heap_cls()
    for i in range(50):
        heap.push(7, i)
    assert [item for _, item in drain(heap)] == list(range(50))


def test_stability_with_mixed_keys():
    heap = MinHeap()
    for key, item in [(2, "a"), (1, "b"), (2, "c"), (1, "d"), (2, "e")]:
        heap.push(key, item)
    assert drain(heap) == [(1, "b"), (1, "d"), (2, "a"), (2, "c"), (2, "e")]


def test_max_heap_stability_with_mixed_keys():
    heap = MaxHeap()
    for key, item in [(2, "a"), (1, "b"), (2, "c"), (1, "d")]:
        heap.push(key, item)
    assert drain(heap) == [(2, "a"), (2, "c"), (1, "b"), (1, "d")]


@pytest.mark.parametrize("heap_cls,reverse", [(MinHeap, False), (MaxHeap, True)])
def test_heapify_builds_a_valid_stable_heap(heap_cls, reverse):
    rng = random.Random(4)
    pairs = [(rng.randint(0, 30), i) for i in range(500)]
    heap = heap_cls()
    heap.push(99, "old")  # heapify replaces the contents
    heap.heapify(pairs)
    assert len(heap) == 500
    expected = sorted(pairs, key=lambda p: (-p[0] if reverse else p[0], p[1]))
    assert drain(heap) == expected


def test_constructor_accepts_pairs():
    assert drain(MinHeap([(3, "c"), (1, "a"), (2, "b")])) == [(1, "a"), (2, "b"), (3, "c")]


def test_peek_does_not_remove():
    heap = MinHeap()
    heap.push(5, "x")
    heap.push(3, "y")
    assert heap.peek() == (3, "y")
    assert len(heap) == 2


@pytest.mark.parametrize("heap_cls", [MinHeap, MaxHeap])
def test_empty_heap_raises(heap_cls):
    heap = heap_cls()
    assert heap.is_empty() and len(heap) == 0
    with pytest.raises(IndexError):
        heap.pop()
    with pytest.raises(IndexError):
        heap.peek()


def test_items_need_not_be_comparable():
    heap = MinHeap()
    heap.push(1, {"a": 1})
    heap.push(1, {"b": 2})
    assert heap.pop() == (1, {"a": 1})
