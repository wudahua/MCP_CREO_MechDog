"""Geometric preflight for consumers requiring a single closed sketch contour.

Sketch creation itself permits open geometry. Explicit dimensions/constraints
can alter endpoints; their final topology must be checked by the native kernel.
"""

from __future__ import annotations

import math


def closed_profile(entities: list[dict], tolerance: float = 0.0001) -> dict:
    endpoints = []
    edges = []
    standalone = 0
    for entity in entities:
        if entity.get("construction") or entity["type"] == "centerline":
            continue
        kind = entity["type"]
        if kind in ("circle", "ellipse") or (kind == "spline" and entity.get("closed")):
            standalone += 1
            continue
        if kind == "rectangle":
            a, b = entity["min"], entity["max"]
            points = [a, [b[0], a[1]], b, [a[0], b[1]], a]
        elif kind == "polyline":
            points = entity["points"] + ([entity["points"][0]] if entity.get("closed") else [])
        elif kind == "line":
            points = [entity["start"], entity["end"]]
        elif kind == "spline":
            points = [entity["points"][0], entity["points"][-1]]
        elif kind == "b_spline":
            # FEAT-066: a clamped B-spline interpolates its first and last
            # control point; knots/weights only shape the interior.
            points = [entity["control_points"][0], entity["control_points"][-1]]
        elif kind == "arc":
            cx, cy = entity["center"]
            points = [
                [
                    cx + entity["radius"] * math.cos(math.radians(entity[key])),
                    cy + entity["radius"] * math.sin(math.radians(entity[key])),
                ]
                for key in ("start_angle", "end_angle")
            ]
        else:
            raise ValueError(f"Unsupported contour entity: {kind}")
        for a, b in zip(points, points[1:]):
            edges.append((len(endpoints), len(endpoints) + 1))
            endpoints.extend([a, b])
    parent = list(range(len(endpoints)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cells = {}
    for i, p in enumerate(endpoints):
        cell = tuple(math.floor(v / tolerance) for v in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cells.get((cell[0] + dx, cell[1] + dy), []):
                    if math.dist(p, endpoints[j]) <= tolerance:
                        parent[find(i)] = find(j)
        cells.setdefault(cell, []).append(i)
    adjacency = {}
    for a, b in edges:
        a, b = find(a), find(b)
        if a == b:
            raise ValueError("Contour has an edge shorter than the closure tolerance")
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    invalid = [node for node, neighbors in adjacency.items() if len(neighbors) != 2]
    if invalid:
        point = endpoints[invalid[0]]
        raise ValueError(
            f"Profile is open or branched near {point}; connect endpoints within {tolerance:g} mm"
        )
    visited = set()
    contours = standalone
    for node in adjacency:
        if node in visited:
            continue
        contours += 1
        stack = [node]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency[current])
    if contours != 1:
        raise ValueError(f"Ordinary solid Blend requires one closed contour; found {contours}")
    return {"closed_contour_count": contours, "closure_tolerance_mm": tolerance}
