"""DEV-051 T08B live driver: what ``body_counts`` actually counts.

BUG-040 separates "body records" from "material bodies". This driver measures the
three shapes the defect was reported on plus two controls that could be counted
by mistake:

* ``part_single``      - one solid body (baseline: 1 object, 1 active, 1 material)
* ``part_two_body``    - a second solid body created with new_body=true
* ``sheetmetal_wall``  - first wall: a material body plus a non-geometry record
* ``part_surface_quilt`` - a surface (quilt) extrude must not add a body
* ``assembly_two``     - an assembly reports null, never 0

Default is strictly offline: the projection contract is checked against fixtures
and no MCP client is created. ``--live --confirm-session-usable`` runs the five
cases on the manually opened session; every case uses a fresh model name, no job
is resubmitted, and a job that is not terminal within HANG_BUDGET_SECONDS stops
the run with the job id recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import sys
import time
import uuid
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from creo_mechdog.model_queries import body_counts  # noqa: E402
from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tools.sheetmetal_live import LiveRunner, require_manual_start, unique_name  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
HANG_BUDGET_SECONDS = 180.0

# --- fixtures -------------------------------------------------------------


def box_sketch(label: str, low: list[float], high: list[float], plane: str = "XY") -> dict:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "entities": [{"type": "rectangle", "name": f"{label}_box", "min": low, "max": high}],
    }


def box_extrude(label: str, sketch: str, depth: float = 10.0, **overrides) -> dict:
    operation = {
        "op": "extrude",
        "label": label,
        "sketch": sketch,
        "depth": depth,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    }
    operation.update(overrides)
    return operation


def sheetmetal_base() -> list[dict]:
    # DEV-051 T03 confirmed thin plate: line 185 on XZ, depth 232, thickness 1.
    return [
        {
            "op": "sketch",
            "label": "wall_sketch",
            "plane": "XZ",
            "entities": [
                {
                    "type": "line",
                    "name": "wall_line",
                    "start": [0.0, 0.0],
                    "end": [185.0, 0.0],
                }
            ],
        },
        {
            "op": "sheetmetal_wall",
            "label": "base_wall",
            "sketch": "wall_sketch",
            "depth": 232.0,
            "thickness": 1.0,
            "direction": "positive",
        },
    ]


PLAN_SINGLE = [
    box_sketch("plate_sketch", [0.0, 0.0], [50.0, 40.0]),
    box_extrude("plate", "plate_sketch"),
]
PLAN_TWO_BODY = [
    *PLAN_SINGLE,
    box_sketch("boss_sketch", [70.0, 0.0], [80.0, 10.0]),
    box_extrude("boss", "boss_sketch", new_body=True),
]
PLAN_SURFACE = [
    *PLAN_SINGLE,
    box_sketch("quilt_sketch", [10.0, 10.0], [20.0, 20.0]),
    box_extrude("quilt", "quilt_sketch", mode="surface"),
]

# Expected native values. ``counts.bodies`` keeps its record meaning and is
# listed separately from the material-body view.
EXPECTATIONS = {
    "part_single": {
        "model_type": "part",
        "volume_mm3": 20_000.0,
        "records": 1,
        "active": 1,
        "with_material": 1,
        "without_material": 0,
    },
    "part_two_body": {
        "model_type": "part",
        "volume_mm3": 21_000.0,
        "records": 2,
        "active": 2,
        "with_material": 2,
        "without_material": 0,
    },
    "sheetmetal_wall": {
        "model_type": "sheetmetal",
        "volume_mm3": 42_920.0,
        "records": 2,
        "active": 1,
        "with_material": 1,
        "without_material": 1,
    },
    "part_surface_quilt": {
        "model_type": "part",
        "volume_mm3": 20_000.0,
        "records": 1,
        "active": 1,
        "with_material": 1,
        "without_material": 0,
    },
    "assembly_two": {"model_type": "assembly", "volume_mm3": None, "body_counts": None},
}


def plan_for(case: str) -> list[dict]:
    return {
        "part_single": PLAN_SINGLE,
        "part_two_body": PLAN_TWO_BODY,
        "sheetmetal_wall": sheetmetal_base(),
        "part_surface_quilt": PLAN_SURFACE,
    }[case]


# --- checks ---------------------------------------------------------------


def check_projection_contract() -> dict:
    sample = {
        "objects": 2,
        "records": 2,
        "active": 1,
        "with_material": 1,
        "without_material": 1,
        "counts_meaning": {
            "bodies": "body_objects",
            "with_material": "active_bodies_with_surfaces",
        },
    }
    projected = body_counts(sample)
    assert projected == sample, projected
    assert body_counts(None) is None, "assembly must stay null, not 0"
    for broken in ({}, {"objects": -1}, {"objects": True}, {"objects": "2"}):
        value = body_counts(broken)
        for key, item in value.items():
            if key != "counts_meaning":
                assert item is None, (broken, key, item)
    return {
        "passthrough_keys": sorted(body_counts(sample)),
        "assembly_is_null": body_counts(None) is None,
        "invalid_values_become_null": True,
        "no_backfill_from_records": True,
    }


def expected_rows() -> list[dict]:
    return [{"case": case, **expectation} for case, expectation in EXPECTATIONS.items()]


def record_text(value: dict | None) -> dict:
    return value if isinstance(value, dict) else {}


def summarize(snapshot: dict) -> dict:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    bodies = inspection.get("bodies") if isinstance(inspection.get("bodies"), list) else []
    model = snapshot.get("model") if isinstance(snapshot.get("model"), dict) else {}
    return {
        "revision": snapshot.get("revision"),
        "volume_mm3": inspection.get("volume_mm3"),
        "body_counts": inspection.get("body_counts"),
        "counts": record_text(inspection.get("counts")),
        "model_type": inspection.get("model_type") or model.get("model_type"),
        "bodies": [
            {
                key: body.get(key)
                for key in ("id", "state", "state_name", "surface_count", "material", "bbox")
            }
            for body in bodies
            if isinstance(body, dict)
        ],
    }


def judge(case: str, summary: dict) -> dict:
    expectation = EXPECTATIONS[case]
    counts = summary["body_counts"]
    problems = []
    if expectation.get("body_counts", "missing") is None:
        if counts is not None:
            problems.append(f"body_counts should be null, got {counts!r}")
    elif not isinstance(counts, dict):
        problems.append(f"body_counts missing: {counts!r}")
    else:
        for key in ("records", "active", "with_material", "without_material"):
            if counts.get(key) != expectation[key]:
                problems.append(f"{key}={counts.get(key)!r} expected {expectation[key]!r}")
    if expectation.get("volume_mm3") is not None:
        if (
            summary["volume_mm3"] is None
            or abs(summary["volume_mm3"] - expectation["volume_mm3"]) > 0.01
        ):
            problems.append(
                f"volume={summary['volume_mm3']!r} expected {expectation['volume_mm3']!r}"
            )
    if summary["model_type"] not in (None, expectation["model_type"]):
        problems.append(
            f"model_type={summary['model_type']!r} expected {expectation['model_type']!r}"
        )
    if isinstance(counts, dict) and summary["counts"].get("bodies") is not None:
        if summary["counts"]["bodies"] != counts.get("records"):
            problems.append(
                f"counts.bodies={summary['counts']['bodies']!r} but records={counts.get('records')!r}"
            )
    return {"case": case, "expected": expectation, "observed": summary, "problems": problems}


# --- live -----------------------------------------------------------------


async def create_part(
    runner: LiveRunner, name: str, operations: list[dict], model_type: str = "part"
) -> dict:
    created = await runner.submit(
        f"{name}:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": model_type, "operations": operations},
    )
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    return {"created": created, "terminal": terminal}


async def run_case(runner: LiveRunner, case: str) -> dict:
    if case == "assembly_two":
        return await run_assembly(runner)
    name = unique_name(f"t08b_{case}")
    result = await create_part(
        runner, name, plan_for(case), model_type=EXPECTATIONS[case]["model_type"]
    )
    entry = {
        "case": case,
        "model_name": name,
        "model_id": result["created"]["model_id"],
        "job_id": result["created"]["job_id"],
        "job_status": result["terminal"].get("status"),
    }
    if result["terminal"].get("status") != "succeeded":
        entry["failure"] = str(result["terminal"].get("message"))[:800]
        entry["passed"] = False
        return runner.case(entry)
    snapshot = await runner.snapshot(result["created"]["model_id"])
    judged = judge(case, summarize(snapshot))
    entry.update(judged)
    entry["passed"] = not judged["problems"]
    return runner.case(entry)


async def run_assembly(runner: LiveRunner) -> dict:
    sources = []
    for index in ("a", "b"):
        name = unique_name(f"t08b_asm_src_{index}")
        made = await create_part(runner, name, PLAN_SINGLE)
        terminal = made["terminal"]
        if terminal.get("status") != "succeeded":
            return runner.case(
                {
                    "case": "assembly_two",
                    "model_name": name,
                    "job_id": made["created"]["job_id"],
                    "job_status": terminal.get("status"),
                    "failure": str(terminal.get("message"))[:800],
                    "passed": False,
                }
            )
        sources.append(made["created"]["model_id"])
    name = unique_name("t08b_asm")
    operations = [
        {
            "op": "assemble_component",
            "label": f"component_{index}",
            "source_model_id": model_id,
            "placement": "fixed",
        }
        for index, model_id in zip("ab", sources)
    ]
    created = await runner.submit(
        "assembly_two:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": "assembly", "operations": operations},
    )
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    entry = {
        "case": "assembly_two",
        "model_name": name,
        "model_id": created["model_id"],
        "job_id": created["job_id"],
        "job_status": terminal.get("status"),
        "component_sources": sources,
    }
    if terminal.get("status") != "succeeded":
        entry["failure"] = str(terminal.get("message"))[:800]
        entry["passed"] = False
        return runner.case(entry)
    snapshot = await runner.snapshot(created["model_id"])
    summary = summarize(snapshot)
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    components = (
        inspection.get("components") if isinstance(inspection.get("components"), list) else []
    )
    problems = []
    if summary["body_counts"] is not None:
        problems.append(f"assembly body_counts should be null, got {summary['body_counts']!r}")
    if len(components) != 2:
        problems.append(f"components={len(components)} expected 2")
    entry.update(
        observed=summary,
        component_count=len(components),
        components=[
            {"label": item.get("label"), "identity": item.get("identity")}
            for item in components
            if isinstance(item, dict)
        ],
        problems=problems,
        passed=not problems,
    )
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
            "BUG-040 / DEV-051 T08B",
            "body_counts on one solid body, two bodies, a sheetmetal wall, a surface quilt "
            "and a two-component assembly",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            runner.report["expectations"] = EXPECTATIONS
            for case in EXPECTATIONS:
                await run_case(runner, case)
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {key: case.get(key) for key in ("case", "job_status", "body_counts", "problems", "passed")}
        for case in runner.report["cases"]
    ]
    if rows and isinstance(rows[0], dict):
        for row, case in zip(rows, runner.report["cases"]):
            row["body_counts"] = (case.get("observed") or {}).get(
                "body_counts", case.get("body_counts")
            )
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


def write_offline_report(output: Path) -> dict:
    report = {
        "task": "BUG-040 / DEV-051 T08B",
        "mode": "offline",
        "native_acceptance": "not_run",
        "statement": (
            "Offline stage only: the body_counts projection contract and the expected native "
            "values are fixed here. No Toolkit connection, no body created."
        ),
        "expectations": EXPECTATIONS,
        "projection": check_projection_contract(),
        "provenance": provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        output = args.output or ROOT / "build" / "body_counts" / run_id / "report.json"
        if output.exists():
            raise SystemExit(f"refusing to overwrite {output}")
        return asyncio.run(live(output, run_id))
    output = args.output or ROOT / "build" / "body_counts" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    report = write_offline_report(output)
    print(
        json.dumps({"report": str(output), "projection": report["projection"]}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
