"""Offline contract checks for the single native custom-hole path."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from creo_mechdog.schema import validate_operations

ROOT = Path(__file__).resolve().parents[2]
PLATE_VOLUME = 50.0 * 50.0 * 10.0
BASE = {
    "op": "hole",
    "label": "hole_one",
    "placement": {"kind": "surface", "id": 1},
    "reference1": {"kind": "datum_plane", "id": 2},
    "reference2": {"kind": "datum_plane", "id": 3},
    "diameter": 6,
}


def oracle_removed(diameter: float, depth: float, option: dict) -> float:
    """Flat-bottom analytical reference for a fully embedded hole in a plate.

    ``depth`` is the overall drill depth measured from the placement face
    (contract semantics); pass the material thickness for a through hole.
    A conical drill tip below that depth is not included here, see
    :func:`oracle_tip_extra`.
    """
    base = math.pi * diameter**2 * depth / 4
    if "counterbore" in option:
        bore = option["counterbore"]
        return base + math.pi * (bore["diameter"] ** 2 - diameter**2) * bore["depth"] / 4
    if "countersink" in option:
        sink = option["countersink"]
        height = (sink["diameter"] - diameter) / (2 * math.tan(math.radians(sink["angle"] / 2)))
        outer = (
            math.pi
            * height
            * (sink["diameter"] ** 2 + sink["diameter"] * diameter + diameter**2)
            / 12
        )
        return base + outer - math.pi * diameter**2 * height / 4
    return base


def oracle_tip_extra(diameter: float, angle: float = 118.0) -> float:
    """Volume below the flat depth if the drill end is a conical tip."""
    radius = diameter / 2.0
    height = radius / math.tan(math.radians(angle / 2.0))
    return math.pi * radius * radius * height / 3.0


def oracle_faces(option: dict, blind: bool) -> int:
    """Faces added over a 6-face plate: bore wall, flat bottom, seat, sink cone."""
    delta = 1
    if blind:
        delta += 1
    if "counterbore" in option:
        delta += 2
    if "countersink" in option:
        delta += 1
    return delta


def oracle_variants(diameter: float, depth: float, option: dict) -> dict:
    """Named removable-volume references; the contract one is judged.

    ``contract_flat_overall`` is the frozen contract (flat bottom, ``depth``
    overall from the placement face). The others diagnose native semantics
    that are not yet verified and never pass a case on their own: a 118-degree
    drill tip below the flat depth, or a counterbore whose drill depth is
    counted from the seat ("till shoulder") instead of the placement face.
    """
    flat = oracle_removed(diameter, depth, option)
    variants = {
        "contract_flat_overall": flat,
        "drill_tip_118_below_depth": flat + oracle_tip_extra(diameter),
    }
    if "counterbore" in option:
        bore = option["counterbore"]
        variants["shoulder_measured_drilldepth"] = (
            math.pi * bore["diameter"] ** 2 * bore["depth"] / 4 + math.pi * diameter**2 * depth / 4
        )
    return variants


def closest_variant(removed: float, variants: dict, tol: float = 1.0) -> str | None:
    """Which named variant the measured removal matches, or None."""
    best = min(variants, key=lambda name: abs(removed - variants[name]))
    return best if abs(removed - variants[best]) <= tol else None


def face_count(snapshot: dict) -> int | None:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    surfaces = inspection.get("surfaces")
    return len(surfaces) if isinstance(surfaces, list) else None


def cylinder_surfaces(snapshot: dict, radius: float, tol: float = 1e-3) -> list:
    """Inspection surface records that are cylinders of the given radius."""
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    found = []
    for item in inspection.get("surfaces") or []:
        if isinstance(item, dict) and isinstance(item.get("radius"), (int, float)):
            if abs(item["radius"] - radius) <= tol:
                found.append(item)
    return found


def axis_is_parallel(vector, normal, tol: float = 1e-3) -> bool:
    """True when the two directions are parallel or antiparallel."""

    def unit(values) -> list | None:
        if not isinstance(values, list) or len(values) != 3:
            return None
        length = math.sqrt(sum(float(v) ** 2 for v in values))
        if length < 1e-12:
            return None
        return [float(v) / length for v in values]

    a, b = unit(vector), unit(normal)
    if a is None or b is None:
        return False
    return abs(abs(sum(x * y for x, y in zip(a, b))) - 1.0) <= tol


def hole_dimensions(snapshot: dict, label: str) -> list:
    """Dimension records of the feature registered under ``label``."""
    aliases = snapshot.get("aliases") if isinstance(snapshot.get("aliases"), dict) else {}
    entry = aliases.get(label)
    feature_id = entry.get("feature_id") if isinstance(entry, dict) else None
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    for feature in inspection.get("features") or []:
        if isinstance(feature, dict) and feature.get("id") == feature_id:
            dims = feature.get("dimensions")
            return dims if isinstance(dims, list) else []
    return []


def missing_dimension_values(dims, expected: dict, tol: float = 1e-3) -> list:
    """Roles whose value is not covered by any dimension of the feature."""
    values = [
        float(dim["value"])
        for dim in dims or []
        if isinstance(dim, dict) and isinstance(dim.get("value"), (int, float))
    ]
    missing = []
    for role, value in expected.items():
        if not any(abs(item - float(value)) <= tol for item in values):
            missing.append(f"{role}={value}")
    return missing


class NativeCountersinkTest(unittest.TestCase):
    def test_old_hole_payload_is_unchanged(self):
        self.assertEqual(
            validate_operations([BASE])[0], {**BASE, "offset1": 0, "offset2": 0, "flip": False}
        )
        self.assertNotIn("depth", validate_operations([BASE])[0])

    def test_each_option_and_plan(self):
        for option in (
            {"counterbore": {"diameter": 10, "depth": 2}},
            {"countersink": {"diameter": 10, "angle": 90}},
        ):
            with self.subTest(option=option):
                op = validate_operations([{**BASE, "depth": 12, **option}])[0]
                self.assertEqual(op[next(iter(option))], next(iter(option.values())))
                self.assertGreater(oracle_removed(6, 12, option), math.pi * 6**2 * 12 / 4)

    def test_invalid_combinations(self):
        cases = [
            {
                "counterbore": {"diameter": 10, "depth": 2},
                "countersink": {"diameter": 10, "angle": 90},
            },
            {"counterbore": {"diameter": 6, "depth": 2}},
            {"counterbore": {"diameter": 10, "depth": 12}, "depth": 12},
            {"counterbore": {"diameter": 10, "depth": 6}, "depth": 6},
            {"countersink": {"diameter": 6, "angle": 90}},
            {"countersink": {"diameter": 10, "angle": 0}},
            {"countersink": {"diameter": 10, "angle": 180}},
            {"countersink": {"diameter": 10, "angle": 10}, "depth": 2},
            {"countersink": {"diameter": 10, "angle": 90}, "depth": 2},
        ]
        for extra in cases:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_operations([{**BASE, **extra}])

    def test_blind_depth_and_flip_payload(self):
        blind = validate_operations([{**BASE, "depth": 7}])[0]
        self.assertEqual(blind["depth"], 7)
        flipped = validate_operations([{**BASE, "flip": True}])[0]
        self.assertIs(flipped["flip"], True)
        self.assertIs(validate_operations([BASE])[0]["flip"], False)
        for option in (
            {"depth": 8, "counterbore": {"diameter": 10, "depth": 2}},
            {"depth": 8, "countersink": {"diameter": 10, "angle": 90}},
        ):
            with self.subTest(option=option):
                op = validate_operations([{**BASE, **option}])[0]
                self.assertEqual(op["depth"], 8)
                self.assertEqual(op[next(iter(option))], option[next(iter(option))])

    def test_blind_and_edit_oracles(self):
        blind = oracle_removed(6, 7, {})
        self.assertAlmostEqual(blind, math.pi * 36 * 7 / 4, places=9)
        self.assertAlmostEqual(blind, 197.92033717615698, places=6)
        cbore = oracle_removed(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        self.assertAlmostEqual(cbore, math.pi * 100 * 2 / 4 + math.pi * 36 * 6 / 4, places=9)
        self.assertAlmostEqual(cbore, 326.7256359733385, places=6)
        sink = oracle_removed(6, 8, {"countersink": {"diameter": 10, "angle": 90}})
        sink_parts = math.pi * 2 * (10**2 + 10 * 6 + 6**2) / 12 + math.pi * 36 * 6 / 4
        self.assertAlmostEqual(sink, sink_parts, places=9)
        self.assertAlmostEqual(sink, 272.2713633111154, places=6)
        edited = oracle_removed(7, 8, {"counterbore": {"diameter": 10, "depth": 3}})
        self.assertAlmostEqual(edited, math.pi * 100 * 3 / 4 + math.pi * 49 * 5 / 4, places=9)
        self.assertAlmostEqual(edited, 428.0419990516093, places=6)

    def test_face_deltas_and_variants(self):
        self.assertEqual(oracle_faces({}, blind=False), 1)
        self.assertEqual(oracle_faces({}, blind=True), 2)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, False), 3)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, True), 4)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, False), 2)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, True), 3)
        option = {"counterbore": {"diameter": 10, "depth": 2}}
        variants = oracle_variants(6, 8, option)
        self.assertEqual(
            set(variants),
            {
                "contract_flat_overall",
                "drill_tip_118_below_depth",
                "shoulder_measured_drilldepth",
            },
        )
        self.assertGreater(oracle_tip_extra(6), 0)
        self.assertAlmostEqual(
            variants["drill_tip_118_below_depth"],
            variants["contract_flat_overall"] + oracle_tip_extra(6),
            places=9,
        )
        self.assertGreater(
            variants["shoulder_measured_drilldepth"], variants["contract_flat_overall"]
        )
        self.assertEqual(
            closest_variant(variants["contract_flat_overall"], variants, tol=1e-6),
            "contract_flat_overall",
        )
        self.assertIsNone(closest_variant(-5.0, variants, tol=1e-6))

    def test_geometry_and_dimension_helpers(self):
        self.assertTrue(axis_is_parallel([0, 0, 10], [0, 0, -1]))
        self.assertFalse(axis_is_parallel([0, 0, 1], [1, 0, 0]))
        self.assertFalse(axis_is_parallel([0, 0, 0], [1, 0, 0]))
        snapshot = {
            "aliases": {"hole_one": {"feature_id": 9}},
            "inspection": {
                "features": [{"id": 9, "dimensions": [{"id": 5, "value": 6.0}]}],
                "surfaces": [{"id": 1, "radius": 3.0}, {"id": 2, "normal": [0, 0, 1]}],
            },
        }
        self.assertEqual(face_count(snapshot), 2)
        self.assertEqual(len(cylinder_surfaces(snapshot, 3.0)), 1)
        self.assertEqual(
            hole_dimensions(snapshot, "hole_one"),
            snapshot["inspection"]["features"][0]["dimensions"],
        )
        self.assertEqual(hole_dimensions(snapshot, "other"), [])
        dims = [{"id": 1, "value": 6.0}, {"id": 2, "value": 7.0}]
        self.assertEqual(missing_dimension_values(dims, {"diameter": 6, "depth": 7}), [])
        self.assertEqual(missing_dimension_values(dims, {"diameter": 6, "depth": 8}), ["depth=8"])

    def test_judge_geometry_separates_oracles(self):
        from tools.test_native_countersink import judge_geometry

        removed = oracle_removed(6, 7, {})
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, -1], "bbox": [[22, 22, 3], [28, 28, 10]]}
        ]
        surfaces += [{"id": 10 + i, "normal": [0, 0, 1]} for i in range(7)]
        after = {
            "aliases": {"blind_hole": {"feature_id": 9}},
            "inspection": {
                "volume_mm3": PLATE_VOLUME - removed,
                "features": [
                    {
                        "id": 9,
                        "type_name": "hole",
                        "dimensions": [{"id": 1, "value": 6.0}, {"id": 2, "value": 7.0}],
                    }
                ],
                "surfaces": surfaces,
            },
        }
        entry = {"base_volume_mm3": PLATE_VOLUME, "base_faces": 6, "base_features": {}}
        terminal = {"result": {"operations": [], "saved_file_reloaded_and_verified": True}}
        variants = oracle_variants(6, 7, {})
        fields, problems = judge_geometry(
            entry,
            terminal,
            after,
            label="blind_hole",
            expected_removed=removed,
            expected_face_delta=oracle_faces({}, blind=True),
            expected_dims={"diameter": 6, "depth": 7},
            variants=variants,
            cylinder_expectations=[
                {
                    "radius": 3.0,
                    "axis_normal": [0, 0, 1],
                    "bbox_axis": 2,
                    "bbox_range": (3.0, 10.0),
                    "bbox_center": {0: 25.0, 1: 25.0},
                }
            ],
        )
        self.assertEqual(problems, [])
        self.assertEqual(fields["matched_variant"], "contract_flat_overall")
        # a volume that matches the drill-tip variant instead never passes
        wrong = json.loads(json.dumps(after))
        wrong["inspection"]["volume_mm3"] = PLATE_VOLUME - variants["drill_tip_118_below_depth"]
        _, problems = judge_geometry(
            entry,
            terminal,
            wrong,
            label="blind_hole",
            expected_removed=removed,
            expected_face_delta=oracle_faces({}, blind=True),
            expected_dims={"diameter": 6, "depth": 7},
            variants=variants,
            cylinder_expectations=[],
        )
        self.assertTrue(any("contract flat-bottom oracle" in item for item in problems))
        # missing reload evidence is a failure, not a silent pass
        _, problems = judge_geometry(
            entry,
            {"result": {"operations": []}},
            after,
            label="blind_hole",
            expected_removed=removed,
            expected_face_delta=oracle_faces({}, blind=True),
            expected_dims={"diameter": 6, "depth": 7},
            variants=variants,
            cylinder_expectations=[],
        )
        self.assertIn("saved_file_reloaded_and_verified is not true", problems)

    def test_native_tree_is_one_hole_and_old_branch_remains(self):
        source = (ROOT / "native/generic.cpp").read_text(encoding="utf-8")
        start = source.index("static J generic_hole(")
        end = source.index("static J ", start + 1)
        body = source[start:end]
        self.assertEqual(body.count("PRO_FEAT_HOLE"), 1)
        self.assertIn("PRO_HLE_CUSTOM_TYPE", body)
        self.assertIn("PRO_HLE_NEW_TYPE_STRAIGHT", body)
        for name in (
            "PRO_E_HLE_ADD_CBORE",
            "PRO_E_HLE_ADD_CSINK",
            "PRO_E_HLE_CBOREDIAM",
            "PRO_E_HLE_CBOREDEPTH",
            "PRO_E_HLE_CSINKDIAM",
            "PRO_E_HLE_CSINKANGLE",
            "PRO_E_HLE_DRILLDEPTH",
            "PRO_E_HLE_DEPTH",
        ):
            self.assertIn(name, body)
        self.assertEqual(body.count("ProFeature f = create(root)"), 1)


class CaseSelectionTests(unittest.TestCase):
    """The default live run must cover exactly the six remainder cases.

    The three cases accepted on 2026-10-29 must not be selectable through the
    remainder selector, so a rerun can never be mistaken for the new
    acceptance set.
    """

    def test_the_default_selection_is_the_six_remainder_cases(self):
        from tools.test_native_countersink import REMAINDER_CASES, resolve_case_selection

        selection = resolve_case_selection(None)
        self.assertEqual(len(selection), 6)
        self.assertEqual(selection, list(REMAINDER_CASES))
        self.assertEqual(
            selection,
            [
                "blind_straight",
                "blind_counterbore",
                "blind_countersink",
                "direction_side_normal",
                "direction_flip_guard",
                "edit_dimension_values",
            ],
        )

    def test_the_accepted_cases_are_not_selectable(self):
        from tools.test_native_countersink import resolve_case_selection

        for name in ("cbore_flat_seat", "csink_90", "countersink_180_contract"):
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    resolve_case_selection([name])

    def test_an_unknown_case_is_refused(self):
        from tools.test_native_countersink import resolve_case_selection

        with self.assertRaises(ValueError):
            resolve_case_selection(["not_a_case"])

    def test_a_repeated_case_is_refused(self):
        from tools.test_native_countersink import resolve_case_selection

        with self.assertRaises(ValueError):
            resolve_case_selection(["blind_straight", "blind_straight"])

    def test_a_narrowed_selection_keeps_the_run_order(self):
        from tools.test_native_countersink import resolve_case_selection

        selection = resolve_case_selection(["edit_dimension_values", "blind_straight"])
        self.assertEqual(selection, ["blind_straight", "edit_dimension_values"])


class RemainderExpectationTests(unittest.TestCase):
    """The six remainder cases keep their frozen oracles and expectations."""

    def test_the_blind_depth_is_overall_from_the_placement_face(self):
        # depth is the overall drill depth measured from the placement face;
        # the flat-bottom oracle uses it as such.
        blind = oracle_removed(6, 7, {})
        self.assertAlmostEqual(blind, math.pi * 36 * 7 / 4, places=9)

    def test_the_three_blind_variants_keep_their_expected_volumes(self):
        self.assertAlmostEqual(oracle_removed(6, 7, {}), 197.92033717615698, places=6)
        self.assertAlmostEqual(
            oracle_removed(6, 8, {"counterbore": {"diameter": 10, "depth": 2}}),
            326.7256359733385,
            places=6,
        )
        self.assertAlmostEqual(
            oracle_removed(6, 8, {"countersink": {"diameter": 10, "angle": 90}}),
            272.2713633111154,
            places=6,
        )

    def test_the_face_deltas_match_the_three_blind_variants(self):
        self.assertEqual(oracle_faces({}, blind=True), 2)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, blind=True), 4)
        self.assertEqual(
            oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, blind=True), 3
        )

    def test_the_edit_case_keeps_its_post_edit_oracle(self):
        edited = oracle_removed(7, 8, {"counterbore": {"diameter": 10, "depth": 3}})
        self.assertAlmostEqual(edited, 428.0419990516093, places=6)


if __name__ == "__main__":
    unittest.main()
