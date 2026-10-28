"""BUG-064/087 T06 offline sketch-order fixture; never connects to Creo.

The missing original 30-segment slot is represented by a regular 30-gon
made of 30 independent line entities. Its area comes from geometry, not from
the historical profile report. ``--live`` deliberately refuses in this phase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_dev049_tilted_cut import TILTED_FIXTURE, setup_operations, tilted_normal

from creo_mechdog.schema import validate_operations

SIDES = 30
RADIUS_MM = 5.0
RECTANGLE = {"type": "rectangle", "name": "rect", "min": [-4.0, -3.0], "max": [0.0, 3.0]}
ORDERS = (
    "rectangle_then_polygon",
    "polygon_then_rectangle",
    "new_face_rectangle",
    "fresh_part_rectangle",
)
STRATEGIES = ("autodim", "coordinates")
REFERENCES = ("datum_plane_id", "datum_feature_label")
SECOND_REFERENCES = ("available", "unavailable_candidate")


def independent_area_mm2() -> float:
    """Thirty isosceles triangles with circumradius 5 mm."""
    return SIDES * RADIUS_MM * RADIUS_MM * math.sin(2 * math.pi / SIDES) / 2


def polygon_entities() -> list[dict]:
    vertices = [
        [
            RADIUS_MM * math.cos(2 * math.pi * index / SIDES),
            RADIUS_MM * math.sin(2 * math.pi * index / SIDES),
        ]
        for index in range(SIDES)
    ]
    return [
        {
            "type": "line",
            "name": f"poly_{index:02d}",
            "start": vertices[index],
            "end": vertices[(index + 1) % SIDES],
        }
        for index in range(SIDES)
    ]


def sketch(
    kind: str, strategy: str, reference: str, plane_id: int, *, new_face: bool = False
) -> dict:
    if (
        kind not in {"rectangle", "polygon"}
        or strategy not in STRATEGIES
        or reference not in REFERENCES
    ):
        raise ValueError((kind, strategy, reference))
    if reference == "datum_plane_id":
        ref = {"kind": "datum_plane", "id": plane_id}
    else:
        ref = {"kind": "datum_feature", "label": "tilted_new" if new_face else "tilted"}
    if new_face and reference == "datum_plane_id":
        ref = {
            "kind": "datum_plane",
            "id": plane_id + 1,
        }  # Offline placeholder; resolve by geometry live.
    return {
        "op": "sketch",
        "label": f"{'new_face_' if new_face else ''}{kind}",
        "plane": {
            "reference": ref,
            "origin": [0.0, 0.0, 0.0],
            "u_axis": [0.809017, -0.587785, 0.0],
        },
        "entities": [
            dict(RECTANGLE) if kind == "rectangle" else entity
            for entity in (polygon_entities() if kind == "polygon" else [RECTANGLE])
        ],
        "dimensioning": strategy,
    }


def build_cases(run_tag: str, plane_id: int = TILTED_FIXTURE["id"]) -> list[dict]:
    """Each row represents a separate creo_new_part and ordered submissions.

    The unavailable second-reference branch is an inspection target. A real
    session must establish reference count/geometry before that branch may be
    scored; offline input cannot force Toolkit reference selection.
    """
    cases = []
    for strategy in STRATEGIES:
        for reference in REFERENCES:
            for second in SECOND_REFERENCES:
                for order in ORDERS:
                    code = f"{strategy[:2]}_{'id' if reference == 'datum_plane_id' else 'lb'}_{second[:2]}_{ORDERS.index(order)}"
                    first = "polygon" if order == "polygon_then_rectangle" else "rectangle"
                    steps = [first]
                    if order == "rectangle_then_polygon":
                        steps.append("polygon")
                    elif order == "polygon_then_rectangle":
                        steps.append("rectangle")
                    operations = [sketch(kind, strategy, reference, plane_id) for kind in steps]
                    if order == "new_face_rectangle":
                        operations = [
                            sketch("rectangle", strategy, reference, plane_id, new_face=True)
                        ]
                    setup = setup_operations()
                    if order == "new_face_rectangle":
                        setup.append({**setup[-1], "label": "tilted_new"})
                    cases.append(
                        {
                            "case": f"{strategy}_{reference}_{second}_{order}",
                            "model_name": f"t06_{code}_{run_tag}",
                            "new_part_required": True,
                            "setup_operations": setup,
                            "ordered_sketch_submissions": operations,
                            "reference_mode": reference,
                            "second_reference_target": second,
                            "second_reference_must_be_verified_live": True,
                            "fresh_tilted_face_required": order == "new_face_rectangle",
                            "failed_then_same_face_rectangle": {
                                "conditional": True,
                                "only_after": "legal_sketch_natural_failure_and_verified_rollback",
                                "operation": sketch("rectangle", strategy, reference, plane_id),
                            },
                        }
                    )
    return cases


def validate_cases(cases: list[dict]) -> None:
    names = [case["model_name"] for case in cases]
    if len(names) != len(set(names)):
        raise ValueError("duplicate model name")
    for case in cases:
        if len(case["model_name"]) > 31:
            raise ValueError("model name too long")
        validate_operations(case["setup_operations"])
        for operation in case["ordered_sketch_submissions"]:
            validate_operations([operation])
        validate_operations([case["failed_then_same_face_rectangle"]["operation"]])
    if len(cases) != 32:
        raise ValueError("incomplete sequence matrix")


def provenance() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=15
        ).stdout.strip()

    names = set(
        git("ls-files", "--", "*.py", "native/*.h", "native/*.hpp", "native/*.cpp").splitlines()
    )
    names.update(
        {"tools/test_tilted_sketch_lifecycle.py", "tests/unit/test_tilted_sketch_lifecycle.py"}
    )
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


def offline_report(run_tag: str) -> dict:
    cases = build_cases(run_tag)
    validate_cases(cases)
    return {
        "task": "DEV-051 T06",
        "mode": "offline",
        "live_run": False,
        "original_30_segment_case": "missing_request_prt_job_native",
        "replacement": "regular_30gon_30_independent_lines_r5mm",
        "independent_area_oracle_mm2": independent_area_mm2(),
        "area_formula": "30/2 * 5^2 * sin(2*pi/30)",
        "tilted_normal": tilted_normal(),
        "cases": cases,
        "native_acceptance": "not_run",
        "contamination_hypothesis": "not_reproduced_offline",
        "provenance": provenance(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live or args.confirm_session_usable:
        parser.error(
            "T06 offline phase refuses --live and session confirmation; no Creo connection"
        )
    run_tag = uuid.uuid4().hex[:8]
    report = offline_report(run_tag)
    path = args.output or ROOT / "build" / "tilted_sketch_lifecycle" / run_tag / "report.json"
    if path.exists():
        parser.error(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
