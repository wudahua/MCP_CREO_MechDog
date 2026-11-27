"""Bounded saved-model queries; partial pages never pretend to be full snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Callable
from typing import Any

from creo_mechdog.f08_contract import is_cut_scope_body_id

RESPONSE_BUDGET = 32 * 1024
COUNT_KEYS = ("features", "surfaces", "edges", "quilts", "bodies", "components")
# BUG-040: counts.bodies is the number of body *objects* (records), which
# includes non-active records that hold no material. The native body_counts
# block carries the separated numbers; it is projected only when present, and
# unknown values stay null instead of being recomputed from the records here.
BODY_COUNT_KEYS = ("objects", "records", "active", "with_material", "without_material")
SECTIONS = (
    "features",
    "dimensions",
    "surfaces",
    "edges",
    "quilts",
    "bodies",
    "datum_planes",
    "datum_axes",
    "parameters",
    "aliases",
    "components",
    "feature_geometry",
    "sketch_dimensions",
    "sheets",
    "views",
    "notes",
    "tables",
    "models",
    "shown_dimensions",
    "metadata",
)


def serialized_size(value: Any) -> int:
    # Include indentation and ASCII escaping used by MCP text renderers.
    return len(json.dumps(value, ensure_ascii=True, indent=2).encode("utf-8"))


def summary_of_model(model: dict[str, Any]) -> dict[str, Any]:
    # Deferred import: inspection_refs reads this module for the summary shape.
    from creo_mechdog.inspection_refs import summary_of

    return qualify_bounding_box(summary_of(model))


def full_inspection_of_model(model: dict[str, Any]) -> dict[str, Any]:
    """Adopted models may carry a controlled reference instead of an inline
    payload (BUG-076); both resolve here, tampered references refuse."""
    from creo_mechdog.inspection_refs import full_inspection

    return qualify_bounding_box(full_inspection(model) or {})


def qualify_bounding_box(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Expose historical regeneration outlines under their own name in read views."""
    if snapshot.get("bounding_box_mm") is None or "bounding_box_source" in snapshot:
        return snapshot
    return {
        **snapshot,
        "bounding_box_mm": None,
        "bounding_box_source": "legacy_regeneration_outline",
        "bounding_box_status": {"state": "unavailable", "reason": "legacy_snapshot"},
        "legacy_regeneration_outline_mm": snapshot["bounding_box_mm"],
    }


def body_counts(value: Any) -> dict[str, Any] | None:
    # None means "not reported" (an assembly, or a pre-T08B result). A single
    # None means the native side could not query that number. Nothing is
    # derived from the records here: that would silently reintroduce the
    # two-meanings-in-one-field defect this block exists to remove.
    if not isinstance(value, dict):
        return None
    counts: dict[str, Any] = {}
    for key in BODY_COUNT_KEYS:
        item = value.get(key)
        counts[key] = item if type(item) is int and item >= 0 else None
    meaning = value.get("counts_meaning")
    if isinstance(meaning, dict):
        counts["counts_meaning"] = {
            key: text
            for key, text in meaning.items()
            if isinstance(key, str) and isinstance(text, str)
        }
    return counts


COUNTS_CONVENTION = (
    "Creo reports full cylindrical faces as 2 half-cylinders and full circular edges as 2 "
    "semicircular arcs (plus seam edges). merged_counts groups coaxial split cylindrical faces "
    "and co-circular split circular edges into logical counts."
)


def _vec_norm(v: Any) -> float:
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        return 0.0
    return (float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2) ** 0.5


