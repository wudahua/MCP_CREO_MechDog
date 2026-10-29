"""DEV-051 T11 offline driver: bend-end relief for the four-wall flange case (FEAT-014).

Second-batch T11. Inputs: the T05 failure candidate (185 x 232 x 1 mm base wall,
four flanges h80 / R2.54 / Y0.5, third flange returned
ProFeatureWithoptionsCreate=-1) and the T03 contract for the thin wall.

The driver is offline only. It records:

* what Creo 12.4 Toolkit exposes for bend relief and corners, read from the
  installed ProSmtFlangeWall.h when a Creo root is configured and otherwise
  reported as a transcription with the header path;
* the admission matrix -- the compatibility default none, the single supported
  rectangular shape, the end selection and every rejected combination;
* the native element tree the implementation must produce, plus what it must
  still not touch (corner relief, miter cuts, edge rip, parent body);
* the four-wall expectation with relief: wall volume, relief removal, shared
  corners and the depth needed to reach the T05 corner run;
* the edit path: relief is fixed at creation, the named height dimension keeps
  its existing edit, and a change means deleting and re-creating the flange.

No Creo session, no Toolkit job, no native geometry. "--live" is refused even
with --confirm-session-usable: the live four-wall relief run belongs to the
single shared dev service integration step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
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
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tests.unit import test_sheetmetal_relief as relief  # noqa: E402

ROOT = SOURCE_PATHS.resource_root

LIVE_REFUSAL = (
    "T11 four-wall relief is a separate integration step on the single shared dev service "
    "(MCP_CREO_MechDog_dev, E:/Projects/MCP_CREO_MechDog). This driver runs offline checks "
    "only: it never instantiates an MCP client, never connects to Creo and never retries a job. "
    "Use --live --confirm-session-usable only inside that assigned integration step, after the "
    "session is confirmed usable and the BUG-001 conditions hold."
)

PROFILES = {
    "thickness_scale": {
        "description": "one thickness wide and deep; the Creo-style default scale",
        "relief": {"type": "rectangular", "width": 1.0, "depth": 1.0},
    },
    "corner_run": {
        "description": (
            "one thickness wide, depth equal to the shared corner run (height - radius); the "
            "smallest notch that reaches through the T05 overlap column"
        ),
        "relief": {"type": "rectangular", "width": 1.0, "depth": 77.46},
    },
}


# --- checks ---------------------------------------------------------------


def configured_creo_root() -> Path | None:
    config = ROOT / "config.json"
    if not config.exists():
        return None
    try:
        root = json.loads(config.read_text(encoding="utf-8-sig")).get("creo_root")
    except (OSError, ValueError):
        return None
    return Path(root) if root else None


def sdk_contract() -> dict:
    """Relief and corner enums, cross-checked against the installed SDK if present."""
    header = "Common Files/protoolkit/includes/ProSmtFlangeWall.h"
    parsed: dict = {"status": "not_checked", "path": None, "lines": {}}
    root = configured_creo_root()
    candidate = root / header if root else None
    if candidate is not None and candidate.exists():
        text = candidate.read_text(encoding="utf-8", errors="replace")
        names = {}
        for match in re.finditer(r"PRO_BEND_RLF_([A-Z_]+)\s*=\s*(-?\d+)", text):
            names[match.group(1).lower()] = int(match.group(2))
        found = {name: names.get(name) for name in relief.RELIEF_TYPES}
        for match in re.finditer(r"^\s*(PRO_E_[A-Z_0-9]+)\s{2,}", text, re.M):
            parsed["lines"][match.group(1)] = text[: match.start()].count("\n") + 1
        parsed.update(
            {
                "status": "parsed",
                "path": str(candidate),
                "relief_types": found,
                "matches_transcription": found == relief.RELIEF_TYPES,
                "element_names_present": {
                    "PRO_E_SMT_BEND_RELIEF": "PRO_E_SMT_BEND_RELIEF" in parsed["lines"],
                    "PRO_E_SMT_BEND_RELIEF_SIDE1": "PRO_E_SMT_BEND_RELIEF_SIDE1" in parsed["lines"],
                    "PRO_E_SMT_BEND_RELIEF_SIDE2": "PRO_E_SMT_BEND_RELIEF_SIDE2" in parsed["lines"],
                    "PRO_E_BEND_RELIEF_WIDTH": "PRO_E_BEND_RELIEF_WIDTH" in parsed["lines"],
                    "PRO_E_BEND_RELIEF_DEPTH_TYPE": "PRO_E_BEND_RELIEF_DEPTH_TYPE"
                    in parsed["lines"],
                    "PRO_E_BEND_RELIEF_DEPTH": "PRO_E_BEND_RELIEF_DEPTH" in parsed["lines"],
                },
            }
        )
    elif candidate is not None:
        parsed.update({"status": "header_not_found", "path": str(candidate)})
    return {
        "sdk_version": relief.SDK_VERSION,
        "header": header,
        "transcribed": {
            "relief_types": relief.RELIEF_TYPES,
            "depth_types": relief.RELIEF_DEPTH_TYPES,
            "corner_relief_types": relief.CORNER_RELIEF_TYPES,
        },
        "installed_header": parsed,
        "selected_shape": {
            "type": "rectangular",
            "why": (
                "the only shape whose geometry the caller fully controls with two numbers; rip "
                "has no width/depth, stretch and obround are not needed for a box corner, and "
                "param defers to part defaults"
            ),
            "width_rule": "width > 0 in model units; mandatory on every enabled end",
            "depth_rule": (
                "depth >= 0 in model units, always PRO_BEND_RLF_DEPTH_BLIND, measured from the "
                "bend edge (SDK note 7)"
            ),
            "end_rule": "ends both|side1|side2; the other end stays PRO_BEND_RLF_NONE",
            "thickness_rule": (
                "absolute model units, never a thickness multiple and never a thickness-derived "
                "default; the applied record carries the measured part thickness"
            ),
        },
        "not_supported": {
            "relief_shapes": list(relief.UNSUPPORTED_RELIEF_TYPES),
            "corner_rules": list(relief.NOT_IMPLEMENTED_CORNER_RULES),
            "statement": (
                "corner relief (ProCornerRelType), miter cuts and edge rips exist in the same "
                "SDK tree but are not emitted; nothing is inferred from edge or corner geometry"
            ),
        },
    }


def _attempt(relief_value) -> dict:
    from creo_mechdog.schema import validate_operations

    operation = relief.flange_op(relief_value)
    try:
        return {"accepted": validate_operations([operation])[0]}
    except Exception as error:  # noqa: BLE001 - the driver records the real rejection text
        return {"rejected": str(error)}


def admission_matrix() -> dict:
    cases = {
        "omitted": None,
        "explicit_none": {"type": "none"},
        "rectangular_both": {"type": "rectangular", "width": 1.0, "depth": 1.0},
        "rectangular_side1": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side1"},
        "rectangular_side2": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "side2"},
        "rectangular_zero_depth": {"type": "rectangular", "width": 1.0, "depth": 0.0},
        "none_with_width": {"type": "none", "width": 1.0},
        "none_with_ends": {"type": "none", "ends": "side1"},
        "rectangular_missing_depth": {"type": "rectangular", "width": 1.0},
        "rectangular_zero_width": {"type": "rectangular", "width": 0.0, "depth": 1.0},
        "rectangular_negative_depth": {"type": "rectangular", "width": 1.0, "depth": -1.0},
        "rectangular_boolean_width": {"type": "rectangular", "width": True, "depth": 1.0},
        "rectangular_infinite_depth": {"type": "rectangular", "width": 1.0, "depth": float("inf")},
        "rip": {"type": "rip"},
        "stretch": {"type": "stretch"},
        "obround": {"type": "obround", "width": 1.0, "depth": 1.0},
        "param": {"type": "param"},
        "auto_corner": {"type": "rectangular", "width": 1.0, "depth": 1.0, "corner": "auto"},
        "unknown_end": {"type": "rectangular", "width": 1.0, "depth": 1.0, "ends": "left"},
    }
    results = {name: _attempt(value) for name, value in cases.items()}
    expected_accepted = {
        name
        for name, value in cases.items()
        if name
        in {
            "omitted",
            "explicit_none",
            "rectangular_both",
            "rectangular_side1",
            "rectangular_side2",
            "rectangular_zero_depth",
        }
    }
    for name, result in results.items():
        assert ("accepted" in result) == (name in expected_accepted), (name, result)
        if "accepted" in result:
            dumped = result["accepted"]
            sides = relief.expected_native_sides(dumped.get("relief"))
            result["native_sides"] = sides
    return {
        "cases": results,
        "accepted": sorted(expected_accepted),
        "statement": (
            "the compatibility default stays none on both ends; rectangular is the only added "
            "shape and every other SDK shape is rejected, not silently mapped to none"
        ),
    }


def default_compatibility() -> dict:
    operations, _ = fx.four_wall_plan(fx.box_inspection())
    from creo_mechdog.schema import validate_operations

    dumped = validate_operations(operations)
    flanges = [item for item in dumped if item["op"] == "sheetmetal_flange"]
    return {
        "reported_plan_still_validates": len(flanges) == 4,
        "relief_key_present": any("relief" in item for item in flanges),
        "unchanged_fields": sorted(flanges[0]),
        "statement": (
            "the pre-T11 four-wall plan validates unchanged and carries no relief key, so both "
            "bend ends keep PRO_BEND_RLF_NONE"
        ),
    }


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.find("\nstatic ", start + len(signature))
    return source[start : end if end > 0 else len(source)]


def native_source() -> dict:
    advanced = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    flange = _function_body(advanced, "static void generic_sheetmetal_flange")
    side = _function_body(advanced, "static void flange_relief_side")
    request = _function_body(advanced, "static FlangeReliefRequest flange_relief_request")
    record = _function_body(advanced, "static J flange_relief_record")
    checks = {
        "relief_compound_both_ends": "PRO_E_SMT_BEND_RELIEF_SIDE1" in flange
        and "PRO_E_SMT_BEND_RELIEF_SIDE2" in flange,
        "default_none_preserved": "PRO_BEND_RLF_NONE" in side,
        "rectangular_opt_in": "PRO_BEND_RLF_RECTANGULAR" in side,
        "width_element": "PRO_E_BEND_RELIEF_WIDTH" in side,
        "depth_type_blind": "PRO_E_BEND_RELIEF_DEPTH_TYPE" in side
        and "PRO_BEND_RLF_DEPTH_BLIND" in side,
        "depth_element": "PRO_E_BEND_RELIEF_DEPTH" in side,
        "no_corner_relief": "PRO_E_SMT_CORNER_RELIEF" not in flange + side + record,
        "no_miter_cut": "PRO_E_SMT_MTR_CUTS" not in flange + side + record,
        "no_edge_rip": "PRO_E_SMT_EDGE_RIP" not in flange + side + record,
        "no_rip_or_obround": "PRO_BEND_RLF_RIP" not in side and "PRO_BEND_RLF_OBROUND" not in side,
        "no_length_or_angle": "PRO_E_BEND_RELIEF_LENGTH" not in side
        and "PRO_E_BEND_RELIEF_ANGLE" not in side,
        "parent_body_still_implicit": "PRO_E_BODY" not in flange + side + record,
        "validated_before_tree": flange.index("flange_relief_request(op)")
        < flange.index("node(nullptr, PRO_E_FEATURE_TREE)"),
        "unknown_type_throws": "Unsupported sheetmetal flange relief type" in request,
        "record_only_when_requested": 'extra["relief"] = flange_relief_record' in flange
        and 'op.contains("relief")' in flange,
        "measured_thickness": "ProSmtPartThicknessValueGet" in record,
        "height_dimension_kept": '{"name", "height"}' in flange,
        "section_path_kept": 'extra["section_path"]' in flange,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "element_tree": {
            "bend_relief": "PRO_E_SMT_BEND_RELIEF with SIDE1 and SIDE2 compounds",
            "default": "both ends PRO_BEND_RLF_NONE (pre-T11 behaviour)",
            "rectangular": (
                "type RECTANGULAR, width, depth type BLIND, depth on the selected ends"
            ),
            "untouched": [
                "PRO_E_SMT_CORNER_RELIEF",
                "PRO_E_SMT_MTR_CUTS",
                "PRO_E_SMT_EDGE_RIP",
                "PRO_E_BODY",
            ],
            "record": (
                "relief alias record: requested sides, measured part thickness, corner run and "
                "the two request-derived comparisons"
            ),
        },
        "live_uncertainty": (
            "the rectangular branch leaves PRO_E_BEND_RELIEF_LENGTH_TYPE/LENGTH/ANGLE unset; the "
            "flange feature mapping table is not published in the SDK header, so the first live "
            "creation must confirm the tree is accepted (fallback: set length type to not-used)"
        ),
    }


def four_wall_plan(profile: str = "thickness_scale") -> dict:
    from creo_mechdog.schema import validate_operations

    relief_value = PROFILES[profile]["relief"]
    inspection = fx.box_inspection()
    operations = [fx.wall_sketch(), fx.wall_base_op()]
    rows = []
    previous: list[str] = []
    run = relief.corner_overlap_run_mm()
    for side, label in fx.FLANGE_SEQUENCE:
        reference = fx.select_wall_edge(inspection, fx.PLATE_BOUNDS, side, face="top")
        operation = fx.flange_op(side, label, reference)
        operation["relief"] = dict(relief_value)
        operations.append(operation)
        corners = fx.shared_corners(previous, side)
        previous.append(side)
        span = reference["geometry"]["span_mm"]
        removed = relief.relief_removed_mm3(relief_value)
        rows.append(
            {
                "label": label,
                "side": side,
                "edge_span_mm": span,
                "relief": dict(relief_value),
                "native_sides": relief.expected_native_sides(relief_value),
                "wall_volume_mm3": fx.wall_volume_mm3(span),
                "relief_removed_mm3": removed,
                "expected_added_volume_mm3": fx.wall_volume_mm3(span) - removed,
                "shared_corners": corners,
                "corner_overlap_lower_bound_mm3": fx.corner_overlap_volume_mm3(corners),
                "corner_overlap_run_mm": run,
                "depth_reaches_corner_run": relief_value["depth"] >= run,
            }
        )
    dumped = validate_operations(operations)
    return {
        "profile": profile,
        "profile_description": PROFILES[profile]["description"],
        "operations_validated": len(dumped),
        "flanges": rows,
        "total_expected_added_volume_mm3": sum(row["expected_added_volume_mm3"] for row in rows),
        "base_volume_mm3": fx.PLATE_VOLUME_MM3,
        "expected_body_volume_mm3": fx.PLATE_VOLUME_MM3
        + sum(row["expected_added_volume_mm3"] for row in rows),
        "volume_note": (
            "wall volume is span x height x thickness; a rectangular notch removes "
            "width x depth x thickness per enabled end. The body total is an independent "
            "expectation, not a native measurement"
        ),
        "not_verified": (
            "the notch footprint relative to the bend line is a live measurement: only a live "
            "volume delta and surface inspection can confirm that depth is measured into the "
            "wall run as assumed"
        ),
    }


def profiles() -> dict:
    run = relief.corner_overlap_run_mm()
    return {
        "corner_overlap_run_mm": run,
        "profiles": {
            name: {
                "relief": dict(value["relief"]),
                "description": value["description"],
                "removed_per_wall_mm3": relief.relief_removed_mm3(value["relief"]),
                "reaches_corner_run": value["relief"]["depth"] >= run,
            }
            for name, value in PROFILES.items()
        },
        "statement": (
            "the thickness-scale notch is the ordinary Creo relief and cannot clear a 77.46 mm "
            "shared corner run; the corner-run profile is the diagnostic that can"
        ),
    }


def edit_path() -> dict:
    return {
        "creation_only": (
            "relief is written into the flange element tree at creation; the executor has no "
            "feature redefine, so there is no in-place relief edit"
        ),
        "kept_edit": "creo_set_dimensions still edits the flanges named height dimension",
        "change_sequence": [
            "delete or suppress the flange with creo_feature_state",
            "re-create it with the new relief through creo_sheetmetal_flange or execute_plan",
            "re-create any flange that consumed the removed features edge",
        ],
        "record": (
            "the relief alias record keeps the requested values, the measured part thickness and "
            "the two request-derived comparisons so a caller can detect drift before rebuilding"
        ),
        "not_verified": "none of these steps was executed in this stage",
    }


def live_checklist() -> list[str]:
    return [
        "confirm the session is usable and BUG-001 conditions hold; one dev service only",
        "fresh model, unique name; record job/model/revision and the base wall 185x232x1 volume",
        "create the first flange with relief {rectangular, both ends, 1x1} and inspect the tree",
        "record the measured added volume and compare with span x height x t - 2 x w x d x t",
        "inspect the notch surfaces and their distance from the bend line (depth axis)",
        "run the same flange without relief on a second model and diff volume and surfaces",
        "submit flanges 2-4 with relief on both ends, re-inspecting each edge before submitting",
        "repeat with the corner-run profile (width 1, depth 77.46) and compare the third flange",
        "toggle ends side1/side2 on one flange to confirm one-sided relief material removal",
        "unbend/flat pattern and bend back with relief present; check the relief in the flat state",
        "edit the named height dimension with relief present; record revision before/after",
        "save, reload and verify the model; then suppress/delete a flange and re-create it",
        "on failure record the raw code, feature status, real rollback and revision",
        "corner relief, miter cuts and edge rips stay out of scope: do not test them as supported",
    ]


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_relief

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_relief)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_relief",
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
    path = (
        Path(output)
        if output is not None
        else ROOT / "build" / "sheetmetal_relief" / run_id / "report.json"
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
    names.update(("tools/test_sheetmetal_relief.py", "tests/unit/test_sheetmetal_relief.py"))
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
        "task": "FEAT-014 / DEV-051 T11",
        "scope": (
            "bend-end relief design and offline implementation for the four-wall flange case: "
            "SDK shape audit, admission, native element tree, geometry expectation, edit path"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "status": {
            "offline_implementation": "complete",
            "four_wall_capability": "pending_native_acceptance",
            "statement": (
                "Offline only: contract, native tree and expectations are in place. No Toolkit "
                "connection, no flange created, no relief measured, no four-wall closure."
            ),
        },
        "fixture": {
            "base_wall_mm": [fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM, fx.PLATE_THICKNESS_MM],
            "base_volume_mm3": fx.PLATE_VOLUME_MM3,
            "labels": [label for _, label in fx.FLANGE_SEQUENCE],
            "flange": {
                "height": fx.FLANGE_HEIGHT_MM,
                "radius": fx.FLANGE_RADIUS_MM,
                "y_factor": fx.FLANGE_Y_FACTOR,
                "angle": fx.FLANGE_ANGLE_DEG,
            },
            "oracle_independent_of_production": True,
        },
        "checks": results,
        "live_checklist": live_checklist(),
        "not_verified": [
            "no flange or relief was created; the four walls remain unverified",
            "unbend/flat pattern, bend back, dimension edit, revision, save/reload and rollback "
            "are untested",
            "the notch footprint relative to the bend line and the volume delta are predictions",
            "corner relief, miter cuts and edge rips are unsupported, not alternative paths",
        ],
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
        print(LIVE_REFUSAL, file=sys.stderr)
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "sdk_contract": sdk_contract(),
        "admission_matrix": admission_matrix(),
        "default_compatibility": default_compatibility(),
        "native_source": native_source(),
        "profiles": profiles(),
        "four_wall_thickness_scale": four_wall_plan("thickness_scale"),
        "four_wall_corner_run": four_wall_plan("corner_run"),
        "edit_path": edit_path(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(
        f"status: {report['status']['offline_implementation']} / "
        f"{report['status']['four_wall_capability']}"
    )
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
