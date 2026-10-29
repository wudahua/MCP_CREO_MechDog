"""FEAT-035 T12 offline contract report; live Toolkit execution is refused."""

from __future__ import annotations

import argparse
import asyncio
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.unit import test_native_countersink as fixture  # noqa: E402
from tools.sheetmetal_live import (  # noqa: E402
    LiveRunner,
    failure_text,
    require_manual_start,
    unique_name,
)

HANG_BUDGET_SECONDS = 180.0
PLATE_VOLUME_MM3 = 50.0 * 50.0 * 10.0
PLATE_PLAN = [
    {
        "op": "sketch",
        "label": "plate_sketch",
        "plane": "XY",
        "entities": [
            {"type": "rectangle", "name": "plate", "min": [0.0, 0.0], "max": [50.0, 50.0]}
        ],
    },
    {
        "op": "extrude",
        "label": "plate",
        "sketch": "plate_sketch",
        "depth": 10.0,
        "mode": "add",
        "direction": "positive",
        "depth_type": "blind",
    },
]


def plane_record(record: dict) -> dict:
    normal = record.get("normal")
    origin = record.get("origin")
    return {
        "id": record.get("id"),
        "normal": normal if isinstance(normal, list) else None,
        "origin": origin if isinstance(origin, list) else None,
    }


def pick_geometry(snapshot: dict) -> dict:
    """Top face (+Z at z=10) and the X/Y datum planes of the plate."""
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    surfaces = [
        plane_record(item)
        for item in (inspection.get("surfaces") or [])
        if isinstance(item, dict) and isinstance(item.get("normal"), list)
    ]
    datum_planes = [
        plane_record(item)
        for item in (inspection.get("datum_planes") or [])
        if isinstance(item, dict) and isinstance(item.get("normal"), list)
    ]

    def unit_axis(normal: list) -> str | None:
        if len(normal) != 3:
            return None
        for name, index in (("x", 0), ("y", 1), ("z", 2)):
            if abs(abs(normal[index]) - 1.0) < 1e-6 and all(
                abs(normal[other]) < 1e-6 for other in range(3) if other != index
            ):
                return name
        return None

    top = [
        item
        for item in surfaces
        if unit_axis(item["normal"]) == "z"
        and item["origin"]
        and abs(item["origin"][2] - 10.0) < 1e-6
    ]
    datum_x = [item for item in datum_planes if unit_axis(item["normal"]) == "x"]
    datum_y = [item for item in datum_planes if unit_axis(item["normal"]) == "y"]
    return {
        "surfaces": surfaces,
        "datum_planes": datum_planes,
        "top_face_id": top[0]["id"] if top else None,
        "datum_x_id": datum_x[0]["id"] if datum_x else None,
        "datum_y_id": datum_y[0]["id"] if datum_y else None,
    }


def hole_op(geometry: dict, label: str, **option) -> dict:
    operation = fixture.BASE | {
        "label": label,
        "placement": {"kind": "surface", "id": geometry["top_face_id"]},
        "reference1": {"kind": "datum_plane", "id": geometry["datum_x_id"]},
        "reference2": {"kind": "datum_plane", "id": geometry["datum_y_id"]},
        "offset1": 25.0,
        "offset2": 25.0,
    }
    operation.update(option)
    return operation


CASES = {
    "cbore_flat_seat": {"counterbore": {"diameter": 10, "depth": 2}},
    "csink_90": {"countersink": {"diameter": 10, "angle": 90}},
}


def feature_counts(snapshot: dict) -> dict:
    inspection = snapshot.get("inspection") if isinstance(snapshot.get("inspection"), dict) else {}
    counts: dict[str, int] = {}
    for feature in inspection.get("features") or []:
        if isinstance(feature, dict):
            name = str(feature.get("type_name") or "other")
            counts[name] = counts.get(name, 0) + 1
    return counts


