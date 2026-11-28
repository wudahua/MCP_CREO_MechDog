"""FEAT-039/W01: the endpoint weld contract, policy layer.

Python plans native coordinate regularisation and reports measured pair counts.
Explicit snap_endpoints may rewrite request coordinates within the supplied bound.

The endpoint view is the one the profile diagnostics already use: the curves
come from :mod:`creo_mechdog.profile_diagnostics`, so this module adds no
parallel gap diagnostics. Two scales stay apart:

* ``CLUSTER_TOLERANCE_MM`` (1e-4 mm) is the closure-diagnostic scale: two
  endpoints that close at that distance are candidates for one weld;
* ``EXACT_TOLERANCE_MM`` (1e-9 mm) is the published native sketch epsilon, the
  only existing constant between the two observations of BUG-101 (an 8.215e-7
  mm gap was welded by the kernel, a 7.83e-13 mm gap was welded too). Neither
  number is the calibrated weld threshold for a pair; that stays open and the
  receipt says which source it used.

Rules, in the order they are applied:

1. a candidate pair is two endpoints of *different* curves within the cluster
   tolerance;
2. an endpoint belongs to at most one accepted pair (smallest gap wins, a tie
   is ambiguous and is refused instead of being resolved arbitrarily);
3. a pair may not bridge two chains: welding the ends of one open chain closes
   it, welding two different chains would merge two contours;
4. two arcs may only be welded when they live on the same circle (centre and radius
   agree) and both carry a real sweep; at the cluster tolerance this is already
   implied by the endpoints meeting, so it stays a guard against a geometry that
   would change the arc;
5. the symmetric move each endpoint would need is gap/2, and a request may
   cap it with ``max_move_mm``.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from creo_mechdog.profile_diagnostics import (
    EXACT_TOLERANCE_MM,
    KERNEL_COINCIDENT_TOLERANCE_MM,
    _expand,
)

POLICIES = ("report", "reject", "weld")
SAMPLE_LIMIT = 20
# The closure-diagnostic scale (1e-4 mm) already published for contour
# closure; it decides which endpoints may be considered one point, not whether
# the kernel welds them.
CLUSTER_TOLERANCE_MM = 1e-4
# The weld plan handed to the native side is bounded like every other receipt field.
WELD_PLAN_LIMIT = 200
# The 2026-10-31 feedback: the kernel welded an 8.215e-7 mm gap on Creo 12.4,
# so the 1e-9 mm bound is a risk flag, never a guarantee.
OBSERVED_KERNEL_WELD_MM = 8.21534267e-7
# BUG-159: joins at or below this are already one point for this policy layer.
# The 2026-11-22 feedback submitted a 40-arc contour whose endpoint residuals
# were 3.464e-8 and 4.727e-8 mm; treating them as weld candidates made
# arc_inconsistent refuse a contour the kernel already merges (it welded the
# larger 8.215e-7 mm gap above on Creo 12.4). This is a classification
# tolerance, not permission to move an endpoint. The admission gate in
# profile_diagnostics reads the same constant.
ARC_COINCIDENT_TOLERANCE_MM = KERNEL_COINCIDENT_TOLERANCE_MM


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.dist(a, b)


def _endpoints(curves: list) -> list[dict]:
    """Every weldable endpoint of the expanded profile, in a stable order."""
    ends: list[dict] = []
    for index, curve in enumerate(curves):
        if curve.kind not in ("line", "arc"):
            continue
        if curve.start is None or curve.end is None:
            continue
        ends.append({"curve": index, "end": "start", "point": curve.start})
        ends.append({"curve": index, "end": "end", "point": curve.end})
    return ends


def _chains(curves: list, ends: list[dict], tolerance: float) -> dict[int, int]:
    """Group curves into chains by exactly coincident endpoints.

    The mapping is curve index -> chain id. Two curves are chained when one of
    their endpoints coincides within the strict tolerance, so a chain is an
    open chain of curves and a closed contour is a chain whose two ends meet.
    """
    parent = list(range(len(curves)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for i, first in enumerate(ends):
        for second in ends[i + 1 :]:
            if first["curve"] == second["curve"]:
                continue
            if _distance(first["point"], second["point"]) <= tolerance:
                union(first["curve"], second["curve"])
    return {index: find(index) for index in range(len(curves))}


def _arc_consistent(first, second, tolerance: float) -> bool:
    if first.kind != "arc" or second.kind != "arc":
        return True
    if first.center is None or second.center is None:
        return False
    if _distance(first.center, second.center) > tolerance:
        return False
    if abs(first.radius - second.radius) > tolerance:
        return False
    # The sweeps stay as they are: the policy layer never rewrites an arc, it
    # only checks that both arcs live on the same circle, so welding their ends
    # keeps one consistent arc geometry.
    return abs(first.sweep) > 0.0 and abs(second.sweep) > 0.0


def _effective_cluster_tolerance(cluster_tolerance_mm: float | None) -> tuple[float, str]:
    if cluster_tolerance_mm is None:
        return CLUSTER_TOLERANCE_MM, "closure_diagnostic_cluster"
    if isinstance(cluster_tolerance_mm, bool) or not isinstance(cluster_tolerance_mm, (int, float)):
        raise ValueError("closure_tolerance_mm must be a finite positive number of millimeters")
    value = float(cluster_tolerance_mm)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("closure_tolerance_mm must be a finite positive number of millimeters")
    return value, "closure_tolerance_mm"


def _plan(
    entities: list[dict[str, Any]],
    max_move_mm: float | None,
    cluster_tolerance_mm: float | None = None,
    *,
    min_gap_mm: float = ARC_COINCIDENT_TOLERANCE_MM,
) -> tuple[list, list[dict], list[dict], list[dict]]:
    """The shared candidate/accepted/refused decision used by every entry."""
    tolerance, _source = _effective_cluster_tolerance(cluster_tolerance_mm)
    curves, _names = _expand(entities)
    ends = _endpoints(curves)
    # BUG-159: chain through the same near-coincident tolerance used below. With
    # the old 1e-9 exact union each 3.5e-8 mm joint split the contour into a
    # separate chain, so adjacent arcs looked like separate loops.
    chain_of = _chains(curves, ends, min_gap_mm)

    candidates: list[dict] = []
    for i, first in enumerate(ends):
        for second in ends[i + 1 :]:
            if first["curve"] == second["curve"]:
                continue
            gap = _distance(first["point"], second["point"])
            # A candidate is a pair inside the closure diagnostic scale. The
            # 2026-11-05 live measurement showed the sketch epsilon is not the
            # coincidence tolerance, so a bound alone cannot widen this.
            if gap <= min_gap_mm or gap > tolerance:
                # An exact or near-coincident join is already one point, not a
                # candidate weld.
                continue
            candidates.append(
                {
                    "curve_a": first["curve"],
                    "curve_b": second["curve"],
                    "end_a": first["end"],
                    "end_b": second["end"],
                    "gap_mm": gap,
                    "required_move_mm": gap / 2.0,
                    "entity_a": curves[first["curve"]].name,
                    "entity_b": curves[second["curve"]].name,
                    "same_chain": chain_of[first["curve"]] == chain_of[second["curve"]],
                    "arc_consistent": _arc_consistent(
                        curves[first["curve"]], curves[second["curve"]], tolerance
                    ),
                }
            )
    candidates.sort(key=lambda entry: (entry["gap_mm"], entry["curve_a"], entry["curve_b"]))

    accepted: list[dict] = []
    refused: list[dict] = []
    used: dict[tuple[int, str], str] = {}
    for candidate in candidates:
        key_a = (candidate["curve_a"], candidate["end_a"])
        key_b = (candidate["curve_b"], candidate["end_b"])
        reason = None
        if not candidate["same_chain"]:
            reason = "separate_loops"
        elif not candidate["arc_consistent"]:
            reason = "arc_inconsistent"
        elif max_move_mm is not None and candidate["required_move_mm"] > max_move_mm:
            reason = "max_move_exceeded"
        elif key_a in used or key_b in used:
            reason = "ambiguous_pair"
        if reason is not None:
            refused.append({**candidate, "reason": reason})
            continue
        used[key_a] = key_b
        used[key_b] = key_a
        accepted.append(candidate)
    return curves, candidates, accepted, refused


def _entity_named(entities: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for entity in entities:
        if entity.get("type") in ("line", "arc") and str(entity.get("name")) == name:
            return entity
    return None


#: Reasons the policy layer can prove it cannot deliver: moving the endpoint
#: would change the geometry the caller described, or the caller's own bound
#: forbids the move. These refuse the plan instead of being reported as advice.
BLOCKING_REASONS = (
    "arc_inconsistent",
    "max_move_exceeded",
    "unsupported_entity",
    "would_merge_closed_contours",
)
#: Reasons only the kernel can settle: a join wider than the exact chain union
#: between two *open* chains is a closure the native solver may or may not make.
UNRESOLVED_REASONS = ("separate_loops",)


def _closed_chains(ends: list[dict], chain_of: dict[int, int]) -> dict[int, bool]:
    """Which chains already close on themselves (every endpoint is shared)."""
    points: dict[int, list[tuple[float, float]]] = {}
    for entry in ends:
        points.setdefault(chain_of[entry["curve"]], []).append(entry["point"])
    closed: dict[int, bool] = {}
    for chain, positions in points.items():
        open_ends = 0
        for index, point in enumerate(positions):
            shared = any(
                index != other and _distance(point, neighbour) <= ARC_COINCIDENT_TOLERANCE_MM
                for other, neighbour in enumerate(positions)
            )
            if not shared:
                open_ends += 1
        closed[chain] = open_ends == 0 and len(positions) >= 2
    return closed


def weld_eligibility(
    entities: list[dict[str, Any]],
    max_move_mm: float | None = None,
    cluster_tolerance_mm: float | None = None,
) -> dict[str, Any]:
    """Whether the policy layer can actually deliver what weld/snap promise.

    This is the single qualification shared by the admission message
    (``profile_diagnostics.validate_solid_profile``) and the submission gate
    (``prepare_operations``). Being inside ``CLUSTER_TOLERANCE_MM`` (or an
    explicit ``closure_tolerance_mm``) only makes a pair a *candidate*; a pair
    is blocked when welding it would move an arc off its circle, exceed the
    caller's bound, or bridge an already closed contour. A join between two open
    chains stays ``unresolved``: the exact chain union cannot prove it, so the
    kernel owns the answer.
    """
    tolerance, _source = _effective_cluster_tolerance(cluster_tolerance_mm)
    curves, _candidates, accepted, refused = _plan(entities, max_move_mm, cluster_tolerance_mm)
    ends = _endpoints(curves)
    chain_of = _chains(curves, ends, ARC_COINCIDENT_TOLERANCE_MM)
    closed = _closed_chains(ends, chain_of)
    blocking: list[dict] = []
    unresolved: list[dict] = []
    resolved_by_nearest: list[dict] = []
    for pair in refused:
        reason = pair["reason"]
        if not pair.get("arc_consistent", True):
            # Two arcs that are not on one circle cannot be welded without
            # moving an endpoint off its circle, whatever the chain topology
            # says; the pair is refused for geometry, not for topology.
            blocking.append({**pair, "reason": "arc_inconsistent"})
        elif reason == "separate_loops":
            if closed.get(chain_of[pair["curve_a"]], False) or closed.get(
                chain_of[pair["curve_b"]], False
            ):
                blocking.append(
                    {
                        **pair,
                        "reason": "would_merge_closed_contours",
                        "reason_detail": (
                            "welding would bridge a contour that is already closed; the two "
                            "rings must stay separate"
                        ),
                    }
                )
            else:
                unresolved.append(pair)
        elif reason == "ambiguous_pair":
            # The endpoint is welded, just to the closer partner; not a refusal.
            resolved_by_nearest.append(pair)
        elif reason in BLOCKING_REASONS:
            blocking.append(pair)
        else:
            unresolved.append(pair)
    if blocking:
        verdict = "blocked"
    elif unresolved:
        verdict = "unresolved"
    elif accepted:
        verdict = "weldable"
    else:
        verdict = "not_needed"
    moves = [pair["required_move_mm"] for pair in accepted]
    return {
        "verdict": verdict,
        "threshold_mm": tolerance,
        "candidate_pairs": len(accepted) + len(refused),
        "accepted_pairs": len(accepted),
        "blocking_pairs": len(blocking),
        "unresolved_pairs": len(unresolved),
        "resolved_by_nearest_pairs": len(resolved_by_nearest),
        "max_required_move_mm": max(moves) if moves else None,
        "max_move_mm": max_move_mm,
        "blocking": blocking[:SAMPLE_LIMIT],
        "unresolved": unresolved[:SAMPLE_LIMIT],
    }


def _pair_line(pair: dict) -> str:
    return (
        f"{pair.get('entity_a')}/{pair.get('entity_b')} gap {pair.get('gap_mm'):.3e} mm "
        f"({pair.get('reason')})"
    )


def eligibility_summary(eligibility: dict[str, Any]) -> str:
    """One sentence the caller can act on, derived from ``weld_eligibility``."""
    verdict = eligibility.get("verdict")
    if verdict == "blocked":
        reasons = sorted({pair["reason"] for pair in eligibility["blocking"]})
        sample = "; ".join(_pair_line(pair) for pair in eligibility["blocking"][:3])
        return (
            "Weld/snap cannot fix this profile: "
            f"{eligibility['blocking_pairs']} join(s) are refused for {reasons} ({sample}). "
            "Correct the geometry - both arcs on one circle, a bound that allows the move, or "
            "separate contours - instead of relying on endpoint welding."
        )
    if verdict == "unresolved":
        widest = max(pair["gap_mm"] for pair in eligibility["unresolved"])
        return (
            f"{eligibility['unresolved_pairs']} join(s) up to {widest:.3e} mm sit between two "
            f"open chains; the {EXACT_TOLERANCE_MM:.0e} mm chain union cannot prove the weld, so "
            "only endpoint_policy='weld' plus the kernel can settle it - check the job result "
            "before treating the contour as closed."
        )
    if verdict == "weldable":
        move = eligibility["max_required_move_mm"]
        return (
            f"All {eligibility['accepted_pairs']} near join(s) are weldable (largest move "
            f"{move:.3e} mm per endpoint); endpoint_policy='weld' or snap_endpoints=true can "
            "close them at submission."
        )
    return (
        f"No candidate join exists inside the {CLUSTER_TOLERANCE_MM:.0e} mm diagnostic scale, so "
        "welding cannot close this profile: the contour is structurally open (missing edge) or "
        "the seam is wider than the diagnostic scale."
    )


def _arc_current_geom(entity: dict[str, Any]) -> dict[str, Any]:
    """Read an arc entity's current (possibly already mutated) geometry."""
    cx, cy = float(entity["center"][0]), float(entity["center"][1])
    radius = float(entity["radius"])
    start_deg = float(entity["start_angle"])
    direction = int(entity.get("dir", 1))
    if entity.get("end_angle") is not None:
        end_deg = float(entity["end_angle"])
        if direction >= 0:
            sweep = (end_deg - start_deg) % 360.0
            if sweep <= 1e-12:
                sweep = 360.0
        else:
            sweep = -((start_deg - end_deg) % 360.0)
            if sweep >= -1e-12:
                sweep = -360.0
    else:
        sweep = float(entity["sweep_deg"])
        end_deg = start_deg + sweep
        direction = 1 if sweep >= 0 else -1
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    mid_rad = math.radians(start_deg + sweep / 2.0)
    return {
        "center": (cx, cy),
        "radius": radius,
        "start_deg": start_deg,
        "end_deg": end_deg,
        "sweep_deg": sweep,
        "dir": direction,
        "start": (cx + radius * math.cos(start_rad), cy + radius * math.sin(start_rad)),
        "mid": (cx + radius * math.cos(mid_rad), cy + radius * math.sin(mid_rad)),
        "end": (cx + radius * math.cos(end_rad), cy + radius * math.sin(end_rad)),
    }


