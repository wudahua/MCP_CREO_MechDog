"""DEV-051 T11 / FEAT-014 offline contract: bend-end relief for four-wall flanges.

Second-batch T11 takes the T05 failure candidate (185 x 232 x 1 mm base wall plus
four h80 / R2.54 / Y0.5 flanges) and the confirmed T03 thin wall as input. This
module is the offline half: it freezes what the installed Creo 12.4 Toolkit
actually exposes for relief, what the MCP contract admits, what the native tree
must therefore contain, and what geometry a live run has to confirm.

Scope of the offline design:

* one relief shape only -- ``rectangular`` with a caller-supplied blind width and
  depth in model units -- plus the compatibility default ``none``, which keeps
  both bend ends at ``PRO_BEND_RLF_NONE`` exactly as before T11;
* no automatic corner rule and no thickness-derived defaults: rip, stretch,
  obround, param, corner relief, miter cuts and edge rips stay unsupported;
* relief is a creation-time property; the named ``height`` dimension keeps its
  existing edit path and there is no in-place relief redefine.

Nothing here creates a flange. The corner overlap and the relief removal are
independent arithmetic on the T05 geometry, not native measurements.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations
from tests.unit import test_sheetmetal_flange as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE = REPO_ROOT / "native" / "advanced.cpp"
SERVER = REPO_ROOT / "server.py"

# --- Creo 12.4 Toolkit facts, transcribed from the installed SDK -----------
SDK_VERSION = "Creo 12.4.0.0"
SDK_HEADER = "Common Files/protoolkit/includes/ProSmtFlangeWall.h"
# ProBendRlfType (ProSmtFlangeWall.h)
RELIEF_TYPES = {"none": 0, "rip": 1, "stretch": 2, "rectangular": 3, "obround": 4, "param": 5}
# ProBendRlfDepthType, expressed through ProSmdRelType (PRO_DIM_*)
RELIEF_DEPTH_TYPES = {
    "not_used": -1,
    "blind": -4,
    "up_to_bend": -7,
    "tan_to_bend": -8,
    "param": -25,
}
# ProCornerRelType, the sibling compound PRO_E_SMT_CORNER_RELIEF in the same tree
CORNER_RELIEF_TYPES = {
    "v_notch": 0,
    "circular": 1,
    "rectangular": 2,
    "obround": 3,
    "no": 5,
    "param": 6,
    "square": 7,
    "normal": 8,
}
SUPPORTED_RELIEF_TYPES = ("none", "rectangular")
UNSUPPORTED_RELIEF_TYPES = ("rip", "stretch", "obround", "param")
NOT_IMPLEMENTED_CORNER_RULES = ("corner_relief", "miter_cut", "edge_rip")

# SDK notes 5-7 (ProSmtEditBendRelief.h) restate the relief constraints for the
# same elements: width is mandatory and positive for every type except rip,
# depth type is mandatory for the same set and tan-to-bend only fits obround,
# and blind depth is mandatory and measured from the bend edge.
WIDTH_REQUIRED_TYPES = ("stretch", "rectangular", "obround", "param")
DEPTH_TYPE_REQUIRED_TYPES = WIDTH_REQUIRED_TYPES
TAN_TO_BEND_TYPES = ("obround",)


# --- request fixtures -----------------------------------------------------


def flange_op(relief: dict | None = None, **overrides) -> dict:
    op = {
        "op": "sheetmetal_flange",
        "label": "f_px",
        "edge": {"kind": "edge", "id": 211},
        "height": fx.FLANGE_HEIGHT_MM,
        "angle": fx.FLANGE_ANGLE_DEG,
        "radius": fx.FLANGE_RADIUS_MM,
        "flip": False,
        "y_factor": fx.FLANGE_Y_FACTOR,
    }
    if relief is not None:
        op["relief"] = relief
    op.update(overrides)
    return op


def validated(relief: dict | None = None, **overrides) -> dict:
    return validate_operations([flange_op(relief, **overrides)])[0]


def rejected(test: unittest.TestCase, relief: dict | None, needle: str, **overrides):
    with test.assertRaises(Exception) as caught:
        validate_operations([flange_op(relief, **overrides)])
    test.assertIn(needle, str(caught.exception))


def relief_rectangular(width: float, depth: float, ends: str = "both") -> dict:
    payload: dict = {"type": "rectangular", "width": width, "depth": depth}
    if ends != "both":
        payload["ends"] = ends
    return payload


def expected_native_sides(relief: dict | None) -> dict:
    """Independent model of the documented element rules, not production code."""
    if relief is None or relief.get("type", "none") == "none":
        return {"side1": "none", "side2": "none"}
    ends = relief.get("ends", "both")
    enabled = {"both": ("side1", "side2"), "side1": ("side1",), "side2": ("side2",)}[ends]
    return {side: "rectangular" if side in enabled else "none" for side in ("side1", "side2")}


def relief_removed_mm3(relief: dict | None, thickness: float = fx.PLATE_THICKNESS_MM) -> float:
    """A rectangular notch removes width x depth x thickness per enabled bend end."""
    if relief is None or relief.get("type", "none") == "none":
        return 0.0
    ends = 2 if relief.get("ends", "both") == "both" else 1
    return ends * float(relief["width"]) * float(relief["depth"]) * thickness


def corner_overlap_run_mm() -> float:
    """Wall run that shares a corner: height minus the bend radius (T05 bound)."""
    return max(0.0, fx.FLANGE_HEIGHT_MM - fx.FLANGE_RADIUS_MM)


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


# --- SDK evidence ---------------------------------------------------------


class SdkEvidenceTest(unittest.TestCase):
    def test_relief_types_are_the_documented_order(self):
        self.assertEqual(sorted(RELIEF_TYPES.values()), list(range(6)))
        self.assertEqual(RELIEF_TYPES["none"], 0)
        self.assertEqual(RELIEF_TYPES["rectangular"], 3)

    def test_admitted_types_are_a_subset_of_the_sdk_enum(self):
        for name in SUPPORTED_RELIEF_TYPES:
            self.assertIn(name, RELIEF_TYPES)
        for name in UNSUPPORTED_RELIEF_TYPES:
            self.assertIn(name, RELIEF_TYPES)
            self.assertNotIn(name, SUPPORTED_RELIEF_TYPES)

    def test_depth_rule_picks_blind(self):
        self.assertIn("blind", RELIEF_DEPTH_TYPES)
        self.assertNotIn("rectangular", TAN_TO_BEND_TYPES)
        for name in UNSUPPORTED_RELIEF_TYPES:
            if name in ("stretch", "obround", "param"):
                self.assertIn(name, WIDTH_REQUIRED_TYPES)
        self.assertIn("rectangular", DEPTH_TYPE_REQUIRED_TYPES)

    def test_corner_and_miter_families_exist_but_are_out_of_scope(self):
        self.assertEqual(CORNER_RELIEF_TYPES["rectangular"], 2)
        self.assertEqual(CORNER_RELIEF_TYPES["no"], 5)
        self.assertEqual(len(NOT_IMPLEMENTED_CORNER_RULES), 3)


# --- compatibility default -------------------------------------------------


class DefaultCompatibilityTest(unittest.TestCase):
    def test_omitted_relief_keeps_the_old_payload(self):
        dumped = validated()
        self.assertNotIn("relief", dumped)
        self.assertEqual(dumped["flip"], False)
        self.assertEqual(dumped["height"], fx.FLANGE_HEIGHT_MM)
        self.assertEqual(dumped["radius"], fx.FLANGE_RADIUS_MM)
        self.assertEqual(dumped["y_factor"], fx.FLANGE_Y_FACTOR)

    def test_omitted_and_explicit_none_apply_the_same_tree(self):
        self.assertEqual(expected_native_sides(None), {"side1": "none", "side2": "none"})
        dumped = validated({"type": "none"})
        self.assertEqual(dumped["relief"], {"type": "none", "ends": "both"})
        self.assertEqual(expected_native_sides(dumped["relief"]), expected_native_sides(None))

    def test_none_cannot_carry_geometry_or_ends(self):
        rejected(self, {"type": "none", "width": 1.0}, "takes no width or depth")
        rejected(self, {"type": "none", "depth": 1.0}, "takes no width or depth")
        rejected(self, {"type": "none", "ends": "side1"}, "no ends to select")

    def test_default_end_selection_is_both(self):
        dumped = validated(relief_rectangular(1.0, 1.0))
        self.assertEqual(dumped["relief"]["ends"], "both")


# --- admission ------------------------------------------------------------


class ReliefAdmissionTest(unittest.TestCase):
    def test_rectangular_requires_explicit_width_and_depth(self):
        rejected(self, {"type": "rectangular", "width": 1.0}, "requires width")
        rejected(self, {"type": "rectangular", "depth": 1.0}, "requires width")
        rejected(self, {"type": "rectangular"}, "requires width")

    def test_width_is_positive_and_depth_non_negative(self):
        rejected(self, relief_rectangular(0.0, 1.0), "greater than 0")
        rejected(self, relief_rectangular(-1.0, 1.0), "greater than 0")
        rejected(self, relief_rectangular(1.0, -0.5), "greater than or equal to 0")
        dumped = validated(relief_rectangular(1.0, 0.0))
        self.assertEqual(dumped["relief"]["depth"], 0.0)

    def test_values_are_absolute_model_units(self):
        dumped = validated(relief_rectangular(2.5, 0.75))
        self.assertEqual(dumped["relief"]["width"], 2.5)
        self.assertEqual(dumped["relief"]["depth"], 0.75)
        # No thickness multiple is accepted as a substitute for a number.
        rejected(self, {"type": "rectangular", "width": "1t", "depth": 1.0}, "valid number")

    def test_non_finite_and_boolean_values_are_rejected(self):
        rejected(self, {"type": "rectangular", "width": True, "depth": 1.0}, "not booleans")
        rejected(self, {"type": "rectangular", "width": 1.0, "depth": False}, "not booleans")
        rejected(self, {"type": "rectangular", "width": float("inf"), "depth": 1.0}, "finite")

    def test_unknown_keys_are_rejected(self):
        rejected(
            self,
            {"type": "rectangular", "width": 1.0, "depth": 1.0, "corner": "miter"},
            "Extra inputs are not permitted",
        )

    def test_relief_type_is_a_closed_set(self):
        rejected(self, {"type": "tear"}, "Input should be")
        rejected(self, {"type": "auto"}, "Input should be")
        rejected(self, {"type": None}, "Input should be")


class UnsupportedShapeTest(unittest.TestCase):
    def test_other_sdk_shapes_are_named_unsupported_not_mapped_to_none(self):
        for name in UNSUPPORTED_RELIEF_TYPES:
            with self.subTest(shape=name):
                rejected(self, {"type": name}, "Input should be")

    def test_corner_rules_are_not_part_of_the_operation(self):
        for name in NOT_IMPLEMENTED_CORNER_RULES:
            with self.subTest(rule=name):
                rejected(
                    self,
                    {"type": "rectangular", "width": 1.0, "depth": 1.0, "rule": name},
                    "Extra inputs are not permitted",
                )


class EndSelectionTest(unittest.TestCase):
    def test_each_end_selection_maps_to_one_or_two_sides(self):
        cases = {
            "both": {"side1": "rectangular", "side2": "rectangular"},
            "side1": {"side1": "rectangular", "side2": "none"},
            "side2": {"side1": "none", "side2": "rectangular"},
        }
        for ends, expected in cases.items():
            with self.subTest(ends=ends):
                dumped = validated(relief_rectangular(1.0, 1.0, ends))
                self.assertEqual(expected_native_sides(dumped["relief"]), expected)

    def test_unknown_end_selection_is_rejected(self):
        rejected(self, relief_rectangular(1.0, 1.0, "left"), "Input should be")
        rejected(self, relief_rectangular(1.0, 1.0, "both_ends"), "Input should be")


class MaterialSideTest(unittest.TestCase):
    def test_relief_does_not_touch_the_trajectory_normal_control(self):
        for relief in (None, {"type": "none"}, relief_rectangular(1.0, 1.0)):
            with self.subTest(relief=relief):
                self.assertEqual(validated(relief)["flip"], False)
                self.assertEqual(validated(relief, flip=True)["flip"], True)

    def test_relief_has_no_material_side_or_auto_field(self):
        dumped = validated(relief_rectangular(1.0, 1.0))
        self.assertEqual(set(dumped["relief"]), {"type", "ends", "width", "depth"})
        self.assertNotIn("side", dumped["relief"])
        self.assertNotIn("material_side", dumped["relief"])


# --- native element tree --------------------------------------------------


class NativeTreeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = NATIVE.read_text(encoding="utf-8", errors="replace")
        cls.flange = _function_body(cls.source, "static void generic_sheetmetal_flange")
        cls.request = _function_body(cls.source, "static FlangeReliefRequest flange_relief_request")
        cls.side = _function_body(cls.source, "static void flange_relief_side")
        cls.record = _function_body(cls.source, "static J flange_relief_record")

    def test_relief_compound_covers_both_bend_ends(self):
        for token in (
            "PRO_E_SMT_BEND_RELIEF",
            "PRO_E_SMT_BEND_RELIEF_SIDE1",
            "PRO_E_SMT_BEND_RELIEF_SIDE2",
        ):
            self.assertIn(token, self.flange)

    def test_default_tree_is_still_none_on_both_ends(self):
        self.assertIn("PRO_BEND_RLF_NONE", self.side)
        self.assertIn("enabled ? PRO_BEND_RLF_RECTANGULAR : PRO_BEND_RLF_NONE", self.side)

    def test_rectangular_sets_width_depth_type_and_blind_depth(self):
        for token in (
            "PRO_BEND_RLF_RECTANGULAR",
            "PRO_E_BEND_RELIEF_WIDTH",
            "PRO_E_BEND_RELIEF_DEPTH_TYPE",
            "PRO_BEND_RLF_DEPTH_BLIND",
            "PRO_E_BEND_RELIEF_DEPTH",
        ):
            self.assertIn(token, self.side)

    def test_unimplemented_shapes_are_absent_from_the_native_tree(self):
        for token in (
            "PRO_BEND_RLF_RIP",
            "PRO_BEND_RLF_STRETCH",
            "PRO_BEND_RLF_OBROUND",
            "PRO_BEND_RLF_PARAM",
            "PRO_BEND_RLF_DEPTH_TAN_TO_BEND",
            "PRO_E_SMT_CORNER_RELIEF",
            "PRO_E_SMT_MTR_CUTS",
            "PRO_E_SMT_EDGE_RIP",
        ):
            self.assertNotIn(token, self.flange + self.side + self.record)

    def test_relief_length_and_angle_stay_unset(self):
        # Neither the flange feature mapping nor the SDK require a length for a
        # rectangular notch; leaving them unset is deliberate and is one of the
        # items a live creation has to confirm.
        for token in ("PRO_E_BEND_RELIEF_LENGTH", "PRO_E_BEND_RELIEF_ANGLE"):
            self.assertNotIn(token, self.side)

    def test_request_is_validated_before_any_element_is_built(self):
        self.assertLess(
            self.flange.index("flange_relief_request(op)"),
            self.flange.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        )

    def test_parent_body_stays_implicit(self):
        self.assertNotIn("PRO_E_BODY", self.flange + self.side + self.record)

    def test_unknown_type_and_ends_throw_instead_of_falling_back(self):
        self.assertIn("Unsupported sheetmetal flange relief type", self.request)
        self.assertIn("relief ends must be both, side1 or side2", self.request)
        self.assertIn("requires width and depth", self.request)

    def test_record_reports_measured_thickness_and_request_arithmetic(self):
        for token in (
            "ProSmtPartThicknessValueGet",
            '"part_thickness_mm"',
            '"corner_overlap_run_mm"',
            '"width_at_least_thickness"',
            '"depth_covers_corner_run"',
        ):
            self.assertIn(token, self.record)
        self.assertIn('op.contains("relief")', self.flange)

    def test_record_is_only_written_when_relief_was_requested(self):
        self.assertIn('extra["relief"] = flange_relief_record(op, relief_request)', self.flange)
        self.assertIn('if (op.contains("relief") && !op.at("relief").is_null())', self.flange)


# --- geometry -------------------------------------------------------------


class ReliefGeometryTest(unittest.TestCase):
    def test_a_rectangular_notch_removes_width_by_depth_by_thickness(self):
        self.assertAlmostEqual(relief_removed_mm3(relief_rectangular(2.0, 3.0)), 12.0, places=6)
        self.assertAlmostEqual(
            relief_removed_mm3(relief_rectangular(2.0, 3.0, "side1")), 6.0, places=6
        )
        self.assertEqual(relief_removed_mm3(None), 0.0)

    def test_thickness_scale_relief_does_not_cover_the_corner_run(self):
        run = corner_overlap_run_mm()
        self.assertAlmostEqual(run, 77.46, places=6)
        relief = relief_rectangular(fx.PLATE_THICKNESS_MM, fx.PLATE_THICKNESS_MM)
        self.assertLess(relief["depth"], run)

    def test_corner_run_profile_reaches_the_shared_corner(self):
        run = corner_overlap_run_mm()
        relief = relief_rectangular(fx.PLATE_THICKNESS_MM, run)
        self.assertGreaterEqual(relief["depth"], run)
        self.assertAlmostEqual(relief_removed_mm3(relief), 2 * 1.0 * run * 1.0, places=6)

    def test_four_wall_volume_expectation_with_relief(self):
        spans = [232.0, 232.0, 185.0, 185.0]
        relief = relief_rectangular(1.0, 1.0)
        walls = sum(fx.wall_volume_mm3(span) for span in spans)
        removed = sum(relief_removed_mm3(relief) for _ in spans)
        self.assertAlmostEqual(walls, 66_720.0, places=6)
        self.assertAlmostEqual(removed, 8.0, places=6)
        self.assertAlmostEqual(fx.PLATE_VOLUME_MM3 + walls - removed, 109_632.0, places=6)

    def test_corner_overlap_bound_is_unchanged_by_the_contract(self):
        self.assertAlmostEqual(fx.corner_overlap_volume_mm3(1), 77.46, places=6)
        self.assertAlmostEqual(fx.corner_overlap_volume_mm3(2), 154.92, places=6)


class FourWallReliefPlanTest(unittest.TestCase):
    def test_reported_four_wall_plan_still_validates_with_relief(self):
        inspection = fx.box_inspection()
        operations = [fx.wall_sketch(), fx.wall_base_op()]
        for side, label in fx.FLANGE_SEQUENCE:
            reference = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="top")
            operation = fx.flange_op(side, label, reference)
            operation["relief"] = relief_rectangular(1.0, 1.0)
            operations.append(operation)
        dumped = validate_operations(operations)
        self.assertEqual(len(dumped), 6)
        flanges = [item for item in dumped if item["op"] == "sheetmetal_flange"]
        self.assertEqual(len(flanges), 4)
        for item in flanges:
            self.assertEqual(
                expected_native_sides(item["relief"]),
                {"side1": "rectangular", "side2": "rectangular"},
            )

    def test_legacy_plan_without_relief_is_unchanged(self):
        operations, _ = fx.four_wall_plan(fx.box_inspection())
        dumped = validate_operations(operations)
        self.assertTrue(all("relief" not in item for item in dumped))


# --- edit path ------------------------------------------------------------


class EditPathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = NATIVE.read_text(encoding="utf-8", errors="replace")
        cls.flange = _function_body(cls.native, "static void generic_sheetmetal_flange")
        cls.server = SERVER.read_text(encoding="utf-8", errors="replace")

    def test_height_dimension_and_section_path_survive(self):
        self.assertIn('{"name", "height"}', self.flange)
        self.assertIn('extra["section_path"]', self.flange)

    def test_relief_is_creation_time_only(self):
        self.assertNotIn("ProFeatureRedefine", self.flange)
        self.assertNotIn("ProElemtreeElementModify", self.flange)
        self.assertIn("fixed when the flange", self.server)
        self.assertIn("deleting/re-creating the flange", self.server)

    def test_tool_exposes_relief_as_an_optional_parameter(self):
        self.assertIn("relief: Annotated[", self.server)
        self.assertIn('operation["relief"] = relief', self.server)
        self.assertIn("relief is not None", self.server)

    def test_tool_description_states_the_supported_subset(self):
        for token in ("'none'|'rectangular'", "Rip/stretch/obround/param", "miter cuts"):
            self.assertIn(token, self.server)


if __name__ == "__main__":
    unittest.main()
