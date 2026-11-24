"""
Phase 3b — Overall delivery route (Travelling Salesman approximation).

Finding the shortest tour through k stops is NP-hard (k! orders), so we use:

1. Nearest-Neighbour (NN) construction  — O(k^2)
   Start at the depot, always drive to the closest stop not yet visited,
   then return to the depot. Simple and fast, but can produce crossings.

2. 2-opt improvement (Phase 4 optimisation) — O(k^2) per pass
   Repeatedly reverse a segment of the tour if doing so shortens it,
   until no improving move is left (a local optimum).

3. Brute force (exact) — O(k!) — only for tiny k, to measure how far
   the heuristics are from the true optimum in tests and benchmarks.

All functions work on `matrix[a][b]` = shortest road distance (from Dijkstra).
A tour is a list of node ids that starts and ends with the depot.
"""

import itertools
import math


def tour_length(tour, matrix):
    """Sum of leg distances along the tour."""
    return sum(matrix[tour[i]][tour[i + 1]] for i in range(len(tour) - 1))


def nearest_neighbour(depot, stops, matrix):
    """Greedy nearest-neighbour tour: depot -> ... -> depot."""
    unvisited = set(stops) - {depot}
    tour = [depot]
    current = depot
    while unvisited:
        # pick the closest remaining stop (ties broken by id for determinism)
        nxt = min(unvisited, key=lambda s: (matrix[current][s], s))
        if math.isinf(matrix[current][nxt]):
            raise ValueError(f"Stop '{nxt}' is unreachable from '{current}'")
        tour.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    tour.append(depot)
    return tour


def two_opt(tour, matrix):
    """
    Improve a closed tour with 2-opt moves.

    Removing edges (a,b) and (c,d) and reconnecting as (a,c) and (b,d)
    is the same as reversing the segment b..c. We apply the move whenever
    it makes the tour shorter. Depot stays fixed at both ends.
    """
    best = list(tour)
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                a, b = best[i - 1], best[i]
                c, d = best[j], best[j + 1]
                delta = (matrix[a][c] + matrix[b][d]) - (matrix[a][b] + matrix[c][d])
                if delta < -1e-9:
                    best[i:j + 1] = reversed(best[i:j + 1])
                    improved = True
    return best


def brute_force(depot, stops, matrix):
    """Exact optimum by trying every permutation. Use only for k <= 9."""
    stops = [s for s in dict.fromkeys(stops) if s != depot]
    best_tour, best_len = [depot, depot], 0.0 if not stops else math.inf
    for perm in itertools.permutations(stops):
        tour = [depot, *perm, depot]
        length = tour_length(tour, matrix)
        if length < best_len:
            best_tour, best_len = tour, length
    return best_tour


def expand_route(tour, paths):
    """Turn a tour of stops into the full road-level node sequence."""
    if len(tour) < 2:
        return list(tour)
    full = [tour[0]]
    for i in range(len(tour) - 1):
        leg = paths[tour[i]][tour[i + 1]]
        full.extend(leg[1:])      # skip the first node, it is already in `full`
    return full