def _circle_intersections(
    c1: tuple[float, float], r1: float, c2: tuple[float, float], r2: float
) -> list[tuple[float, float]]:
    """Return 0, 1, or 2 real intersection points of two circles."""
    dx = c2[0] - c1[0]
    dy = c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if d <= 1e-15:
        return []
    if d > r1 + r2 + 1e-12 or d < abs(r1 - r2) - 1e-12:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h_sq = r1 * r1 - a * a
    if h_sq < -1e-12:
        return []
    h = math.sqrt(max(0.0, h_sq))
    px = c1[0] + a * dx / d
    py = c1[1] + a * dy / d
    if h <= 1e-15:
        return [(px, py)]
    rx = -dy * (h / d)
    ry = dx * (h / d)
    return [(px + rx, py + ry), (px - rx, py - ry)]


def _circumcircle(
    p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]
) -> tuple[tuple[float, float], float] | None:
    """Unique circle through three non-collinear 2D points, or None if degenerate."""
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) <= 1e-18:
        return None
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    if not (math.isfinite(ux) and math.isfinite(uy)):
        return None
    radius = math.hypot(ax - ux, ay - uy)
    if not math.isfinite(radius) or radius <= 0.0:
        return None
    return (ux, uy), radius


def _write_arc_angles(
    entity: dict[str, Any],
    center: tuple[float, float],
    radius: float,
    start_pt: tuple[float, float],
    mid_pt: tuple[float, float],
    end_pt: tuple[float, float],
) -> None:
    """Update an arc entity's center, radius, and angles to pass through start->mid->end."""
    cx, cy = center
    a_start = math.degrees(math.atan2(start_pt[1] - cy, start_pt[0] - cx)) % 360.0
    a_mid = math.degrees(math.atan2(mid_pt[1] - cy, mid_pt[0] - cx)) % 360.0
    a_end = math.degrees(math.atan2(end_pt[1] - cy, end_pt[0] - cx)) % 360.0
    ccw_end = (a_end - a_start) % 360.0
    ccw_mid = (a_mid - a_start) % 360.0
    direction = 1 if (0.0 < ccw_mid < ccw_end) else -1
    entity["center"] = [cx, cy]
    entity["radius"] = radius
    entity["start_angle"] = a_start
    entity["dir"] = direction
    if "sweep_deg" in entity and entity.get("end_angle") is None:
        sweep = ccw_end if direction == 1 else -((a_start - a_end) % 360.0)
        entity["sweep_deg"] = sweep
    else:
        entity["end_angle"] = a_end


