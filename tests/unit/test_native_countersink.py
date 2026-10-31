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


def is_custom_branch(option: dict) -> bool:
    """True when the request carries a counterbore or a countersink.

    The native picks the custom hole branch from exactly these two keys, so
    the oracle follows the same branch the element tree will build.
    """
    return "counterbore" in option or "countersink" in option


def oracle_removed(diameter: float, depth: float, option: dict) -> float:
    """Flat-bottom analytical reference for a fully embedded hole in a plate.

    ``depth`` is the overall drill depth measured from the placement face
    (contract semantics); pass the material thickness for a through hole.
    This reference ends in a plane at ``depth`` and carries no drill point,
    see :func:`oracle_tip_extra`; the blind custom hole reaches its drill
    tip instead, see :func:`oracle_removed_tip`.
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
    """Volume of the conical drill point (one third of its body cylinder)."""
    radius = diameter / 2.0
    height = oracle_tip_height(diameter, angle)
    return math.pi * radius * radius * height / 3.0


def oracle_tip_body(diameter: float, angle: float = 118.0) -> float:
    """Volume of the cylinder that encloses the conical drill point."""
    radius = diameter / 2.0
    return math.pi * radius * radius * oracle_tip_height(diameter, angle)


def oracle_removed_tip(diameter: float, depth: float, option: dict) -> float:
    """Removal of a blind custom hole dimensioned till its drill tip.

    The native custom branch writes ``PRO_HLE_DEP_TIP_DIM_SCHEME``, so the
    requested depth is the overall depth from the placement face down to the
    tip vertex. The flat-bottom reference ends in a plane at that depth; the
    drill point replaces the last cone height of the bore column (a cylinder
    of ``pi * r^2 * h``) by the cone itself (one third of it), so the removal
    drops by two thirds of that cylinder, i.e. by twice the cone volume
    :func:`oracle_tip_extra` returns:

        flat_overall - 2 * tip_cone = flat_overall - (2/3) * tip_body

    The two thirds belong to the cone *body* cylinder, not to the cone
    volume: subtracting two thirds of the cone volume would leave the hole
    one third of a cone too deep.
    """
    return oracle_removed(diameter, depth, option) - 2.0 * oracle_tip_extra(diameter)


def oracle_faces(option: dict, blind: bool) -> int:
    """Faces the contract hole adds to the plate.

    Every revolved surface of a native hole arrives as two seam-split half
    faces (the seam lies in the plane through the hole axis), so the bore
    wall, the seat wall, the sink cone and the drill point each count
    twice. A seat floor and the plain branch's flat bottom are one plane
    each.

    The blind custom branch is dimensioned till its drill tip, so it ends in
    the 118 degree point (two half-cone faces) whose vertex sits at the
    requested overall depth. The plain straight-hole branch has no drill
    point and keeps its flat bottom plane.

    Measured on Creo 12.4.0.0: the plain blind hole +3, the through
    counterbore +5, the through countersink +4, the blind counterbore +7 and
    the blind countersink +6 all match this count.
    """
    faces = 2  # the bore wall, two half-cylinder faces
    if blind:
        if is_custom_branch(option):
            faces += 2  # the drill point, two half-cone faces
        else:
            faces += 1  # the flat bottom plane
    if "counterbore" in option:
        faces += 3  # the seat wall halves and the seat floor plane
    if "countersink" in option:
        faces += 2  # the countersink cone halves
    return faces


def oracle_faces_native(option: dict, blind: bool) -> int:
    """Faces the native hole adds to the plate.

    The custom branch always drills a 118 degree point and the plain branch
    keeps its flat bottom. Since the custom branch is now dimensioned till
    its tip, the native topology and the contract shape coincide; the two
    names are kept apart so the report can show that convergence instead of
    a silent assumption.
    """
    return oracle_faces(option, blind)


def oracle_contract(diameter: float, depth: float, option: dict, blind: bool = True) -> float:
    """The removal the frozen contract requires for this hole.

    A blind custom hole is dimensioned till its drill tip, so the tip vertex
    sits ``depth`` below the placement face and the full-diameter bore stops
    one tip height higher than the flat-bottom reference. A through custom
    hole has no drill point and every plain-branch hole ends in a plane, so
    those keep the flat-bottom reference.
    """
    if blind and is_custom_branch(option):
        return oracle_removed_tip(diameter, depth, option)
    return oracle_removed(diameter, depth, option)


def contract_variant_key(option: dict, blind: bool = True) -> str:
    """The variant name that carries the contract removal for this hole."""
    if blind and is_custom_branch(option):
        return "contract_tip_overall"
    return "contract_flat_overall"


def expected_depth_semantics(option: dict, blind: bool = True) -> str:
    """The depth reading the contract requires for this hole."""
    if blind and is_custom_branch(option):
        return "overall_tip"
    return "overall_flat"


def oracle_variants(diameter: float, depth: float, option: dict, blind: bool = True) -> dict:
    """Named removable-volume references; the contract one is judged.

    The judged contract is ``contract_tip_overall`` for a blind custom hole
    (its depth reaches the drill tip) and ``contract_flat_overall``
    otherwise. The ``defect_*`` entries are the readings the fix must not
    produce: the till-shoulder reading, whose drill point hangs one tip
    height below the requested depth, and a counterbore whose drill depth is
    counted from the seat instead of the placement face.

    Measured on Creo 12.4.0.0 (2026-10-30 live run, N10): the custom hole
    path removed exactly the till-shoulder form (residual 5.5e-12 mm3 for
    the counterbore case), i.e. it read ``depth`` as the depth to the
    shoulder plus a 118 degree drill point beyond it. After the fix that
    form must not be measured again. The plain branch is the legacy
    straight hole with a flat bottom and no drill point; it matches the
    contract oracle to 2.8e-12 mm3 and is unchanged by the fix.
    """
    flat = oracle_removed(diameter, depth, option)
    variants = {
        contract_variant_key(option, blind): oracle_contract(diameter, depth, option, blind)
    }
    if blind:
        variants["defect_till_shoulder_below_tip"] = flat + oracle_tip_extra(diameter)
    if "counterbore" in option:
        bore = option["counterbore"]
        variants["defect_seat_measured_drilldepth"] = (
            math.pi * bore["diameter"] ** 2 * bore["depth"] / 4 + math.pi * diameter**2 * depth / 4
        )
    return variants


def oracle_bore_span(diameter: float, depth: float, option: dict, top: float = 10.0) -> tuple:
    """The (low, high) span of the full-diameter bore of a blind hole.

    The span is in the placement face's axis coordinate (z for the plate top
    face). The custom branch is dimensioned till its drill tip, so its
    full-diameter bore stops one drill-point height above the tip vertex
    and starts below the seat; the plain straight-hole branch keeps its flat
    bottom at the requested depth.
    """
    if not is_custom_branch(option):
        return (top - depth, top)
    low = top - depth + oracle_tip_height(diameter)
    if "counterbore" in option:
        high = top - option["counterbore"]["depth"]
    elif "countersink" in option:
        sink = option["countersink"]
        high = top - (sink["diameter"] - diameter) / (2 * math.tan(math.radians(sink["angle"] / 2)))
    else:
        high = top
    return (low, high)


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

    ``overall_tip`` places the drill tip vertex exactly ``expected_depth``
    below the placement face; the full-diameter bore then stops one tip
    height higher. ``overall_flat`` places the deepest point of a hole
    without a drill point exactly ``expected_depth`` below the placement
    face. ``shoulder_plus_tip`` places the cylindrical walls there and the
    drill point ``tip_height`` below it, which is the till-shoulder defect
    the fix removes.
    """
    total = evidence.get("total_depth")
    if total is None:
        return "unknown"
    if abs(total - expected_depth) <= 0.05:
        return "overall_tip" if evidence.get("cone_depth_max") is not None else "overall_flat"
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
        # The flat-bottom reference is the plain branch's contract; the blind
        # custom hole is dimensioned till its drill tip and removes less.
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

    def test_the_tip_oracle_is_the_flat_reference_less_two_thirds_of_the_cone_body(self):
        # Till tip: the tip vertex sits `depth` below the placement face, so
        # the bore column loses one cone height and the cone itself replaces
        # the last of it. The removal drops by two thirds of the cone body.
        option = {"counterbore": {"diameter": 10, "depth": 2}}
        flat = oracle_removed(6, 8, option)
        self.assertAlmostEqual(oracle_tip_body(6), math.pi * 9 * oracle_tip_height(6), places=9)
        self.assertAlmostEqual(oracle_tip_extra(6), oracle_tip_body(6) / 3.0, places=9)
        self.assertAlmostEqual(
            oracle_removed_tip(6, 8, option), flat - 2.0 / 3.0 * oracle_tip_body(6), places=9
        )
        # The two thirds belong to the cone body, not to the cone volume.
        self.assertAlmostEqual(
            oracle_removed_tip(6, 8, option), flat - 2.0 * oracle_tip_extra(6), places=9
        )
        self.assertNotAlmostEqual(
            oracle_removed_tip(6, 8, option), flat - 2.0 / 3.0 * oracle_tip_extra(6), places=6
        )

    def test_the_tip_oracle_values_are_locked(self):
        # FEAT-035/T12: the blind custom holes are dimensioned till the
        # drill tip vertex. These are the numbers the live run must hit.
        self.assertAlmostEqual(
            oracle_contract(6, 8, {"counterbore": {"diameter": 10, "depth": 2}}),
            292.74776845510735,
            places=9,
        )
        self.assertAlmostEqual(
            oracle_contract(6, 8, {"countersink": {"diameter": 10, "angle": 90}}),
            238.29349579288424,
            places=9,
        )
        self.assertAlmostEqual(
            oracle_contract(7, 8, {"counterbore": {"diameter": 10, "depth": 3}}),
            374.0864038721959,
            places=9,
        )
        # The plain straight hole keeps its flat bottom and its overall depth.
        self.assertAlmostEqual(oracle_contract(6, 7, {}), 197.92033717615698, places=9)

    def test_the_contract_variant_follows_the_branch(self):
        custom = {"counterbore": {"diameter": 10, "depth": 2}}
        self.assertEqual(contract_variant_key(custom), "contract_tip_overall")
        self.assertEqual(contract_variant_key({}), "contract_flat_overall")
        self.assertEqual(contract_variant_key(custom, blind=False), "contract_flat_overall")
        self.assertEqual(expected_depth_semantics(custom), "overall_tip")
        self.assertEqual(expected_depth_semantics({}), "overall_flat")

    def test_face_deltas_and_variants(self):
        # The blind custom hole is dimensioned till its drill tip, so the
        # contract shape and the native shape now coincide: the cone is in
        # the contract, not only in the native tree.
        self.assertEqual(oracle_faces({}, blind=False), 2)
        self.assertEqual(oracle_faces({}, blind=True), 3)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, False), 5)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, True), 7)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, False), 4)
        self.assertEqual(oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, True), 6)
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
                "contract_tip_overall",
                "defect_till_shoulder_below_tip",
                "defect_seat_measured_drilldepth",
            },
        )
        self.assertGreater(oracle_tip_extra(6), 0)
        # The till-shoulder reading is a defect form now: it must not be hit.
        self.assertAlmostEqual(
            variants["defect_till_shoulder_below_tip"],
            oracle_removed(6, 8, option) + oracle_tip_extra(6),
            places=9,
        )
        self.assertGreater(
            variants["defect_till_shoulder_below_tip"], variants["contract_tip_overall"]
        )
        self.assertGreater(
            variants["defect_seat_measured_drilldepth"], variants["contract_tip_overall"]
        )
        self.assertEqual(
            closest_variant(variants["contract_tip_overall"], variants, tol=1e-6),
            "contract_tip_overall",
        )
        self.assertIsNone(closest_variant(-5.0, variants, tol=1e-6))

    def test_the_bore_span_stops_one_tip_height_above_the_tip(self):
        # Till tip: the full-diameter bore stops one drill-point height above
        # the tip vertex, so the cone occupies the last cone height.
        self.assertEqual(
            oracle_bore_span(6, 8, {"counterbore": {"diameter": 10, "depth": 2}}),
            (10.0 - 8.0 + oracle_tip_height(6), 8.0),
        )
        self.assertEqual(
            oracle_bore_span(6, 8, {"countersink": {"diameter": 10, "angle": 90}}),
            (10.0 - 8.0 + oracle_tip_height(6), 8.0),
        )
        # The plain branch keeps its flat bottom at the requested depth.
        self.assertEqual(oracle_bore_span(6, 7, {}), (3.0, 10.0))

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
            expected_variant=contract_variant_key({}, blind=True),
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
        # a volume that matches the defect drill-point variant never passes
        wrong = json.loads(json.dumps(after))
        wrong["inspection"]["volume_mm3"] = (
            PLATE_VOLUME - variants["defect_till_shoulder_below_tip"]
        )
        _, problems = judge_geometry(
            entry,
            terminal,
            wrong,
            label="blind_hole",
            expected_removed=removed,
            expected_face_delta=oracle_faces({}, blind=True),
            expected_dims={"diameter": 6, "depth": 7},
            variants=variants,
            expected_variant=contract_variant_key({}, blind=True),
            cylinder_expectations=[],
        )
        self.assertTrue(any("contract oracle" in item for item in problems))
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
            expected_variant=contract_variant_key({}, blind=True),
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

    def test_the_custom_branch_dimensions_till_the_tip(self):
        """FEAT-035/T12: the custom branch must write the tip scheme.

        The custom branch carries the 118 degree drill point, so its blind
        depth is only "overall" when the depth dimension scheme is the tip
        one. The plain straight-hole branch has no drill point and must
        keep its own element tree untouched.
        """
        source = (ROOT / "native/generic.cpp").read_text(encoding="utf-8")
        start = source.index("static J generic_hole(")
        end = source.index("static J ", start + 1)
        body = source[start:end]
        custom_start = body.index("if (custom) {")
        plain_start = body.index("} else {", custom_start)
        custom = body[custom_start:plain_start]
        plain = body[plain_start:]
        # The custom branch writes the tip scheme and never the shoulder one.
        self.assertIn("PRO_E_HLE_DEPTH_DIM_TYPE", custom)
        self.assertIn("PRO_HLE_DEP_TIP_DIM_SCHEME", custom)
        self.assertNotIn("PRO_HLE_DEP_SHOULDER_DIM_SCHEME", custom)
        self.assertEqual(custom.count("PRO_E_HLE_DEPTH_DIM_TYPE"), 1)
        # The plain straight-hole branch keeps its own depth element tree.
        self.assertNotIn("PRO_E_HLE_DEPTH_DIM_TYPE", plain)
        self.assertNotIn("PRO_HLE_DEP_", plain)
        self.assertIn("PRO_HLE_STRGHT_BLIND_DEPTH", plain)
        # No branch writes the shoulder scheme any more.
        self.assertNotIn("PRO_HLE_DEP_SHOULDER_DIM_SCHEME", body)


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
        # depth is the overall drill depth measured from the placement face.
        # The plain branch ends in a flat bottom there.
        blind = oracle_removed(6, 7, {})
        self.assertAlmostEqual(blind, math.pi * 36 * 7 / 4, places=9)
        self.assertAlmostEqual(oracle_contract(6, 7, {}), blind, places=9)

    def test_the_three_blind_variants_keep_their_expected_volumes(self):
        # The plain blind hole keeps its flat bottom; the two blind custom
        # holes are dimensioned till their drill tip vertex.
        self.assertAlmostEqual(oracle_contract(6, 7, {}), 197.92033717615698, places=6)
        self.assertAlmostEqual(
            oracle_contract(6, 8, {"counterbore": {"diameter": 10, "depth": 2}}),
            292.74776845510735,
            places=6,
        )
        self.assertAlmostEqual(
            oracle_contract(6, 8, {"countersink": {"diameter": 10, "angle": 90}}),
            238.29349579288424,
            places=6,
        )

    def test_the_face_deltas_match_the_three_blind_variants(self):
        # Measured on Creo 12.4.0.0: each revolved surface arrives as two
        # seam-split half faces, and the blind custom hole ends in a 118
        # degree drill point (two half-cone faces). The contract shape now
        # carries that point too, so both oracles agree.
        self.assertEqual(oracle_faces_native({}, blind=True), 3)
        self.assertEqual(
            oracle_faces_native({"counterbore": {"diameter": 10, "depth": 2}}, blind=True), 7
        )
        self.assertEqual(
            oracle_faces_native({"countersink": {"diameter": 10, "angle": 90}}, blind=True), 6
        )
        self.assertEqual(oracle_faces({}, blind=True), 3)
        self.assertEqual(oracle_faces({"counterbore": {"diameter": 10, "depth": 2}}, blind=True), 7)
        self.assertEqual(
            oracle_faces({"countersink": {"diameter": 10, "angle": 90}}, blind=True), 6
        )

    def test_the_edit_case_keeps_its_post_edit_oracle(self):
        edited = {"counterbore": {"diameter": 10, "depth": 3}}
        self.assertAlmostEqual(oracle_contract(7, 8, edited), 374.0864038721959, places=6)


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

    def test_the_depth_reading_of_a_till_tip_drill_point_hole(self):
        # The fixed custom branch: the tip vertex sits exactly `depth` below
        # the placement face, so the bore stops one tip height higher and the
        # cone occupies the last cone height of the hole.
        surfaces = [
            {
                "id": 1,
                "radius": 3.0,
                "axis": [0, 0, 1],
                "bbox": [[22, 22, 3.802581857], [28, 28, 8]],
            },
            {"id": 2, "type": 37, "bbox": [[22, 22, 2], [28, 28, 3.802581857]]},
        ]
        evidence = hole_depth_evidence(self.snapshot(surfaces), 10.0, 2, -1)
        self.assertAlmostEqual(evidence["bore_depth_max"], 6.197418143, places=6)
        self.assertAlmostEqual(evidence["cone_depth_max"], 8.0, places=9)
        self.assertAlmostEqual(evidence["total_depth"], 8.0, places=9)
        self.assertEqual(depth_semantics(evidence, 8.0, oracle_tip_height(6)), "overall_tip")

    def test_the_till_shoulder_reading_is_the_defect_form(self):
        # The measured 2026-10-30 custom hole before the fix: the bore
        # reached the requested depth and the 118 degree drill point
        # extended 1.802582 mm below it. That shape must not come back.
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
    evidence behind the characterization: the custom hole path removed the
    contract flat-bottom volume plus exactly one 118 degree drill point,
    i.e. it read the depth till the shoulder. After the FEAT-035/T12 fix
    that reading is the defect form and must not be measured again.
    """

    def test_the_measured_custom_removals_hit_the_defect_form(self):
        counterbore = oracle_variants(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        countersink = oracle_variants(6, 8, {"countersink": {"diameter": 10, "angle": 90}})
        self.assertEqual(
            closest_variant(343.7145697324486, counterbore),
            "defect_till_shoulder_below_tip",
        )
        self.assertEqual(
            closest_variant(289.26029707022826, countersink),
            "defect_till_shoulder_below_tip",
        )

    def test_the_measured_plain_removal_hits_the_contract_variant(self):
        variants = oracle_variants(6, 7, {})
        self.assertEqual(closest_variant(197.92033717615413, variants), "contract_flat_overall")

    def test_the_seat_measured_drill_depth_is_excluded(self):
        # The blind counterbore does not measure its drill depth from the seat.
        variants = oracle_variants(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        self.assertNotEqual(
            closest_variant(343.7145697324486, variants), "defect_seat_measured_drilldepth"
        )

    def test_the_pre_fix_measurement_is_far_from_the_fixed_contract(self):
        # The fixed contract oracle must not be confused with the pre-fix
        # measurement: they differ by the whole cone body.
        variants = oracle_variants(6, 8, {"counterbore": {"diameter": 10, "depth": 2}})
        contract = variants["contract_tip_overall"]
        self.assertAlmostEqual(contract, 292.74776845510735, places=9)
        self.assertAlmostEqual(contract, 343.7145697324486 - oracle_tip_body(6), places=9)
        self.assertGreater(343.7145697324486 - contract, 50.0)


if __name__ == "__main__":
    unittest.main()
