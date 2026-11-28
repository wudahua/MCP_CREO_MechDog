"""DEV-098: receipt semantics for partial profiles and quilt closure.

The tests pin two reading rules the 0.33.0 feedback needed: a partial analytic
profile is a lower bound, and a quilt closure block answers none of "is the
boundary closed" / "can solidify consume it".
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog.diagnostic_semantics import (
    closure_semantics,
    closure_volume_state,
    describe_profile_consistency,
)
from creo_mechdog.profile_diagnostics import analyze_profile

ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES = ROOT / "src" / "creo_mechdog" / "capabilities.py"


def cap_entity(name: str, left: bool) -> dict:
    points = [[0, -460], [60, -460], [181, -469], [54, -660], [0, -660]]
    if not left:
        points = [[-x, y] for x, y in points]
    return {
        "type": "b_spline",
        "name": name,
        "degree": 3,
        "control_points": points,
        "knots": [0, 0, 0, 0, 0.45, 1, 1, 1, 1],
    }


def native_section(**overrides) -> dict:
    block = {
        "available": True,
        "entities": 2,
        "contours": 1,
        "closed_contours": 1,
        "open_ends": 0,
    }
    block.update(overrides)
    return block


class ProfileConsistencyTests(unittest.TestCase):
    def test_complete_and_equal_counts_are_consistent(self):
        profile = {
            "analysis": "complete",
            "entity_count": 4,
            "contour_count": 1,
            "closed_contour_count": 1,
            "categories": {"unsupported": 0},
        }
        result = describe_profile_consistency(profile, native_section(entities=4))
        self.assertTrue(result["available"])
        self.assertTrue(result["consistent"])
        self.assertEqual(result["differences"], [])
        self.assertEqual(len(result["compared"]), 3)

    def test_complete_mismatch_reports_the_exact_fields(self):
        profile = {
            "analysis": "complete",
            "entity_count": 4,
            "contour_count": 1,
            "closed_contour_count": 0,
            "categories": {},
        }
        result = describe_profile_consistency(profile, native_section(entities=4))
        self.assertFalse(result["consistent"])
        self.assertEqual(
            [item["field"] for item in result["differences"]], ["closed_contour_count"]
        )

    def test_two_b_splines_are_partial_not_a_contradiction(self):
        report = analyze_profile([cap_entity("cap_l", True), cap_entity("cap_r", False)])
        self.assertEqual(report["analysis"], "partial")
        self.assertEqual(report["entity_count"], 0)
        result = describe_profile_consistency(report, native_section())
        self.assertTrue(result["available"])
        self.assertIsNone(result["consistent"])
        self.assertEqual(result["reason"], "analytic_analysis_partial")
        self.assertEqual(result["unsupported_count"], 2)
        self.assertIn("lower bound", result["note"])
        self.assertEqual(result["differences"], [])

    def test_public_projection_count_form_is_accepted(self):
        profile = {
            "analysis": "partial",
            "entity_count": 0,
            "contour_count": 0,
            "closed_contour_count": 0,
            "categories": {"unsupported": 2},
        }
        result = describe_profile_consistency(profile, native_section())
        self.assertEqual(result["unsupported_count"], 2)
        self.assertIsNone(result["consistent"])

    def test_missing_or_unavailable_native_section_is_unknown(self):
        complete = {"analysis": "complete", "entity_count": 1, "categories": {}}
        self.assertIsNone(describe_profile_consistency(complete)["consistent"])
        unavailable = describe_profile_consistency(complete, native_section(available=False))
        self.assertIsNone(unavailable["consistent"])
        self.assertIn("unavailable", unavailable["reason"])

    def test_missing_profile_is_not_consistency(self):
        result = describe_profile_consistency(None, native_section())
        self.assertFalse(result["available"])
        self.assertIsNone(result["consistent"])


def closure(reason: str | None, query_code: int, available: bool = False) -> dict:
    return {"available": available, "reason": reason, "query_code": query_code}


class ClosureVolumeStateTests(unittest.TestCase):
    def test_native_reasons_map_to_three_states(self):
        cases = (
            (closure(None, 0, True), "available"),
            (closure("quilt_is_open", -18), "open"),
            (closure("quilt_volume_eval_failed", -62), "failed"),
            (closure("unit_scale_unknown", 0), "unknown"),
            (None, "unknown"),
        )
        for block, expected in cases:
            with self.subTest(block=block):
                self.assertEqual(closure_volume_state(block), expected)

    def test_available_flag_without_reason_is_available(self):
        self.assertEqual(closure_volume_state({"available": True, "query_code": 0}), "available")

    def test_failed_volume_query_does_not_deny_solidify(self):
        semantics = closure_semantics(
            closure("quilt_volume_eval_failed", -62),
            solidify={"execution_status": "succeeded", "effect_status": "committed"},
        )
        self.assertEqual(semantics["volume_state"], "failed")
        self.assertTrue(semantics["solidifiable"])
        self.assertEqual(semantics["solidifiable_basis"], "solidify.effect_status")
        self.assertIsNone(semantics["topologically_closed"])
        self.assertEqual(semantics["topologically_closed_basis"], "not_measured")
        self.assertTrue(
            any("solidifiability" in note or "topological" in note for note in semantics["notes"])
        )

    def test_single_fill_face_volume_is_not_topology(self):
        semantics = closure_semantics(closure(None, 0, True))
        self.assertEqual(semantics["volume_state"], "available")
        self.assertIsNone(semantics["topologically_closed"])
        self.assertIsNone(semantics["solidifiable"])

    def test_group_boundary_is_the_topology_source(self):
        semantics = closure_semantics(
            closure("quilt_volume_eval_failed", -62),
            group={"state": "closed", "boundary_closed": False},
        )
        self.assertFalse(semantics["topologically_closed"])
        self.assertEqual(semantics["topologically_closed_basis"], "surface_group.boundary_closed")

    def test_rolled_back_solidify_is_not_solidifiable(self):
        semantics = closure_semantics(
            closure("quilt_is_open", -18),
            solidify={"execution_status": "failed", "effect_status": "rolled_back"},
        )
        self.assertFalse(semantics["solidifiable"])

    def test_unknown_never_becomes_true(self):
        semantics = closure_semantics(closure("unit_scale_unknown", 0))
        self.assertIsNone(semantics["topologically_closed"])
        self.assertIsNone(semantics["solidifiable"])
        self.assertEqual(semantics["volume_state"], "unknown")


class DocumentationContractTests(unittest.TestCase):
    def test_reference_syntax_documents_all_five_items(self):
        text = (ROOT / "docs" / "REFERENCE_SYNTAX.md").read_text(encoding="utf-8")
        for phrase in (
            "零匹配边选择器的诊断范围（DEV-098）",
            "quilt closure 的三种含义（DEV-098）",
            "已验证的分步曲面路径：开放壳体封口并实体化（DEV-098 引用）",
            '`analysis="partial"`',
            "native_section",
            "quilt_volume_eval_failed",
            "54,905,286.63066032",
            'dimensioning="coordinates"',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_compatibility_documents_semantics_and_provenance(self):
        text = (ROOT / "docs" / "COMPATIBILITY.md").read_text(encoding="utf-8")
        for phrase in (
            "2026-11-21：DEV-098",
            "hidden_only",
            "visible_hung_window_observed",
            "quilt_is_open",
            "quilt_volume_eval_failed",
            "creo_mechdog.diagnostic_semantics",
            "外部 Creo 10",
            "nearest_surfaces",
            "requested_coordinate_space",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_capabilities_name_the_limits_and_b_spline_coordinates_exclusion(self):
        text = CAPABILITIES.read_text(encoding="utf-8")
        for phrase in (
            "spline uses autodim",
            "sketch_profile_partial_counts",
            "quilt_closure_not_solidifiable",
            "hidden_hung_window_scope",
            "edge_selector_nearest_scope",
            "surface_selector_nearest_scope",
            "native_section",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class NearestEdgeDiagnosticTests(unittest.TestCase):
    """DEV-098: a zero-match edge selector lists candidates but never chooses one."""

    def source(self) -> str:
        return (ROOT / "native" / "geometry_selectors.cpp").read_text(encoding="utf-8")

    def test_zero_match_branch_publishes_a_bounded_nearest_list(self):
        text = " ".join(self.source().split())
        self.assertIn("selector_nearest_edges(selector, state, mm_scale, form)", text)
        self.assertIn('outcome.diagnostic["nearest_edges"]', text)
        self.assertIn("if (rows.size() > 5)", text)
        self.assertIn("never selected automatically", text)

    def test_nearest_list_never_becomes_the_match(self):
        text = " ".join(self.source().split())
        # edge once, surface twice (chosen face and unique match)
        self.assertEqual(text.count("outcome.matched = true"), 3)
        self.assertNotIn('nearest_edges"]; outcome.id', text)

    def test_compact_projection_keeps_the_diagnostic_block(self):
        from creo_mechdog.compact_sections import OPERATION_KEYS

        self.assertIn("geometry_selector_diagnostic", OPERATION_KEYS)
        caps = CAPABILITIES.read_text(encoding="utf-8")
        self.assertIn("geometry_selector_diagnostic.nearest_edges", caps)
        text = (ROOT / "docs" / "REFERENCE_SYNTAX.md").read_text(encoding="utf-8")
        self.assertIn("geometry_selector_diagnostic.nearest_edges", text)
        self.assertIn("geometry_selector_diagnostic.nearest_surfaces", text)


class NearestSurfaceDiagnosticTests(unittest.TestCase):
    """DEV-098: a zero-match surface selector lists candidates but never chooses one."""

    def source(self) -> str:
        return (ROOT / "native" / "geometry_selectors.cpp").read_text(encoding="utf-8")

    def test_zero_match_surface_branch_publishes_a_bounded_list(self):
        text = " ".join(self.source().split())
        self.assertIn("selector_nearest_surfaces(selector, state, mm_scale)", text)
        self.assertIn('outcome.diagnostic["nearest_surfaces"]', text)
        self.assertIn("if (rows.size() > 5)", text)
        self.assertIn("never selected automatically", text)

    def test_surface_list_stays_a_diagnostic(self):
        text = " ".join(self.source().split())
        self.assertIn("if (matches.empty())", text)
        self.assertNotIn('nearest_surfaces"]; outcome.id', text)
        # The list only measures nameable faces; wrong-type ones stay in
        # type_rejected_ids instead of being repeated as candidates.
        self.assertIn("cylinder_only && !cylinder", text)

    def test_assembly_space_provenance_is_kept(self):
        text = " ".join((ROOT / "native" / "generic.cpp").read_text(encoding="utf-8").split())
        self.assertIn(
            'selector_outcome.diagnostic["requested_coordinate_space"] = "assembly"', text
        )


if __name__ == "__main__":
    unittest.main()