def _snap_arc_endpoint_only_angle(
    entity: dict[str, Any], end_key: str, target: tuple[float, float]
) -> None:
    """Move one arc endpoint to target (already on the arc's circle) by updating only its angle."""
    geom = _arc_current_geom(entity)
    cx, cy = geom["center"]
    new_deg = math.degrees(math.atan2(target[1] - cy, target[0] - cx)) % 360.0
    if end_key == "start":
        entity["start_angle"] = new_deg
    else:
        if "sweep_deg" in entity and entity.get("end_angle") is None:
            start_deg = float(entity["start_angle"])
            if geom["dir"] >= 0:
                sweep = (new_deg - start_deg) % 360.0
            else:
                sweep = -((start_deg - new_deg) % 360.0)
            entity["sweep_deg"] = sweep
        else:
            entity["end_angle"] = new_deg


def _snap_arc_pair(
    entity_a: dict[str, Any],
    end_a: str,
    entity_b: dict[str, Any],
    end_b: str,
    bound: float,
) -> tuple[dict[str, Any] | None, str | None]:
    """FEAT-090: snap two arcs to a shared point within bound.

    1. Same circle -> angle-only midpoint on circle (zero radius delta).
    2. Intersecting circles within bound -> angle-only snap to intersection (zero radius delta).
    3. Non-intersecting near-tangent arcs -> 3-point circumcircle snap to midpoint within bound.
    """
    ga = _arc_current_geom(entity_a)
    gb = _arc_current_geom(entity_b)
    pa = ga["start"] if end_a == "start" else ga["end"]
    pb = gb["start"] if end_b == "start" else gb["end"]
    gap = _distance(pa, pb)
    mid = ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)

    # 1. Same circle: project midpoint onto shared circle, angle-only update.
    if _distance(ga["center"], gb["center"]) <= 1e-9 and abs(ga["radius"] - gb["radius"]) <= 1e-9:
        cx, cy = ga["center"]
        dm = math.hypot(mid[0] - cx, mid[1] - cy)
        if dm <= 1e-15:
            return None, "arc_snap_degenerate"
        target = (cx + ga["radius"] * (mid[0] - cx) / dm, cy + ga["radius"] * (mid[1] - cy) / dm)
        shift_a, shift_b = _distance(pa, target), _distance(pb, target)
        if max(shift_a, shift_b) > bound:
            return None, "arc_snap_out_of_bound"
        _snap_arc_endpoint_only_angle(entity_a, end_a, target)
        _snap_arc_endpoint_only_angle(entity_b, end_b, target)
        return {
            "anchor": "arc_same_circle",
            "point": [target[0], target[1]],
            "shift_a_mm": shift_a,
            "shift_b_mm": shift_b,
            "radius_delta_a_mm": 0.0,
            "radius_delta_b_mm": 0.0,
            "gap_mm": gap,
        }, None

    # 2. Intersecting different circles: angle-only update if intersection is within bound.
    intersections = _circle_intersections(ga["center"], ga["radius"], gb["center"], gb["radius"])
    if intersections:
        best = min(intersections, key=lambda pt: _distance(pt, mid))
        shift_a, shift_b = _distance(pa, best), _distance(pb, best)
        if max(shift_a, shift_b) <= bound:
            _snap_arc_endpoint_only_angle(entity_a, end_a, best)
            _snap_arc_endpoint_only_angle(entity_b, end_b, best)
            return {
                "anchor": "arc_intersection",
                "point": [best[0], best[1]],
                "shift_a_mm": shift_a,
                "shift_b_mm": shift_b,
                "radius_delta_a_mm": 0.0,
                "radius_delta_b_mm": 0.0,
                "gap_mm": gap,
            }, None

    # 3. Near-tangent / micro-gap non-intersecting circles: 3-point circumcircle through midpoint.
    target = mid
    shift_a, shift_b = _distance(pa, target), _distance(pb, target)
    if max(shift_a, shift_b) > bound:
        return None, "arc_snap_out_of_bound"
    qa = ga["end"] if end_a == "start" else ga["start"]
    qb = gb["end"] if end_b == "start" else gb["start"]
    ca = _circumcircle(
        target if end_a == "start" else qa, ga["mid"], qa if end_a == "start" else target
    )
    cb = _circumcircle(
        target if end_b == "start" else qb, gb["mid"], qb if end_b == "start" else target
    )
    if ca is None or cb is None:
        return None, "arc_snap_degenerate"
    (cax, cay), ra_new = ca
    (cbx, cby), rb_new = cb
    da_r = abs(ra_new - ga["radius"])
    db_r = abs(rb_new - gb["radius"])
    radius_limit = max(1e-3, 1000.0 * max(gap, bound))
    if max(da_r, db_r) > radius_limit:
        return None, "arc_snap_radius_drift_exceeded"
    _write_arc_angles(
        entity_a,
        (cax, cay),
        ra_new,
        target if end_a == "start" else qa,
        ga["mid"],
        qa if end_a == "start" else target,
    )
    _write_arc_angles(
        entity_b,
        (cbx, cby),
        rb_new,
        target if end_b == "start" else qb,
        gb["mid"],
        qb if end_b == "start" else target,
    )
    return {
        "anchor": "arc_three_point",
        "point": [target[0], target[1]],
        "shift_a_mm": shift_a,
        "shift_b_mm": shift_b,
        "radius_delta_a_mm": da_r,
        "radius_delta_b_mm": db_r,
        "gap_mm": gap,
    }, None


