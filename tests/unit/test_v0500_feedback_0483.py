"""Unit regressions and contract checks for v0.50.0 (v0.48.3 feedback resolution)."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from creo_mechdog import (
    bridge,
    capabilities,
    capability_pages,
    profile_diagnostics,
    seeds,
    server,
)
from creo_mechdog.blend_callback import callback_advisory, callback_guidance
from creo_mechdog.schema import BooleanOp, SketchOp
from creo_mechdog.status_projection import compact_status_response


class Bug204CallbackGuidanceTests(unittest.TestCase):
    def test_callback_guidance_not_loaded_lists_affected_ops_and_recovery_steps(self):
        guidance = callback_guidance(
            {
                "readiness": "not_loaded",
                "artifact_status": "prepared",
                "registry_file": "D:/repo/build/blend_callback_protk.dat",
                "persistent_registration_config": "D:/repo/build/blend_callback.config.pro",
            }
        )
        self.assertEqual(
            guidance["affected_operations"],
            [
                "loft (creo_loft)",
                "surface_loft with creation_route='resident_panel' (creo_surface_loft)",
            ],
        )
        self.assertEqual(
            guidance["unaffected_alternatives"]["creo_new_loft_part"]["scope"], "new_part_only"
        )
        steps_text = " ".join(guidance["recovery_steps"])
        self.assertIn("Auxiliary Applications", steps_text)
        self.assertIn("delay_start=true", steps_text)
        self.assertIn("creo_callback_status", steps_text)

    def test_callback_guidance_ready_clears_affected_operations(self):
        guidance = callback_guidance({"readiness": "ready"})
        self.assertEqual(guidance["affected_operations"], [])
        self.assertEqual(guidance["recovery_steps"], [])

    def test_callback_advisory_non_blocking_summary(self):
        not_ready = callback_advisory({"readiness": "not_loaded", "reason": "no_record"})
        self.assertFalse(not_ready["ready_for_direct_loft"])
        self.assertIn("loft (creo_loft)", not_ready["affected_operations"])
        ready = callback_advisory({"readiness": "ready", "reason": None})
        self.assertTrue(ready["ready_for_direct_loft"])
        self.assertEqual(ready["affected_operations"], [])

    def test_creo_callback_status_includes_guidance_and_compact_view(self):
        fake = {
            "readiness": "not_loaded",
            "artifact_status": "prepared",
            "reason": "no_runtime_identity_record",
            "registry_file": "D:/repo/build/blend_callback_protk.dat",
            "persistent_registration_config": "D:/repo/build/blend_callback.config.pro",
            "instruction": "Start in Auxiliary Applications.",
        }
        with (
            patch.object(server.startup, "status", return_value={"coordinator_running": False}),
            patch.object(bridge, "callback_status", return_value=dict(fake)),
        ):
            full_payload = asyncio.run(server.creo_callback_status())
            compact_payload = asyncio.run(server.creo_callback_status(detail="compact"))
        self.assertIn("affected_operations", full_payload)
        self.assertIn("recovery_steps", full_payload)
        self.assertEqual(compact_payload["detail"], "compact")
        self.assertIn("recovery_steps", compact_payload)
        self.assertNotIn("generation_inventory", compact_payload)

    def test_session_and_startup_status_compact_mode(self):
        fake_startup = {
            "state": "panel_session_locked",
            "connected": False,
            "failure_code": "panel_session_locked",
            "panel_session_guard": {"model_id": "mdl_p", "job_id": "job_p", "state": "active"},
            "next_steps": ["Inspect mdl_p first"],
            "history": [{"attempt": i} for i in range(25)],
        }
        fake_session = {
            **fake_startup,
            "mode": "explicit_live",
            "startup": fake_startup,
            "creo_process_snapshot": {"available": True, "processes": [{"pid": 1}, {"pid": 2}]},
        }
        with (
            patch.object(server.startup, "status", return_value=fake_startup),
            patch.object(server.startup, "session_status", return_value=fake_session),
            patch.object(server.startup, "session_keys", return_value={"session_selection": {}}),
        ):
            startup_compact = asyncio.run(server.creo_startup_status(detail="compact"))
            session_compact = asyncio.run(server.creo_session_status(detail="compact"))
        for compact in (startup_compact, session_compact):
            self.assertEqual(compact["detail"], "compact")
            self.assertEqual(compact["panel_session_guard"]["model_id"], "mdl_p")
            self.assertNotIn("history", compact)
            self.assertIn("next_steps", compact)


class Bug205Creo10SurfaceLoftTests(unittest.TestCase):
    def _creo10_identity(self, kernel_completion: str = "unknown") -> dict:
        return {
            "identity_status": "verified",
            "identity_source": "worker_self_report",
            "worker_sha256": "c" * 64,
            "release_numeric": 42,
            "features": {
                "surface_loft": {
                    "available": True,
                    "state": "compiled",
                    "kernel_completion": kernel_completion,
                    "worker_sha256": "c" * 64,
                    "release_numeric": 42,
                },
                "surface_loft_panel": {"available": True, "state": "ready"},
            },
        }

    def test_creo10_refuses_element_tree_with_or_without_accept_unverified_completion(self):
        base = {"op": "surface_loft", "label": "surf_a", "sections": ["s1", "s2"]}
        for op in (base, {**base, "accept_unverified_completion": True}):
            with self.assertRaisesRegex(ValueError, "resident_panel"):
                capabilities.require_kernel_completion([op], self._creo10_identity("unknown"))

    def test_creo10_allows_element_tree_only_if_explicitly_observed_supported(self):
        capabilities.require_kernel_completion(
            [{"op": "surface_loft", "label": "surf_a", "sections": ["s1", "s2"]}],
            self._creo10_identity("supported"),
        )

    def test_compact_capabilities_shows_surface_loft_not_runtime_ready(self):
        payload = server._capabilities_payload([])
        payload["families"] = capabilities.project_worker_availability(
            payload["families"],
            self._creo10_identity(),
            callback_runtime={
                "readiness": "not_loaded",
                "reason": "recorded_application_not_active",
            },
        )
        compact = capability_pages.capabilities_response(lambda: payload, detail="compact")
        sl = compact["families"]["surface_loft"]
        self.assertFalse(sl["runtime_ready"])
        self.assertEqual(sl["runtime_admission"]["status"], "not_ready")


class Bug206SeedMatrixTests(unittest.TestCase):
    def test_list_seeds_discloses_new_part_only_and_missing_5_straight(self):
        listing = seeds.list_seeds()
        self.assertEqual(listing["target_scope"], "new_part_only")
        self.assertFalse(listing["callback_free_route"]["supports_existing_model"])
        pairs = {
            (row["section_count"], row["interpolation"]) for row in listing["verified_combinations"]
        }
        self.assertEqual(
            pairs,
            {
                (2, "straight"),
                (3, "straight"),
                (4, "straight"),
                (6, "straight"),
                (2, "smooth"),
                (3, "smooth"),
                (4, "smooth"),
                (5, "smooth"),
                (6, "smooth"),
            },
        )
        self.assertIn(
            {"section_count": 5, "interpolation": "straight"},
            listing["missing_bundled_combinations"],
        )

    def test_select_seed_refusal_for_5_straight_names_verified_combos_and_creo_loft(self):
        with self.assertRaises(ValueError) as caught:
            seeds.select_seed(5, "straight")
        text = str(caught.exception)
        self.assertIn("2/3/4/6 straight", text)
        self.assertIn("2/3/4/5/6 smooth", text)
        self.assertIn("5/straight is not bundled", text)
        self.assertIn("creo_install_seed_library", text)


class Bug207EllipseSchemaTests(unittest.TestCase):
    def test_coordinates_dimensioning_accepts_ellipse_and_still_rejects_spline(self):
        op = SketchOp.model_validate(
            {
                "op": "sketch",
                "label": "ell_coord",
                "plane": "XY",
                "dimensioning": "coordinates",
                "entities": [
                    {
                        "type": "ellipse",
                        "name": "e1",
                        "center": [15, 20],
                        "x_radius": 25,
                        "y_radius": 10,
                    }
                ],
            }
        )
        self.assertEqual(op.dimensioning, "coordinates")
        with self.assertRaisesRegex(ValueError, "spline"):
            SketchOp.model_validate(
                {
                    "op": "sketch",
                    "label": "spl_coord",
                    "plane": "XY",
                    "dimensioning": "coordinates",
                    "entities": [
                        {"type": "spline", "name": "sp1", "points": [[0, 0], [5, 5], [10, 0]]}
                    ],
                }
            )


class Bug208BooleanBodyIdTests(unittest.TestCase):
    def test_boolean_op_accepts_initial_body_negative_5778_and_rejects_other_negative_ids(self):
        valid = BooleanOp.model_validate(
            {
                "op": "boolean_bodies",
                "label": "u1",
                "method": "union",
                "targets": [{"kind": "body", "id": -5778}],
                "tools": [{"kind": "body", "id": 115}],
            }
        )
        self.assertEqual(valid.targets[0]["id"], -5778)
        for bad_id in (-1, -2, -9999):
            with self.subTest(bad_id=bad_id):
                with self.assertRaisesRegex(ValueError, "negative body IDs"):
                    BooleanOp.model_validate(
                        {
                            "op": "boolean_bodies",
                            "label": "u_bad",
                            "method": "union",
                            "targets": [{"kind": "body", "id": bad_id}],
                            "tools": [{"kind": "body", "id": 115}],
                        }
                    )


class Bug209ContourLimitationTests(unittest.TestCase):
    def test_known_limitations_discloses_tangent_and_intersecting_contours(self):
        by_id = {entry["id"]: entry for entry in capabilities.KNOWN_LIMITATIONS}
        self.assertIn("sketch_tangent_or_intersecting_contours", by_id)
        entry = by_id["sketch_tangent_or_intersecting_contours"]
        self.assertIn("BUG-209", entry["evidence"])

    def test_four_contour_validation_cases(self):
        shared_edge = [
            {"type": "rectangle", "name": "left", "min": [0, 0], "max": [10, 10]},
            {"type": "rectangle", "name": "right", "min": [10, 0], "max": [20, 10]},
        ]
        point_touch = [
            {
                "type": "polyline",
                "name": "t1",
                "points": [[0, 0], [10, 0], [5, 8]],
                "closed": True,
            },
            {
                "type": "polyline",
                "name": "t2",
                "points": [[10, 0], [20, 0], [15, 8]],
                "closed": True,
            },
        ]
        self_intersecting = [
            {
                "type": "polyline",
                "name": "bowtie",
                "points": [[0, 0], [10, 10], [10, 0], [0, 10]],
                "closed": True,
            }
        ]
        for label, entities in (
            ("shared_edge", shared_edge),
            ("point_touch", point_touch),
            ("self_intersecting", self_intersecting),
        ):
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    profile_diagnostics.validate_solid_profile(entities, operation="extrude")

        valid_nested = [
            {"type": "rectangle", "name": "outer", "min": [0, 0], "max": [20, 20]},
            {"type": "rectangle", "name": "inner", "min": [6, 6], "max": [14, 14]},
        ]
        report = profile_diagnostics.validate_solid_profile(valid_nested, operation="extrude")
        self.assertEqual(report["closed_contour_count"], 2)


class Feat095StatusCompactAndPlanBytesTests(unittest.TestCase):
    def test_compact_status_preserves_essential_fields_and_bounds_bytes(self):
        scenarios = {
            "ready": {
                "server_version": "0.50.0",
                "state": "ready",
                "phase": "ready",
                "connected": True,
                "readiness": "ready",
                "retry_allowed": True,
                "next_steps": ["Call modeling tools"],
                "session_health": {"status": "no_failure_observed", "details": ["x" * 2000]},
                "creo_process_snapshot": {
                    "available": True,
                    "processes": [{"pid": i} for i in range(40)],
                },
                "history": [{"attempt": i, "note": "verbose" * 50} for i in range(30)],
            },
            "busy": {
                "server_version": "0.50.0",
                "state": "waiting_for_channel",
                "connected": False,
                "blocking_job_id": "job123",
                "blocking_model_id": "mdl123",
                "blocking_operation": "extrude",
                "retry_after_seconds": 3,
                "busy": {
                    "job_id": "job123",
                    "blocking_job_id": "job123",
                    "blocking_model_id": "mdl123",
                    "blocking_operation": "extrude",
                    "extra_log": "y" * 4000,
                },
            },
            "panel_session_locked": {
                "server_version": "0.50.0",
                "state": "panel_session_locked",
                "failure_code": "panel_session_locked",
                "panel_session_guard": {
                    "model_id": "mdl_guard",
                    "job_id": "job_guard",
                    "state": "active",
                    "verbose_dump": "z" * 4000,
                },
                "next_steps": ["Inspect model_id first", "Confirm panel closed"],
            },
            "timeout": {
                "server_version": "0.50.0",
                "state": "timeout",
                "failure_code": "startup_timeout",
                "terminal_reason": "probe timed out",
                "next_steps": ["Call creo_startup_status(retry=true)"],
                "creo_process_snapshot": {
                    "available": True,
                    "processes": [{"pid": i} for i in range(15)],
                },
                "session_candidates": [{"pid": i, "window": "Creo " * 10} for i in range(10)],
            },
            "not_loaded": {
                "server_version": "0.50.0",
                "readiness": "not_loaded",
                "reason": "no_runtime_identity_record",
                "affected_operations": ["loft (creo_loft)"],
                "recovery_steps": ["Start in Creo Auxiliary Applications"],
                "generation_inventory": {
                    "generation_count": 3,
                    "payload_generation_count": 2,
                    "current_generation_key": "abc",
                    "generations": [{"key": str(i), "files": ["f" * 500]} for i in range(10)],
                },
            },
        }
        for name, payload in scenarios.items():
            with self.subTest(scenario=name):
                full_bytes = len(json.dumps(payload).encode("utf-8"))
                compact = compact_status_response(payload, tool_name="creo_session_status")
                compact_bytes = len(json.dumps(compact).encode("utf-8"))
                self.assertLess(compact_bytes, full_bytes)
                self.assertLess(compact_bytes, 4096)
                self.assertEqual(compact["detail"], "compact")

    def test_twenty_op_plan_serialized_bytes_and_compact_budget(self):
        plan_20 = [
            {
                "op": "sketch",
                "label": f"sk_{i:02d}",
                "plane": {"kind": "datum_plane", "offset": float(i * 5)},
                "entities": [
                    {"type": "rectangle", "name": "r", "corner1": [0, 0], "corner2": [10, 10]}
                ],
            }
            for i in range(20)
        ]
        plan_bytes = len(json.dumps(plan_20).encode("utf-8"))
        self.assertGreater(plan_bytes, 0)
        self.assertLess(plan_bytes, 32768)


if __name__ == "__main__":
    unittest.main()
