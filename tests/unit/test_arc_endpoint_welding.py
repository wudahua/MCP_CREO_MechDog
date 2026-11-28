"""FEAT-090: near-tolerance arc-arc endpoint welding and sketch tool exposure."""

from __future__ import annotations

import inspect
import math
import unittest

from creo_mechdog import schema, server
from creo_mechdog.endpoint_welding import annotate_result, prepare_endpoint_weld, prepare_operations


def _arc_endpoints(arc: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    cx, cy = arc["center"]
    r = arc["radius"]
    a0 = math.radians(arc["start_angle"])
    a1 = math.radians(arc["end_angle"])
    return (cx + r * math.cos(a0), cy + r * math.sin(a0)), (
        cx + r * math.cos(a1),
        cy + r * math.sin(a1),
    )


def _gear10_like_entities(gap_mm: float = 8.215e-7) -> list[dict]:
    """Build 10 independent closed 4-arc contours (40 arcs) with micro-gaps at seams.

    Mimics the gear10.json topology (different-center arcs meeting at ~8.2e-7 mm gaps).
    """
    entities: list[dict] = []
    for k in range(10):
        ox = k * 20.0
        oy = 0.0
        # 4 bulging arcs forming a closed pillow contour around (ox, oy).
        # Nominal vertices at (ox±3, oy±3); each arc has a distinct center.
        corners = [
            (ox + 3.0, oy - 3.0),
            (ox + 3.0, oy + 3.0),
            (ox - 3.0, oy + 3.0),
            (ox - 3.0, oy - 3.0),
        ]
        centers = [
            (ox - 1.0, oy),
            (ox, oy - 1.0),
            (ox + 1.0, oy),
            (ox, oy + 1.0),
        ]
        radius = 5.0  # distance from (ox-1, oy) to (ox+3, oy±3) is sqrt(16+9)=5
        for side in range(4):
            c = centers[side]
            p0 = corners[side]
            p1 = corners[(side + 1) % 4]
            a0 = math.degrees(math.atan2(p0[1] - c[1], p0[0] - c[0])) % 360.0
            a1 = math.degrees(math.atan2(p1[1] - c[1], p1[0] - c[0])) % 360.0
            # Introduce a small angular offset so every seam has ~gap_mm mismatch
            delta_deg = math.degrees(gap_mm / radius)
            entities.append(
                {
                    "type": "arc",
                    "name": f"g{k}_a{side}",
                    "center": [c[0], c[1]],
                    "radius": radius,
                    "start_angle": a0,
                    "end_angle": (a1 - delta_deg) % 360.0,
                    "dir": 1,
                }
            )
    return entities


class ArcEndpointWeldingTests(unittest.TestCase):
    def test_intersecting_different_center_arcs_snap_with_zero_radius_delta(self):
        # Two arcs of different circles that intersect at (3, 3), slightly backed off.
        entities = _gear10_like_entities(gap_mm=8.215e-7)[:4]
        receipt = prepare_endpoint_weld(entities, snap=True, max_move_mm=1e-4)
        self.assertTrue(receipt["applied"])
        self.assertTrue(receipt["snap"]["applied"])
        self.assertEqual(receipt["snap"]["applied_pair_count"], 4)
        self.assertEqual(receipt["snap"]["max_radius_delta_mm"], 0.0)
        self.assertLessEqual(receipt["snap"]["residual_max_mm"], 1e-12)
        snapped = receipt["_snapped_entities"]
        for i in range(4):
            _, end_i = _arc_endpoints(snapped[i])
            start_next, _ = _arc_endpoints(snapped[(i + 1) % 4])
            self.assertLess(math.dist(end_i, start_next), 1e-12)

    def test_non_intersecting_near_tangent_arcs_snap_via_three_point_refit(self):
        # Two externally near-tangent circles separated by 2e-6 mm along X.
        gap = 2e-6
        entities = [
            {
                "type": "arc",
                "name": "left_arc",
                "center": [-5.0 - gap / 2.0, 0.0],
                "radius": 5.0,
                "start_angle": -90.0,
                "end_angle": 0.0,
                "dir": 1,
            },
            {
                "type": "arc",
                "name": "right_arc",
                "center": [5.0 + gap / 2.0, 0.0],
                "radius": 5.0,
                "start_angle": 180.0,
                "end_angle": 270.0,
                "dir": 1,
            },
        ]
        receipt = prepare_endpoint_weld(entities, snap=True, max_move_mm=1e-4)
        self.assertTrue(receipt["applied"])
        self.assertEqual(receipt["snap"]["rule"], "arc_three_point")
        self.assertLessEqual(receipt["snap"]["residual_max_mm"], 1e-12)
        self.assertLess(receipt["snap"]["max_radius_delta_mm"], 1e-4)
        snapped = receipt["_snapped_entities"]
        _, end_left = _arc_endpoints(snapped[0])
        start_right, _ = _arc_endpoints(snapped[1])
        self.assertLess(math.dist(end_left, start_right), 1e-12)

    def test_gear10_40_arc_10_contour_micro_gaps_all_snap_to_coincidence(self):
        entities = _gear10_like_entities(gap_mm=8.215e-7)
        op = {
            "op": "sketch",
            "label": "gear10",
            "plane": "XY",
            "entities": entities,
            "snap_endpoints": True,
            "max_endpoint_move_mm": 1e-4,
        }
        prepared = prepare_operations([op])
        snap = prepared[0]["snap_endpoint_receipt"]["snap"]
        self.assertTrue(snap["applied"])
        self.assertEqual(snap["applied_pair_count"], 40)
        self.assertLessEqual(snap["residual_max_mm"], 1e-12)
        snapped = prepared[0]["entities"]
        for k in range(10):
            base = k * 4
            for side in range(4):
                _, end_i = _arc_endpoints(snapped[base + side])
                start_next, _ = _arc_endpoints(snapped[base + ((side + 1) % 4)])
                self.assertLess(math.dist(end_i, start_next), 1e-12)

    def test_explicit_internal_pairs_are_refused_on_create_and_update(self):
        for operation in (
            {"op": "sketch", "label": "s"},
            {"op": "update_sketch_geometry", "sketch": "s"},
        ):
            spec = {**operation, "entities": _gear10_like_entities()[:4]}
            with self.assertRaisesRegex(ValueError, "weld_pairs is generated internally"):
                schema.validate_operations([{**spec, "weld_pairs": [{"entity_a": "a"}] * 20}])
            self.assertNotIn(
                "weld_pairs", schema.validate_operations([{**spec, "weld_pairs": []}])[0]
            )

    def test_different_center_arc_weld_requires_explicit_snap(self):
        op = {
            "op": "sketch",
            "entities": _gear10_like_entities(),
            "endpoint_policy": "weld",
            "max_endpoint_move_mm": 0.01,
        }
        with self.assertRaisesRegex(ValueError, "snap_endpoints=true"):
            prepare_operations([op])
        ops = prepare_operations([{**op, "snap_endpoints": True}])
        entry = {"index": 0, "endpoint_weld_native": {"applied_pairs": 0}}
        annotate_result({"operations": [entry]}, ops)
        self.assertEqual(entry["endpoint_weld"]["snap_applied_pairs"], 40)
        self.assertEqual(entry["endpoint_weld"]["applied_by"], "python_request_rewrite")
        self.assertFalse(entry["endpoint_weld"]["native_applied"])

    def test_native_applied_count_comes_from_the_worker(self):
        op = {"op": "sketch", "entities": [], "endpoint_policy": "weld"}
        entry = {"index": 0, "endpoint_weld_native": {"applied_pairs": 2}}
        annotate_result({"operations": [entry]}, [op])
        self.assertEqual(entry["endpoint_weld"]["welded_pairs"], 2)
        self.assertTrue(entry["endpoint_weld"]["native_applied"])
        self.assertEqual(entry["endpoint_weld"]["applied_by"], "native")

    def test_sketch_mcp_tools_expose_endpoint_welding_parameters(self):
        for fn in (server.creo_create_sketch, server.creo_update_sketch_geometry):
            params = inspect.signature(fn).parameters
            for name in (
                "snap_endpoints",
                "endpoint_policy",
                "max_endpoint_move_mm",
                "closure_tolerance_mm",
            ):
                with self.subTest(tool=fn.__name__, param=name):
                    self.assertIn(name, params)


if __name__ == "__main__":
    unittest.main()