def _snap_entities(
    entities: list[dict[str, Any]],
    curves: list,
    accepted: list[dict],
    *,
    max_move_mm: float | None = None,
    tolerance_mm: float = CLUSTER_TOLERANCE_MM,
) -> tuple[list[dict[str, Any]], list[dict], str | None]:
    """Rewrite accepted line and arc endpoints to one shared point (FEAT-090).

    Two lines meet at the midpoint. A line-arc pair anchors the line to the arc's
    current endpoint. Two arcs snap by angle-only intersection when available, or
    by bounded 3-point circumcircle refit through the midpoint. Expanded rectangle
    or polyline segments remain refused because the rewrite cannot address them.
    """
    result = copy.deepcopy(entities)
    applied: list[dict] = []
    effective_bound = max_move_mm if max_move_mm is not None else tolerance_mm
    for pair in accepted:
        first = curves[pair["curve_a"]]
        second = curves[pair["curve_b"]]
        entity_a = _entity_named(result, pair["entity_a"])
        entity_b = _entity_named(result, pair["entity_b"])
        if entity_a is None or entity_b is None:
            return result, applied, "entity_not_snappable"
        if first.kind == "arc" and second.kind == "arc":
            arc_res, err = _snap_arc_pair(
                entity_a, pair["end_a"], entity_b, pair["end_b"], effective_bound
            )
            if err is not None or arc_res is None:
                return result, applied, err or "arc_pair_not_snappable"
            applied.append(
                {
                    "entity_a": pair["entity_a"],
                    "entity_b": pair["entity_b"],
                    "end_a": pair["end_a"],
                    "end_b": pair["end_b"],
                    **arc_res,
                }
            )
            continue
        if first.kind == "arc":
            ga = _arc_current_geom(entity_a)
            point_a = ga["start"] if pair["end_a"] == "start" else ga["end"]
        else:
            raw_a = entity_a[pair["end_a"]]
            point_a = (float(raw_a[0]), float(raw_a[1]))
        if second.kind == "arc":
            gb = _arc_current_geom(entity_b)
            point_b = gb["start"] if pair["end_b"] == "start" else gb["end"]
        else:
            raw_b = entity_b[pair["end_b"]]
            point_b = (float(raw_b[0]), float(raw_b[1]))
        if first.kind == "arc":
            target, anchor = point_a, "a"
        elif second.kind == "arc":
            target, anchor = point_b, "b"
        else:
            target = ((point_a[0] + point_b[0]) / 2.0, (point_a[1] + point_b[1]) / 2.0)
            anchor = "midpoint"
        shift_a = _distance(point_a, target)
        shift_b = _distance(point_b, target)
        if first.kind != "arc":
            entity_a[pair["end_a"]] = [target[0], target[1]]
        if second.kind != "arc":
            entity_b[pair["end_b"]] = [target[0], target[1]]
        applied.append(
            {
                "entity_a": pair["entity_a"],
                "entity_b": pair["entity_b"],
                "end_a": pair["end_a"],
                "end_b": pair["end_b"],
                "gap_mm": pair["gap_mm"],
                "anchor": anchor,
                "shift_a_mm": shift_a,
                "shift_b_mm": shift_b,
                "point": [target[0], target[1]],
            }
        )
    return result, applied, None


