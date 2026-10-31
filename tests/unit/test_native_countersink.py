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


def oracle_tip_height(diameter: float, angle: float = 118.0) -> float:
    """Height of the conical drill point below the flat bottom of the bore."""
    radius = diameter / 2.0
    return radius / math.tan(math.radians(angle / 2.0))


def oracle_tip_extra(diameter: float, angle: float = 118.0) -> float:
    """Volume below the flat depth if the drill end is a conical tip."""
    radius = diameter / 2.0
    height = oracle_tip_height(diameter, angle)
    return math.pi * radius * radius * height / 3.0


def oracle_faces(option: dict, blind: bool) -> int:
    """Faces the contract hole adds to the plate.

    Every revolved surface of a native hole arrives as two seam-split half
    faces (the seam lies in the plane through the hole axis), so the bore
    wall, the seat wall and the sink cone each count twice. A flat bottom
    and a seat floor are one plane each.

    The contract blind hole ends in a flat bottom at the requested overall
    depth. The native custom hole instead ends in a 118 degree drill point
    (two half-cone faces), which is the visible signature of its till-shoulder
    depth reading; see :func:`oracle_faces_native`.

    Measured on Creo 12.4.0.0: the plain blind hole +3, the through
    counterbore +5 and the through countersink +4 match this count, while
    the blind counterbore measures +7 and the blind countersink +6 because
    the drill point replaces the flat bottom.
    """
    faces = 2  # the bore wall, two half-cylinder faces
    if blind:
        faces += 1  # the flat bottom plane
    if "counterbore" in option:
        faces += 3  # the seat wall halves and the seat floor plane
    if "countersink" in option:
        faces += 2  # the countersink cone halves
    return faces


def oracle_faces_native(option: dict, blind: bool) -> int:
    """Faces the native hole adds, with its drill point instead of a flat bottom.

    The custom branch builds a 118 degree drill point below the bore, so its
    blind hole carries two half-cone faces where the contract expects the one
    flat bottom plane. The plain branch is the legacy straight hole and keeps
    its flat bottom.
    """
    faces = oracle_faces(option, blind)
    if blind and ("counterbore" in option or "countersink" in option):
        faces += 1
    return faces


