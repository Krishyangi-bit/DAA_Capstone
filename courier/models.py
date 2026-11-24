"""
Data models and dataset loading for the Mini-Courier Planner.

A dataset is a JSON file with a depot, van capacity, graph nodes,
graph edges (roads) and parcels. See docs/design.md for the format.
"""

import json
from dataclasses import dataclass, asdict


@dataclass
class Parcel:
    """One parcel waiting at the depot."""
    id: str
    destination: str   # node id in the graph
    weight: int        # kg (integer so it can index the DP table)
    value: int         # business value of delivering it on this trip
    deadline: int      # hours from dispatch
    priority: int      # 1 (low) .. 5 (express)

    def sort_key(self):
        """
        Key used to prioritise parcels:
        earliest deadline first, then higher priority, then higher value.
        Priority and value are negated so that a plain ascending comparison works.
        """
        return (self.deadline, -self.priority, -self.value)

    def to_dict(self):
        return asdict(self)


@dataclass
class Node:
    """A delivery point (or the depot) on the map."""
    id: str
    name: str
    x: float
    y: float

    def to_dict(self):
        return asdict(self)


@dataclass
class Dataset:
    """Everything the planner needs for one run."""
    name: str
    depot: str
    capacity: int
    nodes: list          # list[Node]
    edges: list          # list[tuple[str, str, float]]
    parcels: list        # list[Parcel]


def validate(data):
    """
    Basic sanity checks so that bad input fails early with a clear message
    instead of crashing deep inside an algorithm.
    """
    required = ["depot", "capacity", "nodes", "edges", "parcels"]
    for key in required:
        if key not in data:
            raise ValueError(f"Dataset is missing the '{key}' field")

    node_ids = {n["id"] for n in data["nodes"]}
    if data["depot"] not in node_ids:
        raise ValueError(f"Depot '{data['depot']}' is not a node")

    for e in data["edges"]:
        if e["from"] not in node_ids or e["to"] not in node_ids:
            raise ValueError(f"Edge {e} refers to an unknown node")
        if float(e["distance"]) < 0:
            raise ValueError(f"Edge {e} has a negative distance (Dijkstra needs >= 0)")

    for p in data["parcels"]:
        if p["destination"] not in node_ids:
            raise ValueError(f"Parcel {p['id']} goes to unknown node '{p['destination']}'")
        if int(p["weight"]) <= 0:
            raise ValueError(f"Parcel {p['id']} must have a positive weight")

    if int(data["capacity"]) <= 0:
        raise ValueError("Capacity must be a positive integer")


def from_dict(data):
    """Build a Dataset object from an already-parsed JSON dictionary."""
    validate(data)
    nodes = [Node(n["id"], n.get("name", n["id"]), float(n["x"]), float(n["y"]))
             for n in data["nodes"]]
    edges = [(e["from"], e["to"], float(e["distance"])) for e in data["edges"]]
    parcels = [Parcel(p["id"], p["destination"], int(p["weight"]), int(p["value"]),
                      int(p["deadline"]), int(p["priority"]))
               for p in data["parcels"]]
    return Dataset(data.get("name", "custom"), data["depot"], int(data["capacity"]),
                   nodes, edges, parcels)


def load_dataset(path):
    """Read a dataset JSON file from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return from_dict(json.load(f))