def _open_chain_snap_pairs(
    curves: list,
    accepted: list[dict],
    refused: list[dict],
    max_move_mm: float | None,
    *,
    allow_arc_snap: bool = False,
    min_gap_mm: float = ARC_COINCIDENT_TOLERANCE_MM,
) -> list[dict]:
    """Select unambiguous open-chain pairs for explicit snap_endpoints requests.

    A profile with more than one micro-gap (for example several arc-line or
    arc-arc seams) splits into separate open chains under the exact union. When
    the caller explicitly requests ``snap_endpoints=True``, bridge open chains
    greedily by smallest gap while refusing any pair that touches an already
    closed contour or exceeds ``max_move_mm``.
    """
    ends = _endpoints(curves)
    chain_of = _chains(curves, ends, min_gap_mm)
    closed = _closed_chains(ends, chain_of)
    used: set[tuple[int, str]] = set()
    for pair in accepted:
        used.add((pair["curve_a"], pair["end_a"]))
        used.add((pair["curve_b"], pair["end_b"]))
    extra: list[dict] = []
    for pair in refused:
        reason = pair.get("reason")
        if reason == "arc_inconsistent":
            if not allow_arc_snap:
                continue
        elif reason == "separate_loops":
            if not allow_arc_snap and not pair.get("arc_consistent", True):
                continue
        else:
            continue
        if max_move_mm is not None and pair["required_move_mm"] > max_move_mm:
            continue
        if closed.get(chain_of[pair["curve_a"]], False) or closed.get(
            chain_of[pair["curve_b"]], False
        ):
            continue
        key_a = (pair["curve_a"], pair["end_a"])
        key_b = (pair["curve_b"], pair["end_b"])
        if key_a in used or key_b in used:
            continue
        used.add(key_a)
        used.add(key_b)
        extra.append(pair)
    return extra