def oracle_variants(diameter: float, depth: float, option: dict) -> dict:
    """Named removable-volume references; the contract one is judged.

    ``contract_flat_overall`` is the frozen contract (flat bottom, ``depth``
    overall from the placement face). The others diagnose native semantics:
    a 118-degree drill tip below the flat depth, or a counterbore whose drill
    depth is counted from the seat ("till shoulder") instead of the placement
    face.

    Measured on Creo 12.4.0.0 (2026-10-30 live run, N10): the custom hole
    path removes exactly ``contract_flat_overall + drill_tip_118_below_depth``
    (residual 5.5e-12 mm3 for the counterbore case), so the native reads
    ``depth`` as the depth to the shoulder plus a 118-degree drill point
    beyond it. The plain branch (no counterbore, no countersink) is the
    legacy straight hole, which has a flat bottom and no drill point, and it
    matches the contract oracle to 2.8e-12 mm3. The variant is reported,
    never silently adopted: the frozen contract stays the judged reference.
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


def _canonical_axis(axis) -> tuple:
    """A sign-independent key for a direction, so antiparallel halves group."""
    if not (isinstance(axis, list) and len(axis) == 3):
        return ()
    values = [round(float(value), 6) for value in axis]
    for value in values:
        if abs(value) > 1e-9:
            return tuple(-item if value < 0 else item for item in values)
    return tuple(values)


def cylinder_groups(snapshot: dict, radius: float, tol: float = 1e-3) -> list:
    """The cylinders of one radius, one entry per hole axis.

    The native splits every revolved surface into two seam-split half faces,
    so a single hole appears as two cylinder records whose own bounding
    boxes each cover only half of the bore and whose centres sit off the
    hole axis. The union of the halves frames the hole, so the group carries
    the union bounding box and the faces it was merged from.
    """
    groups: dict[tuple, dict] = {}
    for item in cylinder_surfaces(snapshot, radius, tol):
        group = groups.setdefault(
            (radius, _canonical_axis(item.get("axis"))),
            {"radius": radius, "axis": item.get("axis"), "faces": [], "bbox": None},
        )
        group["faces"].append(item)
        bbox = item.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 2):
            continue
        if not all(isinstance(corner, list) and len(corner) == 3 for corner in bbox):
            continue
        if group["bbox"] is None:
            group["bbox"] = [list(bbox[0]), list(bbox[1])]
            continue
        for index in range(3):
            group["bbox"][0][index] = min(group["bbox"][0][index], bbox[0][index])
            group["bbox"][1][index] = max(group["bbox"][1][index], bbox[1][index])
    return list(groups.values())


def cone_surfaces(snapshot: dict) -> list:
    """Inspection surface records that are cones (a drill point or a sink)."""
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    found = []
    for item in inspection.get("surfaces") or []:
        if isinstance(item, dict) and item.get("type") == 37:
            found.append(item)
    return found


def hole_depth_evidence(
    snapshot: dict, placement_value: float, axis_index: int = 2, direction: int = -1
) -> dict:
    """The measured depth of the hole, in millimetres from its placement face.

    ``direction`` is the drilling direction along ``axis_index``: ``-1`` for a
    hole that goes down (the placement face is the high end), ``+1`` for one
    that goes up. A blind hole that carries a 118 degree drill point reaches
    deeper than its cylindrical walls, so the deepest cone and the deepest
    cylinder are reported separately.
    """
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    surfaces = [item for item in (inspection.get("surfaces") or []) if isinstance(item, dict)]
    bore_depths = []
    cone_depths = []
    for item in surfaces:
        bbox = item.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 2):
            continue
        if not all(isinstance(corner, list) and len(corner) == 3 for corner in bbox):
            continue
        is_cylinder = isinstance(item.get("radius"), (int, float))
        if not (is_cylinder or item.get("type") == 37):
            continue
        depth = (
            placement_value - float(bbox[0][axis_index])
            if direction < 0
            else float(bbox[1][axis_index]) - placement_value
        )
        (bore_depths if is_cylinder else cone_depths).append(depth)
    return {
        "bore_depth_max": max(bore_depths) if bore_depths else None,
        "cone_depth_max": max(cone_depths) if cone_depths else None,
        "total_depth": max(bore_depths + cone_depths) if bore_depths or cone_depths else None,
    }


def depth_semantics(evidence: dict, expected_depth: float, tip_height: float) -> str:
    """Which depth reading the measured hole follows.

    ``overall_flat`` places the deepest point of the hole exactly
    ``expected_depth`` below the placement face; ``shoulder_plus_tip`` places
    the cylindrical walls there and the drill point ``tip_height`` below it.
    """
    total = evidence.get("total_depth")
    if total is None:
        return "unknown"
    if abs(total - expected_depth) <= 0.05:
        return "overall_flat"
    if tip_height and abs(total - (expected_depth + tip_height)) <= 0.05:
        return "shoulder_plus_tip"
    return "other"


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
        # The contract shape keeps its flat bottom; the native custom hole
        # replaces it with a 118 degree drill point (two half-cone faces).
        self.assertEqual(oracle_faces({}, blind=False), 2)
        self.assertEqual(oracle_faces({}, blind=True), 3)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, False), 5)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, True), 6)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, False), 4)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, True), 5)
        self.assertEqual(oracle_faces_native({}, blind=True), 3)
        self.assertEqual(
            oracle_faces_native({"counterbore": {"diameter": 10, "depth": 2}}, True), 7
        )
        self.assertEqual(
            oracle_faces_native({"countersink": {"diameter": 10, "angle": 90}}, True), 6
        )
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
        # The measured native topology of a blind straight hole: the bore
        # arrives as two seam-split half faces and the bottom is one plane.
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, -1], "bbox": [[22, 25, 3], [28, 28, 10]]},
            {"id": 2, "radius": 3.0, "axis": [0, 0, -1], "bbox": [[22, 22, 3], [28, 25, 10]]},
            {"id": 3, "normal": [0, 0, -1], "bbox": [[22, 22, 3], [28, 28, 3]]},
        ]
        surfaces += [{"id": 10 + i, "normal": [0, 0, 1]} for i in range(6)]
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
        # Measured on Creo 12.4.0.0: each revolved surface arrives as two
        # seam-split half faces, and the blind custom hole ends in a 118
        # degree drill point (two half-cone faces) instead of a flat bottom.
        self.assertEqual(oracle_faces_native({}, blind=True), 3)
        self.assertEqual(
            oracle_faces_native({"counterbore": {"diameter": 10, "depth": 2}}, blind=True), 7
        )
        self.assertEqual(
            oracle_faces_native({"countersink": {"diameter": 10, "angle": 90}}, blind=True), 6
        )
        # The contract shape keeps its flat bottom, one face less than the
        # native drill point on the custom branch.
        self.assertEqual(oracle_faces({}, blind=True), 3)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, blind=True), 6)
        self.assertEqual(
            oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, blind=True), 5
        )

    def test_the_edit_case_keeps_its_post_edit_oracle(self):
        edited = oracle_removed(7, 8, {"counterbore": {"diameter": 10, "depth": 3}})
        self.assertAlmostEqual(edited, 428.0419990516093, places=6)


class ModelNameTests(unittest.TestCase):
    """The generated model names must stay inside the repository name rule.

    The 31 character rule of the live harness aborted the 2026-10-30 run on
    ``t12_direction_side_normal_193146``, so the name is built from a short
    per-case tag and the length is locked here.
    """

    def test_every_case_name_fits_the_name_rule(self):
        from tools.test_native_countersink import (
            MODEL_NAME_MAX_LENGTH,
            MODEL_NAME_TAGS,
            REMAINDER_CASES,
            model_name_for,
        )

        for case_key in [*REMAINDER_CASES, *MODEL_NAME_TAGS]:
            with self.subTest(case=case_key):
                name = model_name_for(case_key)
                self.assertLessEqual(len(name), MODEL_NAME_MAX_LENGTH)
                self.assertRegex(name, r"^[a-z][a-z0-9_]*$")

    def test_every_registered_case_has_a_short_tag(self):
        from tools.test_native_countersink import MODEL_NAME_TAGS, REMAINDER_CASES

        for case_key in REMAINDER_CASES:
            with self.subTest(case=case_key):
                self.assertIn(case_key, MODEL_NAME_TAGS)
                # tag + "_" + six hex digits must stay within 28 characters.
                self.assertLessEqual(len(MODEL_NAME_TAGS[case_key]) + 7, 28)

    def test_an_unregistered_case_is_refused(self):
        from tools.test_native_countersink import model_name_for

        with self.assertRaises(ValueError):
            model_name_for("not_a_case")


class NativeTopologyTests(unittest.TestCase):
    """The seam-split native topology and the measured depth reading."""

    def snapshot(self, surfaces: list) -> dict:
        return {"inspection": {"surfaces": surfaces}}

    def test_the_seam_halves_frame_the_hole_only_together(self):
        # Measured on Creo 12.4.0.0: one bore arrives as two half faces whose
        # own boxes are off the hole axis; only the union frames the hole.
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, 1], "bbox": [[22, 25, 2], [28, 28, 8]]},
            {"id": 2, "radius": 3.0, "axis": [0, 0, 1], "bbox": [[22, 22, 2], [28, 25, 8]]},
        ]
        groups = cylinder_groups(self.snapshot(surfaces), 3.0)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["bbox"], [[22, 22, 2], [28, 28, 8]])
        self.assertEqual(len(groups[0]["faces"]), 2)

    def test_two_holes_of_one_radius_stay_separate(self):
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, 1], "bbox": [[0, 0, 0], [6, 6, 6]]},
            {"id": 2, "radius": 3.0, "axis": [0, 1, 0], "bbox": [[10, 0, 0], [16, 6, 6]]},
        ]
        self.assertEqual(len(cylinder_groups(self.snapshot(surfaces), 3.0)), 2)

    def test_the_depth_reading_of_a_flat_bottom_hole(self):
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, -1], "bbox": [[22, 22, 3], [28, 28, 10]]},
        ]
        evidence = hole_depth_evidence(self.snapshot(surfaces), 10.0, 2, -1)
        self.assertAlmostEqual(evidence["bore_depth_max"], 7.0, places=9)
        self.assertIsNone(evidence["cone_depth_max"])
        self.assertAlmostEqual(evidence["total_depth"], 7.0, places=9)
        self.assertEqual(depth_semantics(evidence, 7.0, oracle_tip_height(6)), "overall_flat")

    def test_the_depth_reading_of_a_drill_point_hole(self):
        # The measured 2026-10-30 custom hole: the bore reaches the requested
        # depth and the 118 degree drill point extends 1.802582 mm below it.
        surfaces = [
            {"id": 1, "radius": 3.0, "axis": [0, 0, 1], "bbox": [[22, 22, 2], [28, 28, 8]]},
            {"id": 2, "type": 37, "bbox": [[22, 22, 0.19741814291731785], [28, 28, 2]]},
        ]
        evidence = hole_depth_evidence(self.snapshot(surfaces), 10.0, 2, -1)
        self.assertAlmostEqual(evidence["bore_depth_max"], 8.0, places=9)
        self.assertAlmostEqual(evidence["cone_depth_max"], 9.802581857082682, places=9)
        self.assertEqual(depth_semantics(evidence, 8.0, oracle_tip_height(6)), "shoulder_plus_tip")

    def test_the_tip_height_is_the_measured_drill_point(self):
        self.assertAlmostEqual(oracle_tip_height(6), 1.8025818570826808, places=9)
        self.assertAlmostEqual(oracle_tip_extra(6), 16.98893375911559, places=9)


class LiveEvidenceTests(unittest.TestCase):
    """The oracle characterization must stay locked to the measured numbers.

    The 2026-10-30 live run (build/post090_live_20261030T234952/n10) is the
    evidence behind the characterization: the custom hole path removes the
    contract flat-bottom volume plus exactly one 118 degree drill point.
    """

    def test_the_measured_custom_removals_hit_the_drill_point_variant(self):
        counterbore = oracle_variants(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        countersink = oracle_variants(6, 8, {"countersink": {"diameter": 10, "angle": 90}})
        self.assertEqual(
            closest_variant(343.7145697324486, counterbore),
            "drill_tip_118_below_depth",
        )
        self.assertEqual(
            closest_variant(289.26029707022826, countersink),
            "drill_tip_118_below_depth",
        )

    def test_the_measured_plain_removal_hits_the_contract_variant(self):
        variants = oracle_variants(6, 7, {})
        self.assertEqual(closest_variant(197.92033717615413, variants), "contract_flat_overall")

    def test_the_seat_measured_drill_depth_is_excluded(self):
        # The blind counterbore does not measure its drill depth from the seat.
        variants = oracle_variants(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        self.assertNotEqual(
            closest_variant(343.7145697324486, variants), "shoulder_measured_drilldepth"
        )


if __name__ == "__main__":
    unittest.main()