def _vec_dot(a: list[float], b: list[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _axis_distance(point: list[float], origin: list[float], axis: list[float]) -> float:
    dx, dy, dz = point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]
    along = dx * axis[0] + dy * axis[1] + dz * axis[2]
    px, py, pz = dx - axis[0] * along, dy - axis[1] * along, dz - axis[2] * along
    return (px * px + py * py + pz * pz) ** 0.5


def _merged_topology_counts(state: dict[str, Any]) -> dict[str, Any] | None:
    """Group coaxial split cylinders and co-circular split arcs into logical counts (FEAT-078)."""
    surfaces = state.get("surfaces")
    edges = state.get("edges")
    if not isinstance(surfaces, list) and not isinstance(edges, list):
        return state.get("merged_counts") if isinstance(state.get("merged_counts"), dict) else None

    merged_surfaces: int | None = None
    cyl_groups = 0
    if isinstance(surfaces, list):
        # Cylinder type in Creo is PRO_SRF_CYL (36), identified by having axis + radius + origin.
        non_cyl = 0
        groups: list[tuple[list[float], list[float], float, list[list[float]]]] = []
        for srf in surfaces:
            if not isinstance(srf, dict):
                continue
            axis_raw = srf.get("axis")
            origin_raw = srf.get("origin")
            radius_raw = srf.get("radius")
            if (
                isinstance(axis_raw, list)
                and len(axis_raw) == 3
                and isinstance(origin_raw, list)
                and len(origin_raw) == 3
                and isinstance(radius_raw, (int, float))
                and not isinstance(radius_raw, bool)
            ):
                norm = _vec_norm(axis_raw)
                if norm <= 1e-9:
                    non_cyl += 1
                    continue
                axis = [float(x) / norm for x in axis_raw]
                origin = [float(x) for x in origin_raw]
                radius = float(radius_raw)
                bbox = srf.get("bbox")
                matched = False
                for g_axis, g_origin, g_radius, g_bboxes in groups:
                    if abs(_vec_dot(axis, g_axis)) < 0.99996:  # ~0.5 deg
                        continue
                    if abs(radius - g_radius) > 1e-4:
                        continue
                    if _axis_distance(origin, g_origin, g_axis) > 1e-4:
                        continue
                    # Also check axial overlap if bboxes are available so two separate
                    # coaxial cylinders along the same shaft are not merged.
                    if (
                        isinstance(bbox, list)
                        and len(bbox) == 2
                        and g_bboxes
                        and all(isinstance(b, list) and len(b) == 2 for b in g_bboxes)
                    ):
                        p0 = _vec_dot([float(x) for x in bbox[0]], g_axis)
                        p1 = _vec_dot([float(x) for x in bbox[1]], g_axis)
                        lo, hi = min(p0, p1), max(p0, p1)
                        overlaps = False
                        for gb in g_bboxes:
                            q0 = _vec_dot([float(x) for x in gb[0]], g_axis)
                            q1 = _vec_dot([float(x) for x in gb[1]], g_axis)
                            glo, ghi = min(q0, q1), max(q0, q1)
                            if hi >= glo - 1e-3 and ghi >= lo - 1e-3:
                                overlaps = True
                                break
                        if not overlaps:
                            continue
                    if isinstance(bbox, list) and len(bbox) == 2:
                        g_bboxes.append(bbox)
                    matched = True
                    break
                if not matched:
                    groups.append(
                        (
                            axis,
                            origin,
                            radius,
                            [bbox] if isinstance(bbox, list) and len(bbox) == 2 else [],
                        )
                    )
            else:
                non_cyl += 1
        cyl_groups = len(groups)
        merged_surfaces = non_cyl + cyl_groups

    merged_edges: int | None = None
    circle_groups = 0
    if isinstance(edges, list):
        non_arc = 0
        c_groups: list[tuple[list[float], list[float], float]] = []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            arc = edge.get("arc")
            if (
                isinstance(arc, dict)
                and isinstance(arc.get("origin"), list)
                and len(arc["origin"]) == 3
                and isinstance(arc.get("v1"), list)
                and isinstance(arc.get("v2"), list)
                and isinstance(arc.get("radius"), (int, float))
            ):
                normal = _vec_cross([float(x) for x in arc["v1"]], [float(x) for x in arc["v2"]])
                norm = _vec_norm(normal)
                if norm <= 1e-9:
                    non_arc += 1
                    continue
                normal = [x / norm for x in normal]
                center = [float(x) for x in arc["origin"]]
                radius = float(arc["radius"])
                matched = False
                for g_normal, g_center, g_radius in c_groups:
                    if abs(_vec_dot(normal, g_normal)) < 0.99996:
                        continue
                    if abs(radius - g_radius) > 1e-4:
                        continue
                    if max(abs(center[i] - g_center[i]) for i in range(3)) > 1e-4:
                        continue
                    matched = True
                    break
                if not matched:
                    c_groups.append((normal, center, radius))
            else:
                non_arc += 1
        circle_groups = len(c_groups)
        merged_edges = non_arc + circle_groups

    return {
        "surfaces": merged_surfaces,
        "edges": merged_edges,
        "cylindrical_face_groups": cyl_groups,
        "circular_edge_groups": circle_groups,
    }


def inspection_summary(inspection: Any) -> dict[str, Any]:
    """Summarize an inspection payload without changing its meaning.

    ``counts`` keeps its historical meaning: the number of records per
    section (``bodies`` counts body objects, not material bodies). The native
    ``body_counts`` block is the separated view and is passed through as-is.
    """
    state = qualify_bounding_box(inspection) if isinstance(inspection, dict) else {}
    supplied = state.get("counts") or {}
    counts = {}
    for key in COUNT_KEYS:
        value = supplied.get(key)
        counts[key] = (
            len(state[key])
            if isinstance(state.get(key), list)
            else value
            if type(value) is int and value >= 0
            else None
        )
    summary = {
        **{
            key: state[key]
            for key in (
                "healthy",
                "has_solid",
                "units",
                "units_query_code",
                "length_unit",
                "center_of_gravity",
                "model_type",
                "volume_mm3",
                "volume_query_code",
                "total_surface_area_mm2",
                "bounding_box_mm",
                "bounding_box_source",
                "bounding_box_status",
                "legacy_regeneration_outline_mm",
                "inspection_source",
                "inspection_available",
                "verified_feature_counts",
            )
            if key in state
        },
        "counts": counts,
        "body_counts": body_counts(state.get("body_counts")),
        "inspection_available": bool(state) and state.get("inspection_available", True),
    }
    merged = _merged_topology_counts(state)
    if merged is not None:
        summary["merged_counts"] = merged
        summary["counts_convention"] = COUNTS_CONVENTION
    return summary


def model_summary(model: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: model[key]
        for key in (
            "model_id",
            "model_name",
            "model_type",
            "status",
            "revision",
            "created_at",
            "updated_at",
            "pending_job",
            "recovery_pending",
            "reconciliation",
            "part_sha256",
            "last_job",
            "last_query_at",
            "part_file",
        )
        if key in model
    }
    result["inspection"] = summary_of_model(model)
    saved = bool(model.get("inspection") or model.get("inspection_ref")) and bool(
        model.get("part_file")
    )
    snapshot_source = (
        model.get("snapshot_source")
        if saved and model.get("snapshot_source") == "refresh_verified"
        else ("saved_verified" if saved else "unavailable")
    )
    snapshot_meta: dict[str, Any] = {
        "source": snapshot_source,
        "revision": model.get("revision"),
        "at": model.get("updated_at"),
        "live_state_verified": False,
        "mutation_pending": bool(model.get("pending_job") or model.get("recovery_pending")),
    }
    if snapshot_source == "refresh_verified" and model.get("snapshot_refreshed_at"):
        snapshot_meta["refreshed_at"] = model.get("snapshot_refreshed_at")
    insp_summary = result["inspection"]
    if saved and insp_summary.get("inspection_available"):
        counts = insp_summary.get("counts") or {}
        has_surface_or_solid = bool(insp_summary.get("has_solid")) or (
            isinstance(counts.get("surfaces"), int) and counts["surfaces"] > 0
        )
        if has_surface_or_solid:
            stale_fields = [
                key
                for key in ("total_surface_area_mm2", "bounding_box_mm", "merged_counts")
                if insp_summary.get(key) is None
            ]
            if (
                insp_summary.get("bounding_box_source") == "legacy_regeneration_outline"
                and "bounding_box_mm" not in stale_fields
            ):
                stale_fields.append("bounding_box_mm")
            raw_insp = model.get("inspection")
            raw_surfaces = raw_insp.get("surfaces") if isinstance(raw_insp, dict) else None
            if (
                isinstance(raw_surfaces, list)
                and raw_surfaces
                and any(isinstance(s, dict) and s.get("area_mm2") is None for s in raw_surfaces)
            ):
                stale_fields.append("surfaces[].area_mm2")
            if stale_fields:
                snapshot_meta["stale_fields"] = stale_fields
                snapshot_meta["refresh_hint"] = (
                    "This snapshot predates newer inspection fields; call "
                    "creo_refresh_model(model_id, write_back_snapshot=True) to backfill metadata "
                    "without changing revision or model file bytes, or read "
                    "result.inspection_summary via creo_get_job(detail='compact', "
                    "sections=['inspection_summary']) / detail='full'."
                )
    result["snapshot"] = snapshot_meta
    result["detail_available"] = True
    source = model.get("adopted_from")
    result["adopted"] = bool(source and source.get("state") == "completed")
    result["source_kind"] = (source or {}).get("source_kind", "file" if source else "created")
    from creo_mechdog import feature_state

    tombstones = feature_state.tombstones_of(model)
    suppressed = feature_state.suppressed_of(model)
    # Bounded preview: counts stay complete, entries are capped so one registry
    # can never push a compact model summary past the 32 KiB page budget.
    limit = 20
    result["feature_state"] = {
        "tombstone_count": len(tombstones),
        "suppressed_count": len(suppressed),
        "tombstones": dict(list(tombstones.items())[:limit]),
        "suppressed": dict(list(suppressed.items())[:limit]),
        "entries_truncated": len(tombstones) > limit or len(suppressed) > limit,
    }
    return result


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def encode_cursor(value: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if cursor is None:
        return None
    if len(cursor) > 4096:
        raise ValueError("Invalid query cursor")
    try:
        value = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid query cursor") from exc
    if not isinstance(value, dict) or type(value.get("offset")) is not int or value["offset"] < 0:
        raise ValueError("Invalid query cursor")
    return value


def _body_records(records: list[Any]) -> list[Any]:
    return [
        {**record, "cut_scope_id_eligible": is_cut_scope_body_id(record.get("id"))}
        if isinstance(record, dict)
        else record
        for record in records
    ]


def section_records(model: dict[str, Any], section: str) -> list[Any] | None:
    state = full_inspection_of_model(model)
    if section == "metadata":
        excluded = set(SECTIONS) | set(inspection_summary(state)) | {"counts"}
        return [{"name": key, "value": val} for key, val in state.items() if key not in excluded]
    if section in ("aliases", "parameters"):
        if section == "aliases":
            # Split registry records keep aliases in a controlled sidecar
            # (BUG-077); resolve on demand, never inline into every page read.
            from creo_mechdog.model_registry import aliases_of

            values = aliases_of(model)
        else:
            values = full_inspection_of_model(model).get("parameters")
        return (
            [{"name": key, "value": val} for key, val in (values or {}).items()]
            if isinstance(values, dict)
            else None
        )
    if section in ("dimensions", "feature_geometry", "sketch_dimensions"):
        features = state.get("features")
        if not isinstance(features, list):
            return None
        field = {
            "dimensions": "dimensions",
            "feature_geometry": "geometry_items",
            "sketch_dimensions": "sketch_dimensions",
        }[section]
        return [{"feature_id": f["id"], **entry} for f in features for entry in f.get(field, [])]
    values = state.get(section)
    if not isinstance(values, list):
        return None
    if section == "bodies":
        return _body_records(values)
    if section == "components":
        # FEAT-023/T09A: project business labels and source identity onto the
        # physical-copy records at query time (join key: model identity plus
        # feature_id). Stored inspection payloads are never rewritten.
        from creo_mechdog import component_identity

        return component_identity.decorate_component_records(model, values)
    if section == "features":
        # Large nested collections have their own independently paginated sections.
        return [
            {
                key: val
                for key, val in f.items()
                if key not in ("dimensions", "geometry_items", "sketch_dimensions", "datum_axes")
            }
            for f in values
        ]
    return values


NEAR_SECTIONS = ("edges", "surfaces")


def _validate_near(near: Any, max_distance_mm: Any) -> tuple[list[float], float | None]:
    if not isinstance(near, (list, tuple)) or len(near) != 3:
        raise ValueError("near must be a 3-element [x, y, z] coordinate in mm")
    coords: list[float] = []
    for index, value in enumerate(near):
        if isinstance(value, bool) or type(value) not in (int, float):
            raise ValueError(f"near[{index}] must be a finite number")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"near[{index}] must be finite")
        coords.append(number)
    limit_dist: float | None = None
    if max_distance_mm is not None:
        if isinstance(max_distance_mm, bool) or type(max_distance_mm) not in (int, float):
            raise ValueError("max_distance_mm must be a non-negative finite number")
        limit_dist = float(max_distance_mm)
        if not math.isfinite(limit_dist) or limit_dist < 0:
            raise ValueError("max_distance_mm must be a non-negative finite number")
    return coords, limit_dist


def _point_vec(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        x, y, z = float(value[0]), float(value[1]), float(value[2])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
        return None
    return (x, y, z)


def _segment_distance(
    p: tuple[float, float, float], a: tuple[float, float, float], b: tuple[float, float, float]
) -> float:
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    len_sq = dx * dx + dy * dy + dz * dz
    if len_sq <= 1e-18:
        return math.dist(p, a)
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy + (p[2] - a[2]) * dz) / len_sq
    t = max(0.0, min(1.0, t))
    closest = (a[0] + dx * t, a[1] + dy * t, a[2] + dz * t)
    return math.dist(p, closest)


def _arc_distance(p: tuple[float, float, float], arc: dict[str, Any]) -> float | None:
    origin = _point_vec(arc.get("origin"))
    v1 = _point_vec(arc.get("v1"))
    v2 = _point_vec(arc.get("v2"))
    try:
        radius = float(arc["radius"])
        start_a = float(arc.get("start_angle", 0.0))
        end_a = float(arc.get("end_angle", 2.0 * math.pi))
    except (KeyError, TypeError, ValueError):
        return None
    if origin is None or v1 is None or v2 is None or not math.isfinite(radius) or radius < 0:
        return None
    n1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2 + v1[2] ** 2)
    n2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2 + v2[2] ** 2)
    if n1 <= 1e-12 or n2 <= 1e-12:
        return math.dist(p, origin)
    u1 = (v1[0] / n1, v1[1] / n1, v1[2] / n1)
    u2 = (v2[0] / n2, v2[1] / n2, v2[2] / n2)
    rel = (p[0] - origin[0], p[1] - origin[1], p[2] - origin[2])
    c1 = rel[0] * u1[0] + rel[1] * u1[1] + rel[2] * u1[2]
    c2 = rel[0] * u2[0] + rel[1] * u2[1] + rel[2] * u2[2]
    two_pi = 2.0 * math.pi
    span = end_a - start_a
    if span < 0:
        span += two_pi
    angle = math.atan2(c2, c1)
    if span < two_pi - 1e-6:
        offset = (angle - start_a) % two_pi
        if offset > span:
            # Clamp to closer of start_angle or end_angle
            cand_start = (
                origin[0] + radius * (math.cos(start_a) * u1[0] + math.sin(start_a) * u2[0]),
                origin[1] + radius * (math.cos(start_a) * u1[1] + math.sin(start_a) * u2[1]),
                origin[2] + radius * (math.cos(start_a) * u1[2] + math.sin(start_a) * u2[2]),
            )
            cand_end = (
                origin[0] + radius * (math.cos(end_a) * u1[0] + math.sin(end_a) * u2[0]),
                origin[1] + radius * (math.cos(end_a) * u1[1] + math.sin(end_a) * u2[1]),
                origin[2] + radius * (math.cos(end_a) * u1[2] + math.sin(end_a) * u2[2]),
            )
            return min(math.dist(p, cand_start), math.dist(p, cand_end))
    closest = (
        origin[0] + radius * (math.cos(angle) * u1[0] + math.sin(angle) * u2[0]),
        origin[1] + radius * (math.cos(angle) * u1[1] + math.sin(angle) * u2[1]),
        origin[2] + radius * (math.cos(angle) * u1[2] + math.sin(angle) * u2[2]),
    )
    return math.dist(p, closest)


