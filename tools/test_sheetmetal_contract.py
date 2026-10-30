"""DEV-051 T03 offline driver for the sheetmetal first-wall parameter contract.

Checks the fixed-frame depth/thickness matrix, the independent volume and
three-axis extent oracle, the closed-contour reference, the shared admission of
the standalone tool and execute_plan, and the legacy open-line regression. The
native source guard only proves that the committed fix is present in the
working tree; it is not native verification.

Default is strictly offline: no MCP client is instantiated and no Toolkit
connection is made. --live --confirm-session-usable runs the matrix against the
manually opened Creo session: five fresh models, one sheetmetal wall each, the
measured volume and the wall_contract record, then the closed-rectangle and
two-line rejections on the last model to prove the model and revision stay
untouched. It never launches, restarts or closes Creo, never injects a fault,
never clears a protection and never resubmits a job; a busy channel, an unknown
terminal state or a polling timeout stops the run and preserves the scene.
"""

from __future__ import annotations

import argparse
import asyncio
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

ROOT = SOURCE_PATHS.resource_root

from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    LiveStop,
    failure_text,
    require_manual_start,
    unique_name,
)
from tools.sheetmetal_live import (
    new_run_id as live_run_id,
)
from tools.sheetmetal_live import (
    resolve_output as live_output,
)

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


# BUG-090: these SDK APIs are missing from some SDK generations (Creo 10 lacks
# ProSmtPartThicknessValueGet), so their calls may only compile inside the
# matching MECHDOG_HAS_<name> capability guard generated by tools/
# generate_constants.py.
GATED_SDK_CALLS = ("ProSmtPartThicknessGet", "ProSmtPartThicknessValueGet")


def unguarded_sdk_calls(source: str) -> list[str]:
    """Lines calling a gated SDK API outside its capability guard.

    A call is only accepted where the matching MECHDOG_HAS_<name> macro is
    defined: the positive branch of its #ifdef/#ifndef conditional. Comment text
    is not compiled and therefore never counts as a call.
    """
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)
    problems = []
    stack: list[tuple[list[str], bool]] = []
    for line in stripped.splitlines():
        directive = line.strip()
        if directive.startswith("#ifndef "):
            stack.append(([directive.split()[1]], False))
        elif directive.startswith("#ifdef "):
            stack.append(([directive.split()[1]], True))
        elif directive.startswith("#elif"):
            if stack:
                stack[-1] = (re.findall(r"defined\s*\(\s*(\w+)\s*\)", directive), True)
        elif directive.startswith("#else"):
            if stack:
                names, active = stack[-1]
                stack[-1] = (names, not active)
        elif directive.startswith("#endif"):
            if stack:
                stack.pop()
        elif directive.startswith("#if"):
            stack.append((re.findall(r"defined\s*\(\s*(\w+)\s*\)", directive), True))
        for name in GATED_SDK_CALLS:
            if re.search(r"\b" + name + r"\s*\(", line):
                macro = "MECHDOG_HAS_" + name
                if not any(active and macro in names for names, active in stack):
                    problems.append(line.strip())
    return problems


def check_native_source() -> dict:
    """Static guard only: proves the committed fix is in the tree, not that it runs."""
    source = (ROOT / "native" / "advanced.cpp").read_text(encoding="utf-8", errors="replace")
    checks = {
        "section_admission": "first_wall_line_length" in source,
        "thickness_axis_face": "if (fabs(normal[axis]) < 0.999)" in source,
        "volume_identity_guard": "SHEETMETAL_WALL_VOLUME" in source,
        "contract_recorded": '"wall_contract"' in source,
        "largest_face_heuristic_removed": "std::sort(e.begin(), e.end());" not in source,
        # BUG-032/T03: the native wall must read, sync and re-prove the
        # part-level sheetmetal thickness instead of trusting the geometry.
        "part_thickness_read": "ProSmtPartThicknessValueGet(" in source,
        "part_thickness_dimension_sync": "ProSmtPartThicknessGet" in source
        and "ProDimensionValueSet" in source,
        "part_thickness_regen_recheck": "SHEETMETAL_WALL_PART_THICKNESS" in source,
        "part_thickness_mismatch_fails": "did not sync the part thickness parameter" in source,
        # BUG-090: SDK-missing APIs stay out of the compile unit behind the
        # generated capability macros; all three reads share one model-read
        # helper, an unreadable thickness fails the first wall explicitly and
        # only the informational flange fields may degrade to null.
        "part_thickness_api_gated": not unguarded_sdk_calls(source),
        "part_thickness_unified_read": source.count("part_thickness_read(") == 4,
        "part_thickness_parameter_fallback": "ProParameterValueWithUnitsGet" in source,
        "part_thickness_unknown_fails_wall": "could not read the part-level sheetmetal thickness"
        in source,
        "part_thickness_informational_null": "thickness_known ? J(thickness) : J()" in source,
    }
    missing = [name for name, present in checks.items() if not present]
    assert not missing, f"native source guard missing: {missing}"
    return {
        "static_source_assertions": checks,
        "unguarded_sdk_calls": unguarded_sdk_calls(source),
        "note": "Source presence only; native geometry is unverified until the live stage.",
    }


