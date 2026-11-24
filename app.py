"""
Mini-Courier Planner — web interface (Flask).

    pip install -r requirements.txt
    python app.py              -> open http://127.0.0.1:5000

Pages
    /             planner: pick a dataset (or upload JSON), run the pipeline, see results
    /performance  Phase 4 benchmark charts and tables
    /design       Phase 1 design: data model and algorithm choices
    /api/plan     JSON version of the planner (POST a dataset or GET ?dataset=small)
"""

import json
import os

from flask import Flask, jsonify, render_template, request, send_from_directory

from courier.models import from_dict
from courier.planner import plan_delivery
from courier.sorting import ALGORITHMS

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SAMPLES = ["small", "medium", "large"]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024      # uploads up to 2 MB


def read_sample(name):
    with open(os.path.join(DATA_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def map_geometry(raw, result):
    """
    Pre-compute everything the SVG map needs so the template stays simple.
    Coordinates are scaled into a 0..1000 x 0..640 viewBox.
    """
    xs = [n["x"] for n in raw["nodes"]]
    ys = [n["y"] for n in raw["nodes"]]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    W, H, pad = 1000, 640, 40

    def sx(x):
        return pad + (x - min_x) / ((max_x - min_x) or 1) * (W - 2 * pad)

    def sy(y):
        return pad + (y - min_y) / ((max_y - min_y) or 1) * (H - 2 * pad)

    pos = {n["id"]: (round(sx(n["x"]), 1), round(sy(n["y"]), 1)) for n in raw["nodes"]}
    names = {n["id"]: n.get("name", n["id"]) for n in raw["nodes"]}
    order = {stop: i for i, stop in enumerate(result["tour"][1:-1], 1)}

    nodes = []
    for nid, (x, y) in pos.items():
        kind = "depot" if nid == raw["depot"] else ("stop" if nid in order else "other")
        anchor = "end" if x > W * 0.8 else "start"     # keep labels inside the map
        nodes.append({"id": nid, "name": names[nid], "x": x, "y": y, "kind": kind, "anchor": anchor,
                      "order": order.get(nid), "drops": result["drops"].get(nid, [])})

    route_edges = {frozenset(p) for p in zip(result["full_path"], result["full_path"][1:])}
    edges = [{"x1": pos[e["from"]][0], "y1": pos[e["from"]][1],
              "x2": pos[e["to"]][0], "y2": pos[e["to"]][1],
              "on_route": frozenset((e["from"], e["to"])) in route_edges}
             for e in raw["edges"]]
    route = " ".join(f"{pos[n][0]},{pos[n][1]}" for n in result["full_path"])
    return {"w": W, "h": H, "nodes": nodes, "edges": edges, "route": route,
            "small": len(nodes) <= 20}


def dp_view(result, max_cols=26, max_rows=24):
    """A readable slice of the DP table (all of it for the small dataset)."""
    table = result["packing"]["table"]
    parcels = result["sorted_parcels"]
    W = len(table[0]) - 1
    step = 1 if W <= max_cols else -(-W // max_cols)         # ceil division
    cols = list(range(0, W + 1, step))
    if cols[-1] != W:
        cols.append(W)
    rows = [{"label": "—", "cells": [table[0][w] for w in cols]}]
    picked = {p.id for p in result["packing"]["selected"]}
    for i, p in enumerate(parcels[:max_rows], 1):
        rows.append({"label": p.id, "taken": p.id in picked,
                     "cells": [table[i][w] for w in cols]})
    return {"cols": cols, "rows": rows, "full": step == 1 and len(parcels) <= max_rows,
            "total_rows": len(parcels)}


@app.route("/", methods=["GET", "POST"])
def index():
    form = {"dataset": "small", "capacity": "", "sort": "merge", "two_opt": True}
    error = None
    raw = None

    if request.method == "POST":
        form["dataset"] = request.form.get("dataset", "small")
        form["capacity"] = request.form.get("capacity", "").strip()
        form["sort"] = request.form.get("sort", "merge")
        form["two_opt"] = request.form.get("two_opt") == "on"
        upload = request.files.get("upload")
        try:
            if upload and upload.filename:
                raw = json.load(upload.stream)
                form["dataset"] = "upload"
            else:
                raw = read_sample(form["dataset"] if form["dataset"] in SAMPLES else "small")
        except (ValueError, UnicodeDecodeError) as exc:
            error = f"Could not read the uploaded file: {exc}"
    else:
        # GET links such as /?dataset=large&sort=quick&capacity=80 are shareable
        name = request.args.get("dataset", "small")
        form["dataset"] = name if name in SAMPLES else "small"
        form["capacity"] = request.args.get("capacity", "").strip()
        form["sort"] = request.args.get("sort", "merge")
        form["two_opt"] = request.args.get("two_opt", "on") != "off"
        raw = read_sample(form["dataset"])

    context = {"form": form, "samples": SAMPLES, "sorts": list(ALGORITHMS), "error": error}
    if raw is not None and error is None:
        try:
            ds = from_dict(raw)
            capacity = int(form["capacity"]) if form["capacity"] else None
            if capacity is not None and not 1 <= capacity <= 5000:
                raise ValueError("Capacity must be between 1 and 5000 kg")
            sort = form["sort"] if form["sort"] in ALGORITHMS else "merge"
            result = plan_delivery(ds, capacity, sort, use_two_opt=form["two_opt"])
            selected_ids = {p.id for p in result["packing"]["selected"]}
            context.update(ds=ds, r=result, selected_ids=selected_ids,
                           geo=map_geometry(raw, result), dp=dp_view(result),
                           names={n.id: n.name for n in ds.nodes})
        except (ValueError, KeyError, TypeError) as exc:
            context["error"] = f"Invalid dataset: {exc}"
    return render_template("index.html", **context)


@app.route("/performance")
def performance():
    path = os.path.join(ROOT, "results", "benchmark.json")
    bench = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            bench = json.load(f)
    return render_template("performance.html", b=bench)


@app.route("/design")
def design():
    return render_template("design.html")


@app.route("/charts/<path:name>")
def charts(name):
    return send_from_directory(os.path.join(ROOT, "docs", "charts"), name)


@app.route("/data/<name>.json")
def download_sample(name):
    if name not in SAMPLES:
        return "Not found", 404
    return send_from_directory(DATA_DIR, f"{name}.json", as_attachment=True)


@app.route("/api/plan", methods=["GET", "POST"])
def api_plan():
    try:
        raw = request.get_json(force=True) if request.method == "POST" \
            else read_sample(request.args.get("dataset", "small"))
        r = plan_delivery(from_dict(raw))
    except Exception as exc:                                  # report any input problem
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "selected": [p.id for p in r["packing"]["selected"]],
        "total_value": r["packing"]["total_value"],
        "total_weight": r["packing"]["total_weight"],
        "tour": r["tour"],
        "route_length": r["route_length"],
        "full_path": r["full_path"],
        "timings_ms": r["timings_ms"],
    })


if __name__ == "__main__":
    app.run(debug=True)