def _record_distance(section: str, record: dict[str, Any], target: list[float]) -> float | None:
    p = (target[0], target[1], target[2])
    if section == "edges":
        start = _point_vec(record.get("start"))
        end = _point_vec(record.get("end"))
        if start is not None and end is not None:
            return _segment_distance(p, start, end)
        arc = record.get("arc")
        if isinstance(arc, dict):
            return _arc_distance(p, arc)
        return None
    if section == "surfaces":
        bbox = record.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 2:
            lo = _point_vec(bbox[0])
            hi = _point_vec(bbox[1])
            if lo is not None and hi is not None:
                cx = min(max(p[0], lo[0]), hi[0])
                cy = min(max(p[1], lo[1]), hi[1])
                cz = min(max(p[2], lo[2]), hi[2])
                return math.dist(p, (cx, cy, cz))
        origin = _point_vec(record.get("origin"))
        if origin is not None:
            return math.dist(p, origin)
    return None


def inspect_page(
    model: dict[str, Any],
    detail: str = "compact",
    section: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    near: list[float] | None = None,
    max_distance_mm: float | None = None,
) -> dict[str, Any]:
    if detail not in ("compact", "full"):
        raise ValueError("detail must be compact or full")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1–200")
    if section is not None and section not in SECTIONS:
        raise ValueError("Unknown section; use " + ", ".join(SECTIONS))
    if detail == "compact" and (
        section is not None or cursor is not None or near is not None or max_distance_mm is not None
    ):
        raise ValueError("section/cursor/near require detail=full")
    if max_distance_mm is not None and near is None:
        raise ValueError("max_distance_mm requires near=[x, y, z]")
    near_point: list[float] | None = None
    near_limit: float | None = None
    if near is not None:
        if section not in NEAR_SECTIONS:
            raise ValueError("near spatial filter requires section=" + " or ".join(NEAR_SECTIONS))
        near_point, near_limit = _validate_near(near, max_distance_mm)
    response = model_summary(model)
    response.update(detail=detail, sections_available=list(SECTIONS), complete=detail == "compact")
    if detail == "compact":
        if serialized_size(response) > RESPONSE_BUDGET:
            raise ValueError("Model summary exceeds response budget")
        return response
    token = decode_cursor(cursor)
    identity: dict[str, Any] = {
        "model_id": model["model_id"],
        "revision": model["revision"],
        "snapshot_hash": fingerprint(model),
        "section": section,
    }
    if near_point is not None:
        identity["near"] = near_point
        if near_limit is not None:
            identity["max_distance_mm"] = near_limit
    if token and any(token.get(key) != value for key, value in identity.items()):
        raise ValueError("Snapshot or query changed; restart inspection without cursor")
    # Small legacy full snapshots remain available without collection reshaping.
    if section is None and token is None and near_point is None:
        whole = {
            **model,
            **{
                "detail": "full",
                "complete": True,
                "next_cursor": None,
                "snapshot": response["snapshot"],
            },
        }
        # Split registry records keep inspection/aliases in sidecars (BUG-077);
        # resolve them here so this shape carries the same sections the paged
        # shape serves from section_records, instead of only their *_ref stubs.
        if "inspection" not in whole and model.get("inspection_ref") is not None:
            resolved = full_inspection_of_model(model)
            if resolved:
                whole["inspection"] = resolved
        if "aliases" not in whole and model.get("aliases_ref") is not None:
            from creo_mechdog.model_registry import aliases_of

            resolved = aliases_of(model)
            if isinstance(resolved, dict):
                whole["aliases"] = resolved
        # The paged components section serves identity-decorated records; the
        # whole fast path must serve the same shape (T08 feature_state
        # precedent), so the two full shapes cannot disagree on labels.
        payload = whole.get("inspection")
        if isinstance(payload, dict):
            payload = qualify_bounding_box(payload)
            whole["inspection"] = payload
        if isinstance(whole.get("inspection_summary"), dict):
            whole["inspection_summary"] = response["inspection"]
        if isinstance(payload, dict) and isinstance(payload.get("bodies"), list):
            payload = {**payload, "bodies": _body_records(payload["bodies"])}
            whole["inspection"] = payload
        if isinstance(payload, dict) and isinstance(payload.get("components"), list):
            from creo_mechdog import component_identity

            whole["inspection"] = {
                **payload,
                "components": component_identity.decorate_component_records(
                    model, payload["components"]
                ),
            }
        # The T08 registries ride in model_summary; the whole fast path serves
        # the same bounded feature_state section the paged shape serves, so the
        # two full shapes cannot disagree about tombstones/suppressions.
        whole["feature_state"] = response["feature_state"]
        if (
            serialized_size(whole) <= RESPONSE_BUDGET
            and max((len(section_records(model, name) or []) for name in SECTIONS), default=0)
            <= limit
        ):
            return whole
    names = [section] if section is not None else list(SECTIONS)
    if near_point is not None and section is not None:
        raw_items = section_records(model, section) or []
        scored: list[tuple[float, int, dict[str, Any]]] = []
        for index, record in enumerate(raw_items):
            if not isinstance(record, dict):
                continue
            dist = _record_distance(section, record, near_point)
            if dist is None:
                continue
            if near_limit is not None and dist > near_limit:
                continue
            rec_id = record.get("id")
            sort_id = rec_id if isinstance(rec_id, int) else index
            scored.append((dist, sort_id, {**record, "distance_mm": round(dist, 6)}))
        scored.sort(key=lambda item: (item[0], item[1]))
        records = [(section, item[2]) for item in scored]
        response["near_filter"] = {
            "near_mm": near_point,
            "max_distance_mm": near_limit,
            "matched_total": len(records),
            "scanned_total": len(raw_items),
        }
    else:
        records = [
            (name, record) for name in names for record in (section_records(model, name) or [])
        ]
    start = token["offset"] if token else 0
    if start > len(records):
        raise ValueError("Invalid query cursor offset")
    response.update(
        data={name: [] for name in names},
        complete=False,
        next_cursor=None,
        offset=start,
        section=section,
        unavailable_sections=[name for name in names if section_records(model, name) is None],
        returned_count=0,
        page_count=0,
        total_count=len(records),
    )
    end = start
    while end < len(records) and end - start < limit:
        name, record = records[end]
        response["data"][name].append(record)
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": end + 1}) if end + 1 < len(records) else None
        )
        response["complete"] = end + 1 == len(records)
        response["returned_count"] = end + 1 - start
        response["page_count"] = end + 1 - start
        if serialized_size(response) > RESPONSE_BUDGET:
            response["data"][name].pop()
            if end == start:
                raise ValueError(
                    f"Single {name} record exceeds 32 KiB; request dimensions/feature_geometry/sketch_dimensions separately or inspect a narrower section"
                )
            break
        end += 1
    while True:
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": end}) if end < len(records) else None
        )
        response["complete"] = end == len(records)
        response["returned_count"] = end - start
        response["page_count"] = end - start
        if serialized_size(response) <= RESPONSE_BUDGET:
            return response
        # FEAT-023: the cursor belongs to the page; when it no longer fits beside
        # the last record, that record moves to the next page instead of the whole
        # query failing with a budget error.
        if end - start <= 0:
            raise ValueError(
                "Query metadata exceeds response budget even with an empty page; "
                "request a narrower section"
            )
        end -= 1
        response["data"][records[end][0]].pop()