async def run_live(output: Path | None) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    target = output or ROOT / "build" / "native_countersink" / run_id / "report.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite {target}")
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            target,
            "FEAT-035 / DEV-051 T12",
            "custom hole: counterbore and 90-degree countersink on a 50x50x10 plate, plus the "
            "180-degree contract refusal",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            runner.report["plate_volume_mm3"] = PLATE_VOLUME_MM3
            for case, option in CASES.items():
                name = unique_name(f"t12_{case}")
                made = await runner.submit(
                    f"{case}:create",
                    "creo_execute_plan",
                    {"model_name": name, "model_type": "part", "operations": PLATE_PLAN},
                )
                base = await runner.wait_job(made["job_id"], budget=HANG_BUDGET_SECONDS)
                entry = {
                    "case": case,
                    "option": option,
                    "model_name": name,
                    "model_id": made["model_id"],
                    "base_job_id": made["job_id"],
                    "base_status": base.get("status"),
                }
                if base.get("status") != "succeeded":
                    entry.update(failure=failure_text(base), passed=False)
                    runner.case(entry)
                    continue
                before = await runner.snapshot(made["model_id"])
                geometry = pick_geometry(before)
                entry["geometry"] = {
                    key: geometry[key] for key in ("top_face_id", "datum_x_id", "datum_y_id")
                }
                entry["base_volume_mm3"] = LiveRunner.volume(before)
                entry["base_features"] = feature_counts(before)
                if not all(geometry[key] for key in ("top_face_id", "datum_x_id", "datum_y_id")):
                    entry["problems"] = ["plate geometry could not be resolved from inspection"]
                    entry["passed"] = False
                    runner.case(entry)
                    continue
                hole = await runner.submit(
                    f"{case}:hole",
                    "creo_execute_plan",
                    {
                        "model_id": made["model_id"],
                        "expected_revision": before.get("revision"),
                        "operations": [hole_op(geometry, "seated_hole", **option)],
                    },
                )
                terminal = await runner.wait_job(hole["job_id"], budget=HANG_BUDGET_SECONDS)
                entry.update(hole_job_id=hole["job_id"], hole_status=terminal.get("status"))
                if terminal.get("status") != "succeeded":
                    entry.update(failure=failure_text(terminal), passed=False)
                    runner.case(entry)
                    continue
                after = await runner.snapshot(made["model_id"])
                after_volume = LiveRunner.volume(after)
                removed = (
                    None
                    if after_volume is None or entry["base_volume_mm3"] is None
                    else entry["base_volume_mm3"] - after_volume
                )
                expected_removed = fixture.oracle_removed(6.0, 10.0, option)
                counts = feature_counts(after)
                result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
                operations = result.get("operations") or []
                entry.update(
                    revision=after.get("revision"),
                    volume_mm3=after_volume,
                    removed_mm3=removed,
                    expected_removed_mm3=expected_removed,
                    abs_error_mm3=None if removed is None else abs(removed - expected_removed),
                    volume_abs_error_mm3=None
                    if after_volume is None
                    else abs(after_volume - (PLATE_VOLUME_MM3 - expected_removed)),
                    feature_types=counts,
                    feature_delta={
                        key: counts.get(key, 0) - entry["base_features"].get(key, 0)
                        for key in set(counts) | set(entry["base_features"])
                    },
                    operation_result=operations[0] if operations else None,
                    saved_file_reloaded_and_verified=result.get("saved_file_reloaded_and_verified"),
                )
                entry["problems"] = []
                if entry["volume_abs_error_mm3"] is None or entry["volume_abs_error_mm3"] > 1.0:
                    entry["problems"].append("volume outside 1 mm3 of the flat-bottom oracle")
                if entry["feature_delta"].get("hole", 0) != 1:
                    entry["problems"].append(
                        f"hole feature delta={entry['feature_delta'].get('hole')!r}"
                    )
                entry["passed"] = not entry["problems"]
                runner.case(entry)

            reject = await runner.probe(
                "creo_execute_plan",
                {
                    "model_name": unique_name("t12_angle180"),
                    "model_type": "part",
                    "operations": [
                        {
                            **fixture.BASE,
                            "label": "sink_180",
                            "countersink": {"diameter": 10, "angle": 180},
                        }
                    ],
                },
            )
            body = reject["structured"] or {}
            runner.case(
                {
                    "case": "countersink_180_contract",
                    "rejected": bool(reject["is_error"]),
                    "job_id": body.get("job_id"),
                    "message": str(body.get("error") or body.get("message") or reject["text"])[
                        :600
                    ],
                    "passed": bool(reject["is_error"] and not body.get("job_id")),
                }
            )
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {key: case.get(key) for key in ("case", "hole_status", "removed_mm3", "problems", "passed")}
        for case in runner.report["cases"]
    ]
    print(json.dumps({"passed": runner.report["passed"], "cases": rows}, ensure_ascii=False))
    return 0 if runner.report["passed"] else 1


def provenance() -> dict:
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
    names.update(("tests/unit/test_native_countersink.py", "tools/test_native_countersink.py"))
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for name in sorted(names)
    }
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "source_fingerprint": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        return asyncio.run(run_live(args.output))
    suite = unittest.defaultTestLoader.loadTestsFromModule(fixture)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {
        "task": "DEV-051 T12 / FEAT-035",
        "mode": "offline",
        "native_acceptance": "not_run",
        "unit": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
        },
        "oracle_mm3": {
            "counterbore": fixture.oracle_removed(
                6, 12, {"counterbore": {"diameter": 10, "depth": 2}}
            ),
            "countersink": fixture.oracle_removed(
                6, 12, {"countersink": {"diameter": 10, "angle": 90}}
            ),
            "assumption": "flat drill bottom and complete solid intersection; native tip and actual material removal unverified",
        },
        "sdk": "Creo 12.4 ProHole.h custom-hole CBORE/CSINK elements; runtime element acceptance unverified",
        "pending_live": [
            "single native hole feature and element-tree readback",
            "cylinder/frustum geometry",
            "dimension ID edits",
            "revision and rollback",
            "save/reload",
        ],
        "provenance": provenance(),
    }
    run_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    output = args.output or ROOT / "build" / "native_countersink" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    output.with_suffix(".sha256").write_text(digest + "  report.json\n", encoding="ascii")
    print(json.dumps({"report": str(output), "sha256": digest, "passed": result.wasSuccessful()}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