def prepare_endpoint_weld(
    entities: list[dict[str, Any]],
    *,
    policy: str = "report",
    max_move_mm: float | None = None,
    snap: bool = False,
    cluster_tolerance_mm: float | None = None,
) -> dict[str, Any]:
    """Describe which endpoint pairs may be welded.

    With ``snap=False`` no geometry moves. With ``snap=True`` an accepted
    line-line pair meets at the midpoint and a line-arc pair moves the line to
    the arc endpoint; the rewritten copy is returned privately for submission
    and the published receipt records every pair, gap and shift. In both cases
    the native solver still owns its own coincidence check.

    The receipt is the frozen contract: policy, whether anything was applied,
    the threshold and its source, the candidate and accepted pair counts, the
    largest move the pairs would need, the failure reason and a bounded sample
    of the pairs. ``requested_geometry`` is what the caller sent; the actual
    geometry stays ``None`` until the native solver reports it.
    """
    if policy not in POLICIES:
        raise ValueError(f"endpoint_policy must be one of {', '.join(POLICIES)}")
    if max_move_mm is not None:
        if not isinstance(max_move_mm, (int, float)) or isinstance(max_move_mm, bool):
            raise ValueError("max_move_mm must be a number")
        if not math.isfinite(float(max_move_mm)) or max_move_mm <= 0.0:
            raise ValueError("max_move_mm must be a finite number greater than 0")
    tolerance, tolerance_source = _effective_cluster_tolerance(cluster_tolerance_mm)

    min_gap = EXACT_TOLERANCE_MM if snap else ARC_COINCIDENT_TOLERANCE_MM
    curves, candidates, accepted, refused = _plan(
        entities, max_move_mm, cluster_tolerance_mm, min_gap_mm=min_gap
    )

    receipt: dict[str, Any] = {
        "policy": policy,
        "applied": False,
        "applied_by": None,
        "native_applied": False,
        "threshold_mm": tolerance,
        "threshold_source": tolerance_source,
        "kernel_weld_bound_mm": EXACT_TOLERANCE_MM,
        "kernel_weld_bound_source": "creo_mechdog.profile_diagnostics.EXACT_TOLERANCE_MM",
        "observed_kernel_weld_mm": OBSERVED_KERNEL_WELD_MM,
        "candidate_pairs": len(candidates),
        "accepted_pairs": len(accepted),
        "welded_pairs": 0,
        "refused_pairs": len(refused),
        "max_move_mm": None,
        "max_residual_mm": None,
        "failure_reason": None,
        "pairs": [],
        "refused": [],
        # The weld plan names the entities and the endpoints, so the native
        # side can regularise exactly these coordinates before it writes them.
        "weld_plan": [
            {
                "a": {"entity": candidate["entity_a"], "point": candidate["end_a"]},
                "b": {"entity": candidate["entity_b"], "point": candidate["end_b"]},
                "gap_mm": candidate["gap_mm"],
                "required_move_mm": candidate["required_move_mm"],
            }
            for candidate in accepted[:WELD_PLAN_LIMIT]
        ],
        "requested_geometry": {"entity_count": len(entities), "curve_count": len(curves)},
        "actual_geometry": None,
        "note": (
            "Python reports the pairing evidence only; the native solver owns the "
            "coincidence, so applied stays false until the kernel reports it"
        ),
    }
    if accepted:
        receipt["max_move_mm"] = max(entry["required_move_mm"] for entry in accepted)
    receipt["pairs"] = [
        {
            "curve_a": entry["curve_a"],
            "curve_b": entry["curve_b"],
            "end_a": entry["end_a"],
            "end_b": entry["end_b"],
            "entity_a": entry["entity_a"],
            "entity_b": entry["entity_b"],
            "gap_mm": entry["gap_mm"],
            "required_move_mm": entry["required_move_mm"],
        }
        for entry in accepted[:SAMPLE_LIMIT]
    ]
    receipt["refused"] = [
        {
            "curve_a": entry["curve_a"],
            "curve_b": entry["curve_b"],
            "gap_mm": entry["gap_mm"],
            "reason": entry["reason"],
        }
        for entry in refused[:SAMPLE_LIMIT]
    ]
    # DEV-077/R01: an explicit snap request rewrites the caller's line
    # endpoints before the payload leaves Python, so the receipt states that
    # this time Python did move the geometry and names every pair, gap and
    # shift. The native solver still owns its own coincidence work.
    receipt["snap"] = {
        "requested": bool(snap),
        "applied": False,
        "failure_reason": None,
        "rule": None,
        "max_shift_mm": None,
        "residual_max_mm": None,
        "pairs": [],
    }
    if snap:
        if policy == "reject":
            raise ValueError("snap_endpoints cannot be combined with endpoint_policy=reject")
        snap_pairs = accepted + _open_chain_snap_pairs(
            curves,
            accepted,
            refused,
            max_move_mm,
            allow_arc_snap=True,
            min_gap_mm=min_gap,
        )
        if snap_pairs:
            snapped, applied_pairs, failure = _snap_entities(
                entities,
                curves,
                snap_pairs,
                max_move_mm=max_move_mm,
                tolerance_mm=tolerance,
            )
            if failure is not None:
                receipt["snap"]["failure_reason"] = failure
            else:
                residual_plan = _plan(
                    snapped, max_move_mm, cluster_tolerance_mm, min_gap_mm=min_gap
                )
                residual = residual_plan[2] + _open_chain_snap_pairs(
                    residual_plan[0],
                    residual_plan[2],
                    residual_plan[3],
                    max_move_mm,
                    allow_arc_snap=True,
                    min_gap_mm=min_gap,
                )
                rules = sorted({entry["anchor"] for entry in applied_pairs})
                radius_deltas = [
                    max(
                        entry.get("radius_delta_a_mm", 0.0),
                        entry.get("radius_delta_b_mm", 0.0),
                    )
                    for entry in applied_pairs
                ]
                receipt["snap"].update(
                    {
                        "applied": True,
                        "rule": "+".join(rules),
                        "pairs": applied_pairs[:SAMPLE_LIMIT],
                        "applied_pair_count": len(applied_pairs),
                        "max_shift_mm": max(
                            max(entry["shift_a_mm"], entry["shift_b_mm"]) for entry in applied_pairs
                        ),
                        "max_radius_delta_mm": max(radius_deltas) if radius_deltas else 0.0,
                        "residual_max_mm": (
                            max(entry["gap_mm"] for entry in residual) if residual else 0.0
                        ),
                    }
                )
                receipt["applied"] = True
                receipt["applied_by"] = "python_request_rewrite"
                receipt["actual_geometry"] = {
                    "entity_count": len(snapped),
                    "max_endpoint_shift_mm": receipt["snap"]["max_shift_mm"],
                    "max_radius_delta_mm": receipt["snap"]["max_radius_delta_mm"],
                }
                receipt["note"] = (
                    "Python rewrote the accepted line/arc endpoints into shared points before "
                    "submission; the native solver still owns its own coincidence check"
                )
                receipt["_snapped_entities"] = snapped
    if policy == "reject" and accepted:
        receipt["failure_reason"] = "endpoint_pairs_present"
        receipt["would_reject"] = True
    else:
        receipt["would_reject"] = False
    return receipt


