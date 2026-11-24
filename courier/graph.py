"""
Phase 3a — Customer graph and Dijkstra's shortest paths.

The road network is an undirected weighted graph stored as an adjacency list:

    adj = {"D": [("N01", 6.3), ("N04", 9.1)], "N01": [("D", 6.3), ...], ...}

Adjacency list space: O(V + E) — much smaller than an O(V^2) matrix for
sparse road networks where each junction has only a few roads.
"""

import heapq
import math


class Graph:
    def __init__(self):
        self.adj = {}

    def add_node(self, node):
        self.adj.setdefault(node, [])

    def add_edge(self, u, v, distance):
        """Add an undirected road between u and v."""
        self.add_node(u)
        self.add_node(v)
        self.adj[u].append((v, distance))
        self.adj[v].append((u, distance))

    @property
    def num_nodes(self):
        return len(self.adj)

    @property
    def num_edges(self):
        return sum(len(n) for n in self.adj.values()) // 2

    @classmethod
    def from_dataset(cls, dataset):
        g = cls()
        for node in dataset.nodes:
            g.add_node(node.id)
        for u, v, d in dataset.edges:
            g.add_edge(u, v, d)
        return g


def dijkstra(graph, source):
    """
    Single-source shortest paths with a binary heap (heapq).

    Returns (dist, prev):
        dist[v] - length of the shortest path source -> v (inf if unreachable)
        prev[v] - predecessor of v on that path (None for the source)

    Time O((V + E) log V), Space O(V).

    Uses "lazy deletion": instead of a decrease-key operation we push a new
    entry and skip stale ones when they are popped.
    """
    dist = {v: math.inf for v in graph.adj}
    prev = {v: None for v in graph.adj}
    dist[source] = 0.0
    heap = [(0.0, source)]
    visited = set()

    while heap:
        d, u = heapq.heappop(heap)
        if u in visited:          # stale entry, a shorter one was processed already
            continue
        visited.add(u)
        for v, w in graph.adj[u]:
            nd = d + w
            if nd < dist[v]:      # relaxation
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def reconstruct_path(prev, source, target):
    """Follow predecessor links back from target to source."""
    path = []
    node = target
    while node is not None:
        path.append(node)
        if node == source:
            break
        node = prev[node]
    path.reverse()
    if not path or path[0] != source:
        return []                 # target is unreachable
    return path


def distance_matrix(graph, points):
    """
    Run Dijkstra from every point of interest (depot + stops) and build:
        matrix[a][b] - shortest road distance from a to b
        paths[a][b]  - the actual node sequence of that road path

    This is the metric closure used by the TSP heuristic.
    Time O(k * (V + E) log V) for k points.
    """
    matrix, paths = {}, {}
    for a in points:
        dist, prev = dijkstra(graph, a)
        matrix[a] = {b: dist[b] for b in points}
        paths[a] = {b: reconstruct_path(prev, a, b) for b in points}
    return matrix, paths
