"""DEV-051 T05 box driver: third-wall contrast design and end_trim_mm contract.

The 2026-10-29 round six left the four-wall box at 2/4: f_px and f_nx built as
real 90-degree bends, then the third wall f_ny failed inside regeneration
(feature status 6, empty geometry), the health check failed the job and the
model rolled back. Corner interference is a candidate, not a cause: no contrast
has run yet.

This driver freezes the offline half of the mandated contrast experiment. It
does not connect to Creo and does not decide the cause:

1. the three contrast groups on the confirmed 185x232x1 base (full-length third
   wall, the same wall trimmed 20 mm short of both chain ends, and the order
   gradient that gives f_ny 0, 1 and 2 material corners), each on a fresh model
   with one job per wall and a fresh edge inspection;
2. the ``end_trim_mm`` contract the trimmed group needs: both depth sides blind
   with the requested offset, gated on a free-wall probe that classifies the
   blind-offset semantics (setback from each chain end vs length from the
   section) from the measured volume before any trimmed third wall is trusted;
3. the per-stage record a live run must fill for a failing wall (submission,
   terminal failure, UNHEALTHY_FEATURES status/geometry, health-check message,
   restored revision/volume) and the corner decision table, where corner
   interference becomes "supported" only when the trim contrast and the order
   gradient agree;
4. static guards over the native trim branch and the schema/server contract.

Default is strictly offline: no MCP client, no Toolkit connection, no job.
--live needs --confirm-session-usable and is still refused here; the four-wall
live acceptance belongs to the single shared dev service integration step.
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
from tests.unit import test_sheetmetal_box_live as box  # noqa: E402
from tests.unit import test_sheetmetal_flange as fx  # noqa: E402
from tests.unit import test_sheetmetal_relief as relief  # noqa: E402

ROOT = SOURCE_PATHS.resource_root


# --- checks ---------------------------------------------------------------


def check_contrast_design() -> dict:
    groups = box.contrast_groups()
    return {
        "trim_mm": box.TRIM_MM,
        "groups": {
            name: {
                "order": group["order"],
                "trim_third": group["trim_third"],
                "why": group["why"],
                "walls": group["walls"],
                "f_ny_material_corners": group["f_ny_material_corners"],
            }
            for name, group in groups.items()
        },
        "corner_gradient": {
            name: groups[name]["f_ny_material_corners"]
            for name in ("order_ny_first", "order_ny_second", "full_length", "trimmed_20")
        },
        "rules": [
            "one fresh model per group; one job per wall",
            "every wall's edge is re-selected from a fresh inspection with an explicit face",
            "the trimmed group only runs after the free-wall probe confirms the setback "
            "reading of the blind offset",
        ],
        "statement": (
            "the contrast design is frozen offline; no group has run, so no outcome is "
            "recorded and corner interference stays a candidate"
        ),
    }


def check_oracle_rows() -> dict:
    rows = {name: box.offline_plan_rows(name) for name in box.contrast_groups()}
    trimmed = rows["trimmed_20"][-1]
    assert trimmed["label"] == "f_ny" and trimmed["end_trim_mm"] == box.TRIM_MM
    assert abs(trimmed["effective_span_mm"] - (trimmed["fixture_span_mm"] - 2 * box.TRIM_MM)) < 1e-9
    assert (
        abs(
            trimmed["expected_added_mm3"]
            - relief.bent_wall_increment_mm3(trimmed["effective_span_mm"])
        )
        < 1e-6
    )
    return {
        "rows": rows,
        "oracle_basis": (
            "bent-wall increment (span x height x thickness with the bend-arc correction) "
            "validated against the measured 2026-10-29 walls"
        ),
        "trim_rows_are_setback_reading_only": True,
        "statement": (
            "offline expectations assume full fixture spans and the setback trim reading; "
            "the live driver recomputes every expectation from the measured span"
        ),
    }


def check_trim_probe() -> dict:
    operations, reference = box.trim_probe_plan()
    interpretations = {
        span: box.trim_interpretations(span) for span in (fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM)
    }
    self_check = {
        name: box.classify_trim_semantics(expected, fx.PLATE_WIDTH_MM)["semantics"]
        for name, expected in interpretations[fx.PLATE_WIDTH_MM].items()
    }
    assert all(got == name for name, got in self_check.items()), self_check
    return {
        "probe_wall": "f_px on +x as the first wall (both bend ends at free plate corners)",
        "probe_operations": len(operations),
        "probe_reference": reference["geometry"],
        "interpretations": interpretations,
        "classifier_self_check": self_check,
        "gating": (
            "the trimmed third wall is submitted only when the probe classifies the "
            "semantics as setback_from_ends; any other reading keeps the trim contrast "
            "inconclusive about corner clearance"
        ),
    }


def check_admission() -> dict:
    plans = box.group_plans_validate()
    probe, _ = box.trim_probe_plan()
    return {
        "groups": plans,
        "probe_plan_last_operation": probe[-1],
        "statement": (
            "every group's base plan and per-wall request, plus the trimmed probe plan, "
            "pass validate_operations with the shared contract"
        ),
    }


def check_native_trim_branch() -> dict:
    guard = box.native_source()
    return {
        **guard,
        "statement": (
            "end_trim_mm switches both flange depth sides from TO_END to blind with the "
            "requested offset and nothing else; calls without the field keep the stock "
            "TO_END tree byte-for-byte"
        ),
    }


def check_contract() -> dict:
    return box.contract_source()


def check_stage_record_contract() -> dict:
    """Exercise the stage-record helpers on the round-six synthetic line.

    This is a fixture self-check, not a live result: it proves the live driver
    can recognise the round-six failure shape and will record deviations as new
    evidence instead of forcing them into the old shape.
    """
    unhealthy_line = (
        'UNHEALTHY_FEATURES=[{"id":9,"type":17,"type_name":"WALL","status":6,'
        '"incomplete":false,"name":"f_ny","dimensions":[],"geometry_items":[],'
        '"parent_ids":[],"child_ids":[]}]'
    )
    snapshot = {"revision": 3, "inspection": {"volume_mm3": 80_040.0}}
    stage = box.third_wall_stage_record(
        "f_ny",
        "job-synthetic",
        {
            "status": "failed",
            "message": "Regeneration produced a failed, suppressed or incomplete feature",
        },
        unhealthy_line,
        3,
        80_040.0,
        snapshot,
    )
    verdict = box.failed_wall_verdict(stage, "f_ny")
    assert verdict["matches_round_six_shape"], verdict
    deviation = box.failed_wall_verdict(
        box.third_wall_stage_record(
            "f_ny",
            "job-synthetic",
            {"status": "failed", "message": "other"},
            None,
            3,
            80_040.0,
            snapshot,
        ),
        "f_ny",
    )
    assert not deviation["matches_round_six_shape"]
    return {
        "stages": [
            "stage_submission",
            "stage_terminal",
            "stage_feature_state (from the native log's UNHEALTHY_FEATURES dump)",
            "stage_health_check",
            "stage_rollback (revision and volume restored)",
        ],
        "round_six_shape_recognised": True,
        "deviation_recorded_not_forced": True,
        "statement": (
            "the live run fills each stage from observation; a failing wall that does not "
            "match the round-six shape is recorded as a new observation"
        ),
        "synthetic_only": True,
    }


def check_corner_decision_table() -> dict:
    reachable = {
        "incomplete_run": box.corner_decision({"full_length": "third_failed"})["conclusion"],
        "not_reproduced": box.corner_decision(
            {
                "full_length": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            }
        )["conclusion"],
        "zero_corner_failure_refutes_corners": box.corner_decision(
            {
                "full_length": "third_failed",
                "order_ny_first": "third_failed",
                "order_ny_second": "third_succeeded",
            }
        )["conclusion"],
        "trim_builds_but_semantics_unconfirmed": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="unresolved",
        )["conclusion"],
        "corner_interference_supported": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_succeeded",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )["conclusion"],
        "trimmed_wall_also_fails_refutes_corners": box.corner_decision(
            {
                "full_length": "third_failed",
                "trimmed_20": "third_failed",
                "order_ny_first": "third_succeeded",
                "order_ny_second": "third_succeeded",
            },
            trim_semantics="setback_from_ends",
        )["conclusion"],
    }
    return {
        "reachable_conclusions": reachable,
        "corner_interference_now": "candidate_only_no_contrast_run",
        "statement": (
            "offline, no observation exists, so the standing conclusion is "
            "undetermined_incomplete; corner interference becomes supported only when the "
            "trim contrast and the order gradient agree with the setback semantics confirmed"
        ),
    }


def check_round_six_evidence() -> dict:
    report = ROOT / "build" / "sheetmetal_relief" / "20261029T222754_44e6ab6a" / "report.json"
    return {
        **box.ROUND_SIX,
        "report_present": report.exists(),
        "statement": (
            "round six is the starting observation (status=6, empty geometry, rollback); it "
            "is a candidate shape, not a cause, and this run does not resubmit anything"
        ),
    }


def live_checklist() -> list[str]:
    return [
        "confirm the session is usable and BUG-001 conditions hold; one dev service only "
        "(MCP_CREO_MechDog_dev)",
        "fresh model per group with a unique name; record job/model/revision and the base "
        "wall volume (42 920 mm³)",
        "first run the trim-semantics probe: one free first wall (f_px on +x) with "
        "end_trim_mm=20; classify the semantics from the measured increment with "
        "box.classify_trim_semantics; record extra['depth_trim'] from the echo",
        "only when the probe says setback_from_ends, run the trimmed_20 group; otherwise "
        "record the semantics and skip the trim (the cause stays undetermined)",
        "run full_length, order_ny_first and order_ny_second; one job per wall, edge "
        "re-selected from a fresh inspection with an explicit face, assert_edge_current "
        "before each submit",
        "for each wall record the full judgement fields and, after each, bbox (material "
        "side and direction), revision and volume",
        "on a failing wall fill third_wall_stage_record from the terminal payload, the "
        "native log's UNHEALTHY_FEATURES dump and the post-failure snapshot; never "
        "resubmit the failed edge",
        "map the four outcomes with box.corner_decision; only the agreed trim+order "
        "contrast may raise corner interference to supported",
        "stop on first unknown/hang (180 s budget per job), keep the scene and hand over",
    ]


def run_unit_module() -> dict:
    from tests.unit import test_sheetmetal_box_live

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sheetmetal_box_live)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    return {
        "module": "tests.unit.test_sheetmetal_box_live",
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
        else ROOT / "build" / "sheetmetal_box" / run_id / "report.json"
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
    names.update(
        (
            "tools/test_sheetmetal_box_live.py",
            "tests/unit/test_sheetmetal_box_live.py",
            "tools/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_flange.py",
            "tests/unit/test_sheetmetal_relief.py",
            "tools/sheetmetal_live.py",
        )
    )
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
        "task": "FEAT-014 / BUG-047 / DEV-051 T05",
        "scope": (
            "third-wall contrast design: full-length / trimmed-20 / order gradient on the "
            "confirmed 1 mm base wall, the end_trim_mm contract with its semantics probe, "
            "the failing-wall stage record and the corner decision table"
        ),
        "run_id": run_id,
        "mode": "offline",
        "live_run": False,
        "native_acceptance": "not_run",
        "status": {
            "reproduction": "not_run_offline",
            "root_cause": "undetermined",
            "corner_interference": "candidate_only_no_contrast_run",
            "production_change": (
                "end_trim_mm: opt-in blind depth on both flange sides (advanced.cpp, "
                "schema.py, server.py); the stock tree is unchanged without the field"
            ),
            "statement": (
                "Offline only: the contrast design, trim contract, stage record and decision "
                "table are frozen and the executor builds. No Toolkit connection, no wall "
                "created, no failure reproduced and corner interference is not a cause."
            ),
        },
        "fixture": {
            "base_wall_mm": [fx.PLATE_LENGTH_MM, fx.PLATE_WIDTH_MM, fx.PLATE_THICKNESS_MM],
            "base_volume_mm3": fx.PLATE_VOLUME_MM3,
            "flange": {
                "height": fx.FLANGE_HEIGHT_MM,
                "radius": fx.FLANGE_RADIUS_MM,
                "y_factor": fx.FLANGE_Y_FACTOR,
                "angle": fx.FLANGE_ANGLE_DEG,
                "flip": False,
            },
            "trim_mm": box.TRIM_MM,
            "hang_budget_seconds": box.HANG_BUDGET_SECONDS,
        },
        "checks": results,
        "live_checklist": live_checklist(),
        "not_verified": [
            "no wall was created in this run; the trim-semantics probe has not run",
            "the third-wall failure is not reproduced here and no hypothesis is resolved",
            "the trimmed group's geometry depends on the probe outcome and is unmeasured",
            "four-wall capability remains open: unbend/bend-back, edit, reload and rollback "
            "are all untested",
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
        print(box.LIVE_REFUSAL, file=sys.stderr)
        return 2

    run_id = new_run_id()
    output = resolve_output(args.output, run_id)
    results = {
        "contrast_design": check_contrast_design(),
        "oracle_rows": check_oracle_rows(),
        "trim_probe": check_trim_probe(),
        "admission": check_admission(),
        "native_trim_branch": check_native_trim_branch(),
        "contract": check_contract(),
        "stage_record_contract": check_stage_record_contract(),
        "corner_decision_table": check_corner_decision_table(),
        "round_six_evidence": check_round_six_evidence(),
    }
    report = write_offline_report(output, run_id, results)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_name("report.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"report: {output}")
    print(f"report_sha256: {digest}")
    print(f"status: {report['status']['reproduction']} / {report['status']['root_cause']}")
    print(f"unit_module: {report['unit_module']}")
    return 0 if report["unit_module"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
