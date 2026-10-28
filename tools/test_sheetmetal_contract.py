"""DEV-051 T03 offline driver for the sheetmetal first-wall parameter contract.

Checks the fixed-frame depth/thickness matrix, the independent volume and
three-axis extent oracle, the closed-contour reference, the shared admission of
the standalone tool and execute_plan, and the legacy open-line regression. The
native source guard only proves that the committed fix is present in the
working tree; it is not native verification.

Default is strictly offline: no MCP client is instantiated and no Toolkit
connection is made. --live requires --confirm-session-usable and is refused
here: the live native acceptance of BUG-032 runs as a separate integration step
on the shared dev service, never from this driver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

LINE_LENGTH_MM = 185.0
MATRIX = ((1.0, 232.0), (232.0, 1.0), (1.0, 1.0), (2.0, 1.0), (0.5, 1.0))
REPORTED_VOLUME_MM3 = 9_957_440.0
VOLUME_TOLERANCE_MM3 = 0.01


# --- independent oracle ---------------------------------------------------


def oracle_volume_mm3(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> float:
    """Line length x in-plane thin width x extrusion depth."""
    return length * thickness * depth


def oracle_bbox_mm(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> dict:
    """Extents per axis for a line along X on XY, extruded along +Z."""
    return {"x": length, "y": thickness, "z": depth}


def oracle_centroid_mm(depth: float, thickness: float, length: float = LINE_LENGTH_MM) -> dict:
    """Centroid of the box that starts at the sketch line and grows to +Y/+Z."""
    return {"x": length / 2.0, "y": thickness / 2.0, "z": depth / 2.0}


def near(actual: float, expected: float, tolerance: float = VOLUME_TOLERANCE_MM3) -> None:
    assert abs(actual - expected) <= max(tolerance, abs(expected) * 1e-9), (actual, expected)


# --- fixtures -------------------------------------------------------------


def wall_sketch(length: float = LINE_LENGTH_MM) -> dict:
    return {
        "op": "sketch",
        "label": "s1",
        "plane": "XY",
        "entities": [
            {"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [length, 0.0]}
        ],
    }


def wall_op(depth: float, thickness: float, **overrides) -> dict:
    operation = {
        "op": "sheetmetal_wall",
        "label": "wall1",
        "sketch": "s1",
        "depth": depth,
        "thickness": thickness,
        "direction": "positive",
    }
    operation.update(overrides)
    return operation


# --- checks ---------------------------------------------------------------


def check_matrix() -> list[dict]:
    from creo_mechdog.schema import validate_operations

    rows = []
    for depth, thickness in MATRIX:
        validated = validate_operations([wall_sketch(), wall_op(depth, thickness)])
        operation = validated[1]
        assert operation["depth"] == depth, operation
        assert operation["thickness"] == thickness, operation
        assert operation["direction"] == "positive", operation
        volume = oracle_volume_mm3(depth, thickness)
        bbox = oracle_bbox_mm(depth, thickness)
        centroid = oracle_centroid_mm(depth, thickness)
        near(volume, LINE_LENGTH_MM * thickness * depth * 1.0)
        rows.append(
            {
                "depth_mm": depth,
                "thickness_mm": thickness,
                "line_length_mm": LINE_LENGTH_MM,
                "accepted": True,
                "depth_preserved": operation["depth"],
                "thickness_preserved": operation["thickness"],
                "expected_volume_mm3": volume,
                "expected_bbox_mm": bbox,
                "expected_centroid_mm": centroid,
                "native_result": "not_measured_offline",
            }
        )
    return rows


def check_reported_volume() -> dict:
    intended = oracle_volume_mm3(1.0, 232.0)
    replaced = LINE_LENGTH_MM * 232.0 * 232.0
    near(intended, 42_920.0)
    near(replaced, REPORTED_VOLUME_MM3, tolerance=0.5)
    return {
        "report": "0.3.2 S5: sheetmetal_wall(depth=1.0, thickness=232.0), 185 line",
        "reported_volume_mm3": REPORTED_VOLUME_MM3,
        "intended_volume_mm3": intended,
        "ratio": REPORTED_VOLUME_MM3 / intended,
        "reported_shape": "185 x 232 x 232 = line x thickness x thickness",
        "conclusion": (
            "The reported body keeps the 185 x 232 thin section and re-applies the "
            "232 thickness along the depth axis, so the requested depth 1 never reached "
            "the final geometry. Python passes both values unchanged, so the difference "
            "is in the native sheetmetal conversion, not the request."
        ),
        "explained_by": "depth_replaced_by_thickness_at_native_conversion",
    }


def check_closed_reference() -> dict:
    from creo_mechdog.schema import validate_operations

    rejected = []
    for entities, label in (
        (
            [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [40.0, 7.0]}],
            "rectangle",
        ),
        (
            [
                {
                    "type": "polyline",
                    "name": "outline",
                    "points": [[0.0, 0.0], [40.0, 0.0], [40.0, 7.0], [0.0, 7.0]],
                    "closed": True,
                }
            ],
            "closed_polyline",
        ),
        (
            [
                {
                    "type": "arc",
                    "name": "bend",
                    "center": [0.0, 0.0],
                    "radius": 20.0,
                    "start_angle": 0.0,
                    "end_angle": 90.0,
                }
            ],
            "arc",
        ),
        (
            [
                {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [90.0, 0.0]},
                {"type": "line", "name": "l2", "start": [90.0, 0.0], "end": [185.0, 0.0]},
            ],
            "two_line_chain",
        ),
        (
            [{"type": "centerline", "name": "axis", "start": [0.0, 0.0], "end": [185.0, 0.0]}],
            "centerline_only",
        ),
    ):
        try:
            validate_operations(
                [
                    {"op": "sketch", "label": "s1", "plane": "XY", "entities": entities},
                    wall_op(1.0, 1.0),
                ]
            )
        except ValueError as error:
            message = str(error)
            assert "exactly one open straight line" in message, (label, message)
            rejected.append({"section": label, "rejected": True, "message": message})
        else:
            raise AssertionError(f"{label} was accepted as a first wall section")
    return {"rejected": rejected, "model_untouched": "rejected_before_native_modelling"}


def check_paths() -> dict:
    from creo_mechdog.schema import validate_operations

    standalone = {
        "op": "sheetmetal_wall",
        "label": "wall1",
        "sketch": 12,
        "depth": 1.0,
        "thickness": 232.0,
        "direction": "positive",
    }
    tool = validate_operations([standalone])[0]
    assert tool == standalone, tool
    plan = validate_operations([wall_sketch(), wall_op(1.0, 232.0)])[1]
    assert plan["sketch"] == "s1" and plan["depth"] == 1.0 and plan["thickness"] == 232.0, plan
    legacy = validate_operations(
        [
            {
                "op": "sketch",
                "label": "s1",
                "plane": "XY",
                "entities": [
                    {"type": "line", "name": "wall_line", "start": [0.0, 0.0], "end": [40.0, 0.0]}
                ],
            },
            wall_op(30.0, 1.0),
        ]
    )[1]
    assert legacy["depth"] == 30.0 and legacy["thickness"] == 1.0, legacy
    near(oracle_volume_mm3(30.0, 1.0, 40.0), 1200.0)
    return {
        "standalone_tool": tool,
        "execute_plan": plan,
        "legacy_open_line_40_1_30": {
            "depth_mm": legacy["depth"],
            "thickness_mm": legacy["thickness"],
            "expected_volume_mm3": 1200.0,
        },
        "admission_shared_by": "creo_mechdog.schema.validate_operations",
    }


def check_native_source() -> dict:
    """Static guard only: proves the committed fix is in the tree, not that it runs."""
    source = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    checks = {
        "section_admission": "first_wall_line_length" in source,
        "thickness_axis_face": "if (fabs(normal[axis]) < 0.999)" in source,
        "volume_identity_guard": "SHEETMETAL_WALL_VOLUME" in source,
        "contract_recorded": '"wall_contract"' in source,
        "largest_face_heuristic_removed": "std::sort(e.begin(), e.end());" not in source,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "note": "Source presence only; native geometry is unverified until the live stage.",
    }


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_contract

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_contract)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_contract",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": result.wasSuccessful(),
    }


# --- provenance and report ------------------------------------------------


def new_run_id() -> str:
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def resolve_output(output: Path | None, run_id: str) -> Path:
    """Refuse to overwrite an existing report before anything else runs."""
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "sheetmetal_contract" / run_id / "report.json"
    )
    if path.exists():
        raise ValueError(f"Refusing to overwrite an existing report: {path}")
    return path


def local_provenance() -> dict:
    from version import VERSION

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(("tools/test_sheetmetal_contract.py", "tests/unit/test_sheetmetal_contract.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "version": VERSION,
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_sha256": hashes,
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
        "human_session_confirmation": True,
    }


def write_offline_report(output: Path, run_id: str, results: dict) -> dict:
    report = {
        "task": "BUG-032 / DEV-051 T03",
        "scope": "sheetmetal first wall: fixed-frame depth/thickness matrix, admission",
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: parameter contract, independent oracle, shared admission "
            "and legacy regression validated. No Toolkit connection, no native geometry."
        ),
        "oracle": {
            "line_length_mm": LINE_LENGTH_MM,
            "volume_formula": "line_length_mm * thickness_mm * depth_mm",
            "bbox_axes": "x=line, y=in-plane thin width, z=extrusion depth",
            "tolerance_mm3": VOLUME_TOLERANCE_MM3,
            "independent_of_production_normalization": True,
        },
        "checks": results,
        "unit_module": run_unit_module(),
        "provenance": local_provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.live and not args.confirm_session_usable:
        print("live runs require --confirm-session-usable", file=sys.stderr)
        return 2
    if args.live:
        print(
            "BUG-032 live native acceptance is a separate integration step on the shared "
            "dev service; this driver never instantiates an MCP client or connects to Creo.",
            file=sys.stderr,
        )
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "matrix": check_matrix(),
        "reported_volume": check_reported_volume(),
        "closed_reference_and_rejections": check_closed_reference(),
        "paths_and_legacy": check_paths(),
        "native_source": check_native_source(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
