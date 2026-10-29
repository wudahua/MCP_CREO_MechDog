"""DEV-051 T09B live driver: the revolve axis actually used (FEAT-008).

The result block ``revolve_axis`` must come from the axis or section centerline
Creo really resolved, never from the request. This driver measures three cases:

* ``internal_centerline`` - sketch centerline, no axis requested
* ``explicit_datum_axis`` - a datum axis feature built from two datum planes
* ``no_centerline``       - neither, so the job must fail without the block

Default is strictly offline (contract shape and volume oracles only, no MCP
client). ``--live --confirm-session-usable`` runs the three cases serially with a
fresh model each; a job that is not terminal within HANG_BUDGET_SECONDS stops
the run with its job id kept.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import platform
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tools.sheetmetal_live import LiveRunner, failure_text, require_manual_start, unique_name  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
HANG_BUDGET_SECONDS = 180.0

# Volume oracles (mm3), derived from the request geometry only.
RING_VOLUME = math.pi * (20.0**2 - 10.0**2) * 10.0  # rectangle x10..20, y-5..5, axis at x=0
CYLINDER_VOLUME = math.pi * 5.0**2 * 10.0  # rectangle x10..20, y0..5, axis = X

FIELD_KEYS = (
    "source",
    "kind",
    "id",
    "origin",
    "direction",
    "frame",
    "geometry_known",
    "query_code",
    "resolution",
)


def ring_sketch() -> dict:
    return {
        "op": "sketch",
        "label": "ring_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "ring", "min": [10.0, -5.0], "max": [20.0, 5.0]},
            {
                "type": "centerline",
                "name": "spin_centerline",
                "start": [0.0, -10.0],
                "end": [0.0, 10.0],
            },
        ],
    }


def cylinder_sketch() -> dict:
    return {
        "op": "sketch",
        "label": "cyl_sketch",
        "plane": "XY",
        "entities": [{"type": "rectangle", "name": "cyl", "min": [10.0, 0.0], "max": [20.0, 5.0]}],
    }


def axis_op() -> dict:
    # X axis = intersection of the XZ (id 4) and XY (id 6) datum planes.
    return {
        "op": "datum_axis",
        "label": "x_axis",
        "references": [{"kind": "plane", "id": 4}, {"kind": "plane", "id": 6}],
    }


def revolve_op(label: str, sketch: str, axis: dict | None = None) -> dict:
    operation = {
        "op": "revolve",
        "label": label,
        "sketch": sketch,
        "angle": 360.0,
        "mode": "add",
        "direction": "positive",
    }
    if axis is not None:
        operation["axis"] = axis
    return operation


PLANS = {
    "internal_centerline": [ring_sketch(), revolve_op("ring_revolve", "ring_sketch")],
    "explicit_datum_axis": [
        cylinder_sketch(),
        axis_op(),
        revolve_op("cyl_revolve", "cyl_sketch", {"kind": "datum_axis_feature", "label": "x_axis"}),
    ],
    "no_centerline": [cylinder_sketch(), revolve_op("no_axis_revolve", "cyl_sketch")],
}
EXPECTED = {
    "internal_centerline": {
        "source": "internal_centerline",
        "kind": "section_centerline",
        "frame": "sketch_local",
        "volume_mm3": RING_VOLUME,
        "geometry_known": True,
        "succeeds": True,
    },
    "explicit_datum_axis": {
        "source": "explicit",
        "kind": "datum_axis",
        "frame": "model",
        "volume_mm3": CYLINDER_VOLUME,
        "geometry_known": True,
        "succeeds": True,
    },
    "no_centerline": {"succeeds": False},
}


# --- checks ---------------------------------------------------------------


def check_contract() -> dict:
    block_keys = set(FIELD_KEYS)
    return {
        "expected_block_keys": sorted(block_keys),
        "oracles_mm3": {
            "ring": round(RING_VOLUME, 6),
            "cylinder": round(CYLINDER_VOLUME, 6),
        },
        "note": (
            "revolve_axis comes from the resolved axis/centerline; the driver compares it with "
            "these request-derived volumes and with the direction/origin it can predict"
        ),
    }


def axis_block(terminal: dict) -> dict:
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    for operation in result.get("operations") or []:
        if isinstance(operation, dict) and isinstance(operation.get("revolve_axis"), dict):
            return operation["revolve_axis"]
    return {}


def volume_of(snapshot: dict) -> float | None:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    value = inspection.get("volume_mm3")
    return value if isinstance(value, (int, float)) else None


def near(a: float | None, b: float | None, tolerance: float) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tolerance


# --- live -----------------------------------------------------------------


async def run_case(runner: LiveRunner, case: str) -> dict:
    name = unique_name(f"t09b_{case}")
    created = await runner.submit(
        f"{case}:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": "part", "operations": PLANS[case]},
    )
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    entry = {
        "case": case,
        "model_name": name,
        "model_id": created["model_id"],
        "job_id": created["job_id"],
        "job_status": terminal.get("status"),
        "expected": EXPECTED[case],
    }
    snapshot = await runner.snapshot(created["model_id"])
    entry["revision"] = snapshot.get("revision")
    entry["volume_mm3"] = volume_of(snapshot)
    block = axis_block(terminal)
    entry["revolve_axis"] = {key: block.get(key) for key in FIELD_KEYS} if block else None

    if not EXPECTED[case]["succeeds"]:
        entry["failure"] = failure_text(terminal)
        entry["block_absent"] = not block
        entry["passed"] = bool(
            terminal.get("status") == "failed" and not block and entry["volume_mm3"] is None
        )
        return runner.case(entry)

    problems = []
    if terminal.get("status") != "succeeded":
        problems.append(f"job {terminal.get('status')}")
    if not block:
        problems.append("revolve_axis block missing")
    for key in ("source", "kind"):
        if block.get(key) != EXPECTED[case][key]:
            problems.append(f"{key}={block.get(key)!r} expected {EXPECTED[case][key]!r}")
    if block.get("frame") not in ("model", "sketch_local"):
        problems.append(f"frame={block.get('frame')!r} is not model or sketch_local")
    if block.get("geometry_known") is not True:
        problems.append(f"geometry_known={block.get('geometry_known')!r}")
    if not near(entry["volume_mm3"], EXPECTED[case]["volume_mm3"], 1.0):
        problems.append(f"volume={entry['volume_mm3']!r} expected {EXPECTED[case]['volume_mm3']!r}")
    origin = block.get("origin")
    direction = block.get("direction")
    # The block prefers the created feature's own axis (model frame); the sketch-local
    # 2D form is the fallback when that axis cannot be read. Both must describe the
    # same line: the origin may be any point on it, so only off-axis components are
    # constrained.
    if block.get("frame") == "sketch_local":
        if not (isinstance(origin, list) and len(origin) == 2 and near(origin[0], 0.0, 1e-6)):
            problems.append(f"origin={origin!r} expected [0, <v>]")
        if not (
            isinstance(direction, list)
            and len(direction) == 2
            and near(abs(direction[1]), 1.0, 1e-6)
        ):
            problems.append(f"direction={direction!r} expected [0, ±1]")
    elif block.get("frame") == "model":
        if not (isinstance(origin, list) and len(origin) == 3):
            problems.append(f"origin={origin!r} expected a 3D point")
        elif EXPECTED[case]["kind"] == "section_centerline":
            # Centerline at x = 0 on the XY plane -> point on the Y axis.
            if not (near(origin[0], 0.0, 1e-6) and near(origin[2], 0.0, 1e-6)):
                problems.append(f"origin={origin!r} not on the x=0 line")
        elif not (near(origin[1], 0.0, 1e-6) and near(origin[2], 0.0, 1e-6)):
            problems.append(f"origin={origin!r} not on the X axis")
        axis_index = 1 if EXPECTED[case]["kind"] == "section_centerline" else 0
        if not (
            isinstance(direction, list)
            and len(direction) == 3
            and near(abs(direction[axis_index]), 1.0, 1e-6)
        ):
            problems.append(f"direction={direction!r} not along the expected axis")
    else:
        problems.append(f"frame={block.get('frame')!r} is not measurable")

    # Independent axis-geometry read: the same revolve feature must expose one datum
    # axis whose geometry matches the reported direction.
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    axes = [
        item
        for item in (inspection.get("datum_axes") or inspection.get("axes") or [])
        if isinstance(item, dict)
    ]
    entry["datum_axes"] = [
        {key: item.get(key) for key in ("id", "origin", "direction", "geometry_known")}
        for item in axes
    ]
    entry["problems"] = problems
    entry["passed"] = not problems
    return runner.case(entry)


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "FEAT-008 / DEV-051 T09B",
            "revolve_axis: internal centerline, explicit datum axis, and the failure path",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            for case in EXPECTED:
                await run_case(runner, case)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {key: case.get(key) for key in ("case", "job_status", "volume_mm3", "problems", "passed")}
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


# --- offline --------------------------------------------------------------


def provenance() -> dict:
    from version import VERSION

    return {
        "version": VERSION,
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "auto_start_creo": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    output = args.output or ROOT / "build" / "revolve_axis" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        return asyncio.run(live(output, run_id))
    report = {
        "task": "FEAT-008 / DEV-051 T09B",
        "mode": "offline",
        "native_acceptance": "not_run",
        "contract": check_contract(),
        "plans": PLANS,
        "expected": EXPECTED,
        "provenance": provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "contract": report["contract"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
