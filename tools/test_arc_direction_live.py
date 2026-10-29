"""FEAT-034 live acceptance: explicit arc ``dir`` shapes the intended segment.

Default is strict offline (contract + oracle only). ``--live --confirm-session-usable``
connects to a Creo session the user opened manually and measures one arc+chord
extrusion per case; it never launches or closes Creo and never resubmits a job.

Geometry: radius 10 mm arc plus its chord, extruded 5 mm. Independent oracle is
``depth * 0.5 * r^2 * (theta - sin(theta))`` with theta from the T02 sweep rule,
computed here without calling production normalization.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RADIUS_MM = 10.0
DEPTH_MM = 5.0
TOLERANCE_MM3 = 0.01


def oracle_sweep_deg(start_deg: float, end_deg: float, direction: int) -> float:
    if direction > 0:
        return (end_deg - start_deg) % 360.0
    return (start_deg - end_deg) % 360.0


def oracle_volume_mm3(start_deg: float, end_deg: float, direction: int) -> float:
    theta = math.radians(oracle_sweep_deg(start_deg, end_deg, direction))
    return DEPTH_MM * 0.5 * RADIUS_MM * RADIUS_MM * (theta - math.sin(theta))


def on_circle(angle_deg: float) -> list[float]:
    angle = math.radians(angle_deg)
    return [RADIUS_MM * math.cos(angle), RADIUS_MM * math.sin(angle)]


def operations(start_deg: float, end_deg: float, direction: int | None) -> list[dict]:
    arc: dict[str, Any] = {
        "type": "arc",
        "name": "arc_a",
        "center": [0.0, 0.0],
        "radius": RADIUS_MM,
        "start_angle": start_deg,
        "end_angle": end_deg,
    }
    if direction is not None:
        arc["dir"] = direction
    chord = {
        "type": "line",
        "name": "chord_a",
        "start": on_circle(end_deg),
        "end": on_circle(start_deg),
    }
    return [
        {
            "op": "sketch",
            "label": "seg",
            "plane": "XY",
            "entities": [arc, chord],
            "dimensioning": "coordinates",
        },
        {"op": "extrude", "label": "body", "sketch": "seg", "depth": DEPTH_MM},
    ]


CASES: list[dict] = [
    {"case": "legacy_0_to_90", "start": 0.0, "end": 90.0, "dir": None},
    {"case": "legacy_90_to_0", "start": 90.0, "end": 0.0, "dir": None},
    {"case": "dir_minus1_90_to_0", "start": 90.0, "end": 0.0, "dir": -1},
    {"case": "dir_minus1_0_to_90", "start": 0.0, "end": 90.0, "dir": -1},
]


def require_manual_start(config_file: Path) -> None:
    settings = json.loads(config_file.read_text(encoding="utf-8-sig"))
    if settings.get("auto_start_creo") is not False:
        raise ValueError(
            "Live acceptance requires config.json auto_start_creo=false; no client was started"
        )


async def live(output: Path) -> None:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    require_manual_start(ROOT / "config.json")
    report: dict[str, Any] = {
        "task": "DEV-051 T02",
        "scope": "FEAT-034 explicit arc dir, live geometry",
        "mode": "live",
        "started_at": time.time(),
        "cases": [],
        "calls": 0,
    }
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=120) as client:

        async def call(name: str, args: dict, allow_error: bool = False) -> dict:
            report["calls"] += 1
            result = await client.call_tool(name, args)
            if result.is_error and not allow_error:
                raise RuntimeError(f"{name}: {result.content}")
            return result

        deadline = time.monotonic() + 180
        while True:
            status = (await call("creo_startup_status", {})).structured_content or {}
            if status.get("state") == "ready" and status.get("connected") is True:
                break
            if time.monotonic() >= deadline:
                output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                raise TimeoutError("session not ready; nothing submitted")
            await asyncio.sleep(1)
        report["status"] = status

        for case in CASES:
            ops = operations(case["start"], case["end"], case["dir"])
            created = await call("creo_execute_plan", {"operations": ops})
            body = created.structured_content or {}
            job_id = body.get("job_id")
            model_id = body.get("model_id")
            terminal = body
            poll_deadline = time.monotonic() + 300
            while terminal.get("status") in ("queued", "running"):
                terminal = (await call("creo_get_job", {"job_id": job_id})).structured_content or {}
                if time.monotonic() >= poll_deadline:
                    raise TimeoutError(f"{job_id} did not settle; do not resubmit")
                if terminal.get("status") in ("queued", "running"):
                    await asyncio.sleep(1)
            assert terminal.get("status") == "succeeded", terminal
            inspection = (
                await call("creo_inspect_model", {"model_id": model_id})
            ).structured_content
            inspection = inspection or {}
            inner = inspection.get("inspection", inspection)
            measured = inner.get("volume_mm3")
            direction = 1 if case["dir"] is None else case["dir"]
            expected = oracle_volume_mm3(case["start"], case["end"], direction)
            results = terminal.get("result", {}).get("operations", [])
            echo = None
            for operation in results:
                for entity in operation.get("arc_geometry") or []:
                    echo = entity
            report["cases"].append(
                {
                    "case": case["case"],
                    "dir": case["dir"],
                    "start_angle": case["start"],
                    "end_angle": case["end"],
                    "job_id": job_id,
                    "model_id": model_id,
                    "revision": terminal.get("revision"),
                    "expected_volume_mm3": expected,
                    "measured_volume_mm3": measured,
                    "abs_error_mm3": None if measured is None else abs(measured - expected),
                    "arc_echo": echo,
                    "saved_file_reloaded_and_verified": terminal.get(
                        "saved_file_reloaded_and_verified"
                    ),
                    "passed": measured is not None and abs(measured - expected) <= TOLERANCE_MM3,
                }
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            failed = [row for row in report["cases"] if not row["passed"]]
            if failed:
                raise AssertionError(failed)

    report["finished_at"] = time.time()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def offline() -> int:
    rows = []
    for case in CASES:
        direction = 1 if case["dir"] is None else case["dir"]
        rows.append(
            {
                "case": case["case"],
                "sweep_deg": oracle_sweep_deg(case["start"], case["end"], direction),
                "expected_volume_mm3": oracle_volume_mm3(case["start"], case["end"], direction),
            }
        )
    print(json.dumps({"mode": "offline", "oracle": rows}, ensure_ascii=False, indent=2))
    print("LIVE NOT RUN: no MCP client, no Toolkit call, no Creo connection.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "build/arc_direction_live.json")
    args = parser.parse_args(argv)
    if not (args.live and args.confirm_session_usable):
        return offline()
    asyncio.run(live(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
