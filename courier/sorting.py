"""
Phase 2a — Parcel prioritisation.

Four comparison sorts are implemented from scratch so they can be compared
in Phase 4. Every function takes a list and a `key` function and returns a
NEW sorted list (the input is not modified).

    Algorithm        Best        Average     Worst       Space     Stable
    ---------------  ----------  ----------  ----------  --------  ------
    Insertion sort   O(n)        O(n^2)      O(n^2)      O(1)      yes
    Merge sort       O(n log n)  O(n log n)  O(n log n)  O(n)      yes   <- chosen
    Quick sort       O(n log n)  O(n log n)  O(n^2)      O(log n)  no
    Heap sort        O(n log n)  O(n log n)  O(n log n)  O(1)      no

Merge sort is used by the planner: it has a guaranteed O(n log n) bound and
is stable, so two parcels with the same (deadline, priority, value) keep the
order in which they arrived at the depot.
"""

import random


def _identity(x):
    return x


# ---------------------------------------------------------------- insertion
def insertion_sort(items, key=_identity):
    """Insert each element into the already-sorted prefix on its left."""
    arr = list(items)
    for i in range(1, len(arr)):
        current = arr[i]
        current_key = key(current)
        j = i - 1
        # shift bigger elements one place right to make room
        while j >= 0 and key(arr[j]) > current_key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = current
    return arr


# ---------------------------------------------------------------- merge
def merge_sort(items, key=_identity):
    """Divide in half, sort each half recursively, then merge the two halves."""
    arr = list(items)
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid], key)
    right = merge_sort(arr[mid:], key)
    return _merge(left, right, key)


def _merge(left, right, key):
    """Merge two sorted lists. `<=` keeps equal elements in order (stability)."""
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if key(left[i]) <= key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    # one of the halves is exhausted; copy the rest of the other
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


# ---------------------------------------------------------------- quick
def quick_sort(items, key=_identity):
    """
    In-place quick sort with a random pivot (Lomuto partition).
    A random pivot makes the O(n^2) worst case very unlikely on sorted input.
    """
    arr = list(items)
    _quick(arr, 0, len(arr) - 1, key)
    return arr


def _quick(arr, low, high, key):
    # loop on the larger part and recurse on the smaller one -> O(log n) stack
    while low < high:
        p = _partition(arr, low, high, key)
        if p - low < high - p:
            _quick(arr, low, p - 1, key)
            low = p + 1
        else:
            _quick(arr, p + 1, high, key)
            high = p - 1


def _partition(arr, low, high, key):
    r = random.randint(low, high)
    arr[r], arr[high] = arr[high], arr[r]          # move pivot to the end
    pivot_key = key(arr[high])
    i = low - 1
    for j in range(low, high):
        if key(arr[j]) <= pivot_key:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[high] = arr[high], arr[i + 1]  # pivot to its final place
    return i + 1


# ---------------------------------------------------------------- heap
def heap_sort(items, key=_identity):
    """Build a max-heap, then repeatedly move the root (largest) to the end."""
    arr = list(items)
    n = len(arr)
    for i in range(n // 2 - 1, -1, -1):     # build heap bottom-up: O(n)
        _sift_down(arr, i, n, key)
    for end in range(n - 1, 0, -1):         # n extractions: O(n log n)
        arr[0], arr[end] = arr[end], arr[0]
        _sift_down(arr, 0, end, key)
    return arr


def _sift_down(arr, root, size, key):
    while True:
        largest = root
        left, right = 2 * root + 1, 2 * root + 2
        if left < size and key(arr[left]) > key(arr[largest]):
            largest = left
        if right < size and key(arr[right]) > key(arr[largest]):
            largest = right
        if largest == root:
            return
        arr[root], arr[largest] = arr[largest], arr[root]
        root = largest


# Registry used by the benchmark and the web UI
ALGORITHMS = {
    "insertion": insertion_sort,
    "merge": merge_sort,
    "quick": quick_sort,
    "heap": heap_sort,
}


def prioritise(parcels, algorithm="merge"):
    """Sort parcels by (deadline, -priority, -value) with the chosen algorithm."""
    sorter = ALGORITHMS[algorithm]
    return sorter(parcels, key=lambda p: p.sort_key())