# --- live acceptance ------------------------------------------------------

LIVE_CASES = (
    {"tag": "t03_d1_t232", "depth": 1.0, "thickness": 232.0},
    {"tag": "t03_d232_t1", "depth": 232.0, "thickness": 1.0},
    {"tag": "t03_d1_t1", "depth": 1.0, "thickness": 1.0},
    {"tag": "t03_d2_t1", "depth": 2.0, "thickness": 1.0},
    {"tag": "t03_d05_t1", "depth": 0.5, "thickness": 1.0},
)

REJECTION_SECTIONS = (
    (
        "closed_rectangle",
        [{"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [185.0, 232.0]}],
    ),
    (
        "two_line_chain",
        [
            {"type": "line", "name": "l1", "start": [0.0, 0.0], "end": [90.0, 0.0]},
            {"type": "line", "name": "l2", "start": [90.0, 0.0], "end": [185.0, 0.0]},
        ],
    ),
)


def volume_verdict(depth: float, thickness: float, measured: float | None) -> dict:
    expected = oracle_volume_mm3(depth, thickness)
    tolerance = max(VOLUME_TOLERANCE_MM3, abs(expected) * 1e-3)
    if measured is None:
        return {
            "expected_volume_mm3": expected,
            "tolerance_mm3": tolerance,
            "abs_error_mm3": None,
            "passed": False,
        }
    error = abs(float(measured) - expected)
    return {
        "expected_volume_mm3": expected,
        "tolerance_mm3": tolerance,
        "abs_error_mm3": error,
        "passed": error <= tolerance,
    }


THICKNESS_TOLERANCE_MM = 1e-6


def thickness_verdict(thickness_mm: float, contract: dict) -> dict:
    """BUG-032: the native part-level thickness must agree with the request.

    A wall may only pass when its contract carries a *measured* native part
    thickness equal to the requested wall thickness. The 2026-10-29 round 6
    defect shape - geometry 1 mm while ProSmtPartThicknessValueGet reads the
    3.71 mm template default - is a thickness source contradiction and must
    fail here, even when the volume and bounding box are correct.
    """
    native = contract.get("part_thickness_mm")
    entry: dict = {
        "requested_thickness_mm": thickness_mm,
        "native_part_thickness_mm": native,
        "part_thickness_synced": contract.get("part_thickness_synced"),
    }
    if native is None:
        entry.update(
            passed=False,
            reason="wall_contract carries no measured native part thickness",
        )
        return entry
    error = abs(float(native) - float(thickness_mm))
    entry["abs_error_mm"] = error
    entry["passed"] = error <= THICKNESS_TOLERANCE_MM
    if not entry["passed"]:
        entry["reason"] = (
            "thickness source contradiction: the part-level sheetmetal thickness "
            f"({native} mm) does not match the requested wall thickness "
            f"({thickness_mm} mm); geometry alone does not prove the parameter"
        )
    return entry


async def run_matrix_case(runner: LiveRunner, case: dict) -> dict:
    """One fresh model, one first wall, one measured volume."""
    depth, thickness = case["depth"], case["thickness"]
    name = unique_name(case["tag"])
    created = await runner.submit(
        f"{case['tag']}:new-wall",
        "creo_execute_plan",
        {
            "model_name": name,
            "model_type": "sheetmetal",
            "operations": [wall_sketch(), wall_op(depth, thickness)],
        },
    )
    job_id, model_id = created["job_id"], created["model_id"]
    terminal = await runner.wait_job(job_id)
    entry: dict = {
        "case": case["tag"],
        "depth_mm": depth,
        "thickness_mm": thickness,
        "line_length_mm": LINE_LENGTH_MM,
        "model_name": name,
        "model_id": model_id,
        "job_id": job_id,
        "status": terminal.get("status"),
        "revision": terminal.get("revision"),
        "saved_file_reloaded_and_verified": (terminal.get("result") or {}).get(
            "saved_file_reloaded_and_verified"
        ),
    }
    if terminal.get("status") != "succeeded":
        verdict = volume_verdict(depth, thickness, None)
        entry.update(
            expected_volume_mm3=verdict["expected_volume_mm3"],
            tolerance_mm3=verdict["tolerance_mm3"],
            failure=failure_text(terminal),
            passed=False,
            note="the wall was not created; the raw failure is kept, expectations unchanged",
        )
        return runner.case(entry)

    snapshot = await runner.snapshot(model_id)
    measured = runner.volume(snapshot)
    verdict = volume_verdict(depth, thickness, measured)
    contract = (runner.record(snapshot, "wall1") or {}).get("wall_contract") or {}
    thickness_check = thickness_verdict(thickness, contract)
    entry.update(
        measured_volume_mm3=measured,
        expected_volume_mm3=verdict["expected_volume_mm3"],
        tolerance_mm3=verdict["tolerance_mm3"],
        abs_error_mm3=verdict["abs_error_mm3"],
        wall_contract=contract,
        thickness_source=thickness_check,
        feature_types=runner.feature_types(snapshot),
        passed=bool(
            verdict["passed"]
            and thickness_check["passed"]
            and entry["saved_file_reloaded_and_verified"] is True
        ),
    )
    if (depth, thickness) == (1.0, 232.0):
        reproduces = measured is not None and abs(float(measured) - REPORTED_VOLUME_MM3) <= 0.5
        entry["reported_error_volume_mm3"] = REPORTED_VOLUME_MM3
        entry["reproduces_reported_error_volume"] = reproduces
    return runner.case(entry)


async def open_rejection_anchor(runner: LiveRunner) -> dict:
    """A sketch-only sheetmetal model, so the admission path is still observable.

    The rejection contract is Python-side admission; it does not need a wall. This
    anchor exists only when every matrix case failed, and it is recorded as such.
    """
    name = unique_name("t03_reject_anchor")
    created = await runner.submit(
        "rejection_anchor:new-sketch",
        "creo_execute_plan",
        {"model_name": name, "model_type": "sheetmetal", "operations": [wall_sketch()]},
    )
    terminal = await runner.wait_job(created["job_id"])
    runner.report["rejection_anchor"] = {
        "model_name": name,
        "model_id": created["model_id"],
        "job_id": created["job_id"],
        "status": terminal.get("status"),
        "reason": "no matrix case succeeded, so the rejection check uses a sketch-only model",
    }
    if terminal.get("status") != "succeeded":
        raise LiveStop(f"rejection anchor sketch failed: {failure_text(terminal)}")
    return {"model_id": created["model_id"]}


async def run_rejection_case(runner: LiveRunner, anchor: dict) -> dict:
    """Illegal first-wall sections must be refused before any feature exists."""
    model_id = anchor["model_id"]
    before = await runner.snapshot(model_id)
    revision = before.get("revision")
    volume = runner.volume(before)
    sections = []
    for name, entities in REJECTION_SECTIONS:
        answer = await runner.probe(
            "creo_execute_plan",
            {
                "model_id": model_id,
                "expected_revision": revision,
                "operations": [
                    {"op": "sketch", "label": "s1", "plane": "XY", "entities": entities},
                    wall_op(1.0, 1.0),
                ],
            },
        )
        body = answer["structured"] or {}
        message = body.get("error") or body.get("message") or answer["text"]
        sections.append(
            {
                "section": name,
                "rejected": bool(answer["is_error"]),
                "job_id": body.get("job_id"),
                "message": str(message)[:600],
            }
        )
    after = await runner.snapshot(model_id)
    unchanged = (
        after.get("revision") == revision
        and runner.volume(after) == volume
        and not any(section["job_id"] for section in sections)
    )
    return runner.case(
        {
            "case": "rejection_before_modelling",
            "model_id": model_id,
            "revision_before": revision,
            "revision_after": after.get("revision"),
            "volume_before_mm3": volume,
            "volume_after_mm3": runner.volume(after),
            "sections": sections,
            "model_and_revision_unchanged": unchanged,
            "passed": bool(unchanged and all(section["rejected"] for section in sections)),
        }
    )


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "BUG-032 / DEV-051 T03",
            "first-wall depth/thickness matrix: live volume, wall_contract, pre-modelling rejection",
            run_id,
        )
        try:
            await runner.start()
            anchor = None
            for case in LIVE_CASES:
                entry = await run_matrix_case(runner, case)
                if entry["passed"] and anchor is None:
                    anchor = entry
            if anchor is None:
                anchor = await open_rejection_anchor(runner)
            await run_rejection_case(runner, anchor)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {
            key: case.get(key)
            for key in (
                "case",
                "status",
                "measured_volume_mm3",
                "expected_volume_mm3",
                "abs_error_mm3",
                "passed",
            )
        }
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


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
        run_id = live_run_id()
        return asyncio.run(live(live_output("sheetmetal_contract", run_id, args.output), run_id))

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