SKETCH_OPS = ("sketch", "airfoil_sketch", "update_sketch_geometry")


def prepare_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Refuse a profile the policy rejects, before a job exists.

    "reject" refuses the plan when the requested endpoints could be welded;
    "report" and the default change nothing. The receipt itself is published
    with the job result, not here, so the plan payload stays the caller's.
    """
    for operation in operations:
        if operation.get("op") not in SKETCH_OPS:
            continue
        policy = operation.get("endpoint_policy", "report")
        snap = bool(operation.get("snap_endpoints"))
        if policy == "report" and not snap:
            continue
        cluster_tol = operation.get("closure_tolerance_mm")
        receipt = prepare_endpoint_weld(
            operation.get("entities", []),
            policy=policy,
            max_move_mm=operation.get("max_endpoint_move_mm"),
            snap=snap,
            cluster_tolerance_mm=cluster_tol,
        )
        snapped = receipt.pop("_snapped_entities", None)
        # FEAT-039: the same qualification the admission message quotes decides
        # whether the requested policy can be delivered at all.
        eligibility = weld_eligibility(
            operation.get("entities", []),
            operation.get("max_endpoint_move_mm"),
            cluster_tolerance_mm=cluster_tol,
        )
        snap_failure = (receipt.get("snap") or {}).get("failure_reason")
        if snap and snap_failure:
            # snap_endpoints promised geometry movement the policy layer cannot
            # perform (two arcs, or a rectangle/polyline segment). Publishing an
            # "applied" receipt after a silent no-op is what the feedback saw.
            raise ValueError(
                "snap_endpoints asked the policy layer to snap the profile, but the rewrite was "
                f"refused ({snap_failure}) so no geometry moved. "
                + eligibility_summary(eligibility)
            )
        if snap:
            # The rewrite replaces the request geometry; the receipt keeps the
            # before/after evidence and is published with the job result.
            if snapped is not None:
                operation["entities"] = snapped
            operation["snap_endpoint_receipt"] = receipt
            operation["endpoint_weld_eligibility"] = eligibility
        if policy == "weld":
            if eligibility["verdict"] == "blocked":
                # A pair the policy layer proves it cannot weld is refused here;
                # handing the kernel a pair Python already rejected used to make
                # the job fail after the channel was taken.
                sample = "; ".join(_pair_line(pair) for pair in eligibility["blocking"][:3])
                raise ValueError(
                    "endpoint policy weld: "
                    f"{eligibility['blocking_pairs']} endpoint join(s) cannot be welded by the "
                    f"policy layer ({sample}). " + eligibility_summary(eligibility)
                )
            if (
                not snap
                and eligibility["verdict"] == "not_needed"
                and any(entity.get("type") == "arc" for entity in operation["entities"])
            ):
                # Native regularisation supports lines. Check the finer explicit
                # snap scale so an arc seam cannot silently receive an empty plan.
                entities = operation["entities"]
                _, candidates, _, _ = _plan(
                    entities,
                    operation.get("max_endpoint_move_mm"),
                    cluster_tol,
                    min_gap_mm=EXACT_TOLERANCE_MM,
                )
                if any(not pair["arc_consistent"] for pair in candidates):
                    raise ValueError(
                        "endpoint policy weld cannot regularise arc-arc seams in the native "
                        "worker. Use snap_endpoints=true with max_endpoint_move_mm to request "
                        "bounded coordinate rewriting."
                    )
            # The weld policy hands the native side the pairs to regularise.
            # Python still decides and still reports; the native side owns the
            # coordinates it writes.
            operation["weld_pairs"] = receipt.get("weld_plan") or []
            operation["endpoint_weld_eligibility"] = eligibility
        if receipt["would_reject"]:
            pairs = receipt["pairs"][:SAMPLE_LIMIT]
            raise ValueError(
                "endpoint policy reject: the requested profile has "
                f"{receipt['accepted_pairs']} weldable endpoint pair(s); "
                f"largest gap {receipt['max_move_mm']} mm; sample {pairs}"
            )
    return operations


def annotate_result(result: dict[str, Any], operations: list[dict[str, Any]]) -> None:
    """Publish the endpoint weld receipt on the matching operation result."""
    if not isinstance(result, dict):
        return
    entries = result.get("operations")
    if not isinstance(entries, list):
        return
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        if not isinstance(index, int) or not 0 <= index < len(operations):
            continue
        operation = operations[index]
        if operation.get("op") not in SKETCH_OPS:
            continue
        policy = operation.get("endpoint_policy", "report")
        stored = operation.get("snap_endpoint_receipt")
        if isinstance(stored, dict):
            receipt = dict(stored)
        else:
            receipt = prepare_endpoint_weld(
                operation.get("entities", []),
                policy=policy,
                max_move_mm=operation.get("max_endpoint_move_mm"),
                cluster_tolerance_mm=operation.get("closure_tolerance_mm"),
            )
        if (
            policy == "report"
            and receipt.get("accepted_pairs", 0) == 0
            and not isinstance(stored, dict)
        ):
            continue
        native_block = entry.get("endpoint_weld_native")
        receipt["native"] = native_block if isinstance(native_block, dict) else None
        native_details = native_block if isinstance(native_block, dict) else {}
        native_count = native_details.get("applied_pairs", 0)
        snap_count = receipt["snap"].get("applied_pair_count", 0)
        receipt["snap_applied_pairs"] = snap_count
        receipt["native_applied"] = native_count > 0
        receipt["welded_pairs"] = native_count
        if native_count:
            receipt["applied"] = True
            receipt["applied_by"] = "python_request_rewrite_and_native" if snap_count else "native"
            receipt["note"] = "Native coordinate regularisation is reported in the native block."
        elif policy == "weld" and not snap_count:
            receipt["failure_reason"] = (
                "native_pairs_skipped"
                if native_details.get("skipped")
                else "no_native_pairs_applied"
            )
        entry["endpoint_weld"] = receipt
