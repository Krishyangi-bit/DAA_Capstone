# Phase 1 — Courier Problem Design and Planning

## 1. Problem statement

A small courier hub (the **depot**) receives a batch of parcels every morning.
Each parcel must be taken to a customer location on a road network. The delivery
van has a limited **weight capacity**, so not every parcel fits on one trip.

The planner must answer three questions:

1. **In what order should parcels be considered?** — by urgency (deadline) and priority.
2. **Which parcels go on this trip?** — the set with the highest total value that fits in the van.
3. **In what order should the van visit customers?** — a short closed tour that starts and ends at the depot.

## 2. Data design

### Parcel

| Attribute     | Type  | Meaning                                                   |
|---------------|-------|-----------------------------------------------------------|
| `id`          | str   | Unique parcel id, e.g. `P07`                              |
| `destination` | str   | Id of the delivery node in the graph                      |
| `weight`      | int   | Weight in kg (integer so it can index the DP table)       |
| `value`       | int   | Business value of delivering it today (higher = better)   |
| `deadline`    | int   | Hours from dispatch by which it should be delivered       |
| `priority`    | int   | 1 (low) … 5 (express)                                     |

### Delivery point (graph node)

| Attribute | Type  | Meaning                                  |
|-----------|-------|------------------------------------------|
| `id`      | str   | Node id, e.g. `D` (depot), `N03`         |
| `name`    | str   | Human readable name                      |
| `x`, `y`  | float | Map coordinates (used only for drawing)  |

### Road (graph edge)

Undirected weighted edge: `{"from": "N01", "to": "N04", "distance": 7.5}` (km).

### Dataset file (JSON)

```json
{
  "name": "small",
  "depot": "D",
  "capacity": 25,
  "nodes":   [{"id": "D", "name": "Depot", "x": 50, "y": 50}, ...],
  "edges":   [{"from": "D", "to": "N01", "distance": 6.3}, ...],
  "parcels": [{"id": "P01", "destination": "N01", "weight": 4,
               "value": 60, "deadline": 3, "priority": 5}, ...]
}
```

The graph is stored in memory as an **adjacency list**
`{node: [(neighbour, distance), ...]}` — O(V + E) space, ideal for sparse road maps.

## 3. Algorithm selection

| Stage                     | Algorithm                              | Why this one                                                                                       | Time            | Space   |
|---------------------------|----------------------------------------|----------------------------------------------------------------------------------------------------|-----------------|---------|
| Prioritise parcels        | **Merge Sort** (compared with Insertion, Quick, Heap) | Guaranteed O(n log n) in every case and **stable** — parcels with equal keys keep their input order. | O(n log n)      | O(n)    |
| Fill the van              | **0/1 Knapsack — Dynamic Programming** | Parcels cannot be split; DP gives the exact optimum where greedy-by-ratio can fail.                | O(n · W)        | O(n · W)|
| Shortest road paths       | **Dijkstra (binary heap)**             | All distances are non-negative; heap version is fast on sparse graphs.                            | O((V + E) log V)| O(V)    |
| Visiting order            | **Nearest-Neighbour TSP heuristic**    | TSP is NP-hard; NN gives a reasonable tour in polynomial time.                                     | O(k²)           | O(k)    |
| Tour improvement (Phase 4)| **2-opt local search**                 | Removes crossing edges from the NN tour, usually shortening it noticeably.                         | O(k²) per pass  | O(k)    |

`n` = parcels, `W` = capacity, `V`/`E` = graph size, `k` = stops on the trip.

## 4. How the pieces work together

```
            dataset.json
                 │
                 ▼
     ┌───────────────────────┐
     │ 1. Merge Sort parcels │  key = (deadline ↑, priority ↓, value ↓)
     └───────────┬───────────┘
                 ▼
     ┌───────────────────────┐
     │ 2. 0/1 Knapsack (DP)  │  maximise Σ value  s.t.  Σ weight ≤ capacity
     └───────────┬───────────┘
                 │  selected parcels → set of stops
                 ▼
     ┌───────────────────────┐
     │ 3. Dijkstra from the  │  depot + every stop → distance matrix
     │    depot and each stop│  + predecessor maps for real road paths
     └───────────┬───────────┘
                 ▼
     ┌───────────────────────┐
     │ 4. Nearest-Neighbour  │  closed tour depot → … → depot
     │    TSP (+ 2-opt)      │
     └───────────┬───────────┘
                 ▼
     route sequence, road-level path, total km, packing plan, timings
```

### Route-planning logic

1. Collect the distinct destinations of the selected parcels (several parcels can go to one stop).
2. Run Dijkstra once from the depot and once from each stop. This turns the sparse road graph into a
   small **complete** graph (metric closure) over only the points we must visit.
3. Run nearest-neighbour on that complete graph: from the current point always drive to the closest
   unvisited stop; finally return to the depot.
4. Expand every leg of the tour back into its real road path using Dijkstra's predecessor map,
   and sum the leg distances for the total route length.

### Why sorting is still useful after the DP

The knapsack decides *which* parcels travel, but the sorted order is used to:
- present parcels to the dispatcher in urgency order,
- break ties consistently (the DP scans parcels in sorted order),
- flag parcels left behind that are urgent (candidates for the next trip).

## 5. Suitability summary

- Every algorithm runs in polynomial time and scales to hundreds of parcels and nodes.
- The only exponential sub-problem (TSP) is handled by an approximation, as required.
- Each stage is a separate module, so it can be timed and replaced independently in Phase 4.