def list_page(
    models: list[dict[str, Any]],
    loader: Callable[[str], dict[str, Any]],
    detail: str = "compact",
    limit: int = 10,
    cursor: str | None = None,
) -> dict[str, Any]:
    if detail not in ("compact", "full") or not 1 <= limit <= 50:
        raise ValueError("detail must be compact/full and limit must be 1–50")
    identity = {"detail": detail, "snapshot_hash": fingerprint(models)}
    token = decode_cursor(cursor)
    if token and any(token.get(key) != value for key, value in identity.items()):
        raise ValueError("Model list changed; restart listing without cursor")
    start = token["offset"] if token else 0
    if start > len(models):
        raise ValueError("Invalid query cursor offset")
    response = {"models": [], "detail": detail, "complete": False, "next_cursor": None}
    end = start
    while end < len(models) and end - start < limit:
        model = models[end]
        if detail == "full":
            current = loader(model["model_id"])
            if model_summary(current) != model:
                raise ValueError("Model list changed; restart listing without cursor")
            item = inspect_page(current, "full")
        else:
            item = model
        # full lists may include a first detail page; each model exposes its own cursor.
        response["models"].append(item)
        response["next_cursor"] = (
            encode_cursor({**identity, "offset": end + 1}) if end + 1 < len(models) else None
        )
        if serialized_size(response) > RESPONSE_BUDGET:
            response["models"].pop()
            if end == start:
                raise ValueError(
                    "Single model exceeds list budget; use detail=compact then creo_inspect_model"
                )
            break
        end += 1
    response["complete"] = end == len(models)
    response["next_cursor"] = (
        encode_cursor({**identity, "offset": end}) if end < len(models) else None
    )
    return response
