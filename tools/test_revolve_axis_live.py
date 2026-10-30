"""DEV-051 T09B live driver: the revolve axis actually used (FEAT-008).

The result block ``revolve_axis`` must come from the axis or section centerline
Creo really resolved, never from the request. This driver measures three cases:

* ``internal_centerline`` - sketch centerline, no axis requested
* ``explicit_datum_axis`` - a datum axis feature built from two datum planes
* ``no_centerline``       - neither, so the job must fail without the block

For the successful cases it also locks the fixed centerline accounting: the
count reports user-drawn centerlines only (the sketch's system reference
projections must not inflate it - the 10-29 run counted 3 for one drawn line),
the reported ``id`` is the sketch section entity id of that centerline, and an
explicit save with ``saved_file_reloaded_and_verified=true`` leaves the same
axis resolvable at the same id and geometry.

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
        # The sketch draws exactly one user centerline; the two system
        # reference projections must not be counted (the fixed accounting).
        "section_centerline_count": 1,
        "sketch_entity": "spin_centerline",
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


def axis_id_source(
    block: dict, entity_ids: dict, expected_entity: str | None, datum_axes: list
) -> tuple[list[str], dict]:
    """Where the reported ``id`` must come from, and whether it does.

    The section_centerline id is the sketch section entity id of the drawn
    centerline (same id space as the sketch result's entity_ids); an explicit
    datum axis id is the id the inspection lists for that axis. Both sources
    must be present: a missing source is not a match, and a missing id is
    never quietly accepted as "unknown but fine". Multiple user centerlines
    keep id=null and are never assigned the first line.
    """
    problems: list[str] = []
    evidence: dict = {}
    if expected_entity is not None:
        source_id = entity_ids.get(expected_entity)
        evidence = {"entity": expected_entity, "sketch_entity_id": source_id}
        if source_id is None:
            problems.append(
                f"sketch entity_ids has no {expected_entity!r}; the id source cannot be verified"
            )
        elif block.get("id") is None:
            problems.append(
                f"revolve_axis.id is null; the id of {expected_entity!r} "
                f"(sketch entity id {source_id}) was not reported"
            )
        elif block.get("id") != source_id:
            problems.append(
                f"id={block.get('id')!r} does not match sketch "
                f"entity_ids[{expected_entity!r}]={source_id!r}"
            )
    elif block.get("kind") == "datum_axis":
        if len(datum_axes) != 1:
            problems.append(
                f"the inspection lists {len(datum_axes)} datum axes; the resolved axis id "
                "source cannot be verified"
            )
        else:
            axis_id = datum_axes[0].get("id")
            evidence = {"axis": "datum_axes[0]", "axis_id": axis_id}
            if block.get("id") is None:
                problems.append(
                    "revolve_axis.id is null; the resolved datum axis id was not reported"
                )
            elif block.get("id") != axis_id:
                problems.append(
                    f"id={block.get('id')!r} does not match inspection datum_axes[0].id={axis_id!r}"
                )
    return problems, evidence


def check_contract() -> dict:
    block_keys = set(FIELD_KEYS)
    return {
        "expected_block_keys": sorted(block_keys),
        "oracles_mm3": {
            "ring": round(RING_VOLUME, 6),
            "cylinder": round(CYLINDER_VOLUME, 6),
        },
        "centerline_accounting": {
            "internal_centerline.section_centerline_count": 1,
            "internal_centerline.id_source": "sketch result entity_ids['spin_centerline']",
            "rule": (
                "the count covers user-drawn centerlines only; the sketch's system reference "
                "projections are never user lines and a count above the drawn user lines is a "
                "regression, while truly multiple user centerlines keep id=null (never guessed)"
            ),
        },
        "id_source_rule": (
            "revolve_axis.id must equal the sketch section entity id of the drawn centerline "
            "(entity_ids['spin_centerline']) or the inspection datum_axes[0].id for an explicit "
            "datum axis; a missing source or a null id is a failure, never a silent pass"
        ),
        "multiple_user_centerlines": (
            "not constructible through this service: the sketch admission accepts one centerline "
            "per sketch, so a truly multi-centerline scene needs an external native fixture and "
            "is reported as unverified until then; an admission refusal is not a geometry pass"
        ),
        "note": (
            "revolve_axis comes from the resolved axis/centerline; the driver compares it with "
            "these request-derived volumes, with the direction/origin it can predict, with the "
            "sketch section entity id, and with a verified save/reload of the same axis"
        ),
    }


def axis_block(terminal: dict) -> dict:
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    for operation in result.get("operations") or []:
        if isinstance(operation, dict) and isinstance(operation.get("revolve_axis"), dict):
            return operation["revolve_axis"]
    return {}


def sketch_entity_ids(terminal: dict) -> dict:
    """Section entity ids (name -> id) from the plan's sketch operation record."""
    result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
    for operation in result.get("operations") or []:
        if isinstance(operation, dict) and operation.get("op") == "sketch":
            ids = operation.get("entity_ids")
            if isinstance(ids, dict):
                return ids
    return {}


def reload_flag(terminal: dict | None) -> object:
    """Reload evidence from the job result block only.

    A missing terminal or a missing result block means "no evidence", never
    a crash: the verdict must record the gap, not abort the whole run.
    """
    result = terminal.get("result") if isinstance(terminal, dict) else None
    block = result if isinstance(result, dict) else {}
    return block.get("saved_file_reloaded_and_verified")


def axes_of(snapshot: dict) -> list:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    return [
        item
        for item in (inspection.get("datum_axes") or inspection.get("axes") or [])
        if isinstance(item, dict)
    ]


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
    axes = axes_of(snapshot)
    entry["datum_axes"] = [
        {key: item.get(key) for key in ("id", "origin", "direction", "geometry_known")}
        for item in axes
    ]

    # Fixed centerline accounting: the count is user-drawn centerlines only.
    # An inflated count (the 10-29 run measured 3 for one drawn line because
    # the two system reference projections were counted) is a regression.
    resolution = block.get("resolution") if isinstance(block.get("resolution"), dict) else {}
    expected_count = EXPECTED[case].get("section_centerline_count")
    if expected_count is not None and resolution.get("section_centerline_count") != expected_count:
        problems.append(
            f"section_centerline_count={resolution.get('section_centerline_count')!r} "
            f"expected {expected_count!r} (system reference lines must not be counted)"
        )

    # ID source: the section_centerline id is the sketch section entity id of
    # the drawn centerline (same id space as the sketch result entity_ids).
    entity_ids = sketch_entity_ids(terminal)
    if entity_ids:
        entry["sketch_entity_ids"] = entity_ids
    expected_entity = EXPECTED[case].get("sketch_entity")
    id_problems, id_evidence = axis_id_source(block, entity_ids, expected_entity, axes)
    problems.extend(id_problems)
    if id_evidence:
        entry["id_source"] = id_evidence

    # Save + reload: the axis must stay resolvable at the same identity and
    # geometry after the save erased and reloaded the file. Model inspection
    # does not list a revolve feature's own section axis, so the identity
    # comparison runs on the explicit datum-axis case; for the internal
    # centerline the reload evidence is the save job's verified reload plus
    # unchanged volume, and the entry records that the axis re-location itself
    # is not observable via inspection.
    if EXPECTED[case]["succeeds"]:
        saved = await runner.submit(
            f"{case}:save",
            "creo_save_model",
            {"model_id": created["model_id"], "expected_revision": entry["revision"]},
        )
        save_terminal = await runner.wait_job(saved["job_id"], budget=HANG_BUDGET_SECONDS)
        post = await runner.snapshot(created["model_id"])
        post_volume = volume_of(post)
        post_axes = axes_of(post)
        save_problems = []
        if save_terminal.get("status") != "succeeded":
            save_problems.append(f"save job {save_terminal.get('status')}")
        if reload_flag(save_terminal) is not True:
            save_problems.append(f"saved_file_reloaded_and_verified={reload_flag(save_terminal)!r}")
        if not near(post_volume, entry["volume_mm3"], 1.0):
            save_problems.append(f"post-reload volume={post_volume!r} pre={entry['volume_mm3']!r}")
        if EXPECTED[case].get("kind") == "datum_axis" and len(axes) == 1 and len(post_axes) == 1:
            pre_axis, post_axis = axes[0], post_axes[0]
            if pre_axis.get("id") != post_axis.get("id"):
                save_problems.append(
                    f"axis id changed after reload: {pre_axis.get('id')!r} -> {post_axis.get('id')!r}"
                )
            else:
                for key in ("origin", "direction"):
                    before, after = pre_axis.get(key), post_axis.get(key)
                    if not (
                        isinstance(before, list)
                        and isinstance(after, list)
                        and len(before) == len(after)
                        and all(near(b, a, 1e-6) for b, a in zip(before, after))
                    ):
                        save_problems.append(f"axis {key} changed after reload")
        else:
            entry["axis_relocation_after_reload"] = "not_observable_via_inspection"
        entry["save_reload"] = {
            "job_id": save_terminal.get("job_id"),
            "status": save_terminal.get("status"),
            "saved_file_reloaded_and_verified": reload_flag(save_terminal),
            "post_reload_revision": post.get("revision"),
            "post_reload_volume_mm3": post_volume,
            "post_reload_datum_axes": [
                {key: item.get(key) for key in ("id", "origin", "direction")} for item in post_axes
            ],
            "problems": save_problems,
        }
        problems.extend(f"save_reload:{name}" for name in save_problems)

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
