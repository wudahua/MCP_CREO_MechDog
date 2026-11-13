"""BUG-124/C1: STEP/IGES import must create a real part with a measured quilt.

The native route calls `ProIntfimportModelWithOptionsMdlnameCreate`, which
creates the model itself, so this driver submits a one-operation plan with no
model_id and then reads the receipt the import measured: `create_code`, the
quilt the importer actually produced, its area and whether the job's save /
reload verified. A licence refusal must surface as `PRO_TK_NO_LICENSE`, never as
a generic failure.

Offline (default) checks the schema and the release gate. Live needs the
operator's confirmation for THIS run and a real STEP (and optionally IGES) plus
an explicit import profile:

  .venv\\Scripts\\python.exe tools\\test_import_geometry.py
  .venv\\Scripts\\python.exe tools\\test_import_geometry.py --live --confirm-session-usable \\
      --step D:\\incoming\\bulb.stp --profile D:\\incoming\\step.prof

The operation stays in `UNAVAILABLE_OPERATIONS` until that live run passes, so
live mode refuses while the gate entry is present and prints how to lift it for
one run (and how to put it back when it fails).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OP = "import_geometry"


def checker(checks: list[dict]):
    """A recorder bound to one check list, shaped like the other live drivers."""

    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    return check


def operation(file: Path, profile: Path | None = None, fmt: str = "step") -> dict[str, Any]:
    payload: dict[str, Any] = {"op": OP, "file": str(file), "format": fmt}
    if profile is not None:
        payload["profile"] = str(profile)
    return payload


def case_offline() -> dict:
    """Schema and gate only: no Creo, no import, no model."""
    from unittest.mock import patch

    from creo_mechdog import capabilities
    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []
    check = checker(checks)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        step = root / "sample.stp"
        step.write_bytes(b"ISO-10303-21;")
        profile = root / "sample.prof"
        profile.write_bytes(b"profile")

        (validated,) = validate_operations([operation(step, profile)])
        check(
            "schema_accepts_import_with_profile",
            validated["file_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest(),
            {"file": validated["file"], "format": validated["format"]},
        )
        (default_profile,) = validate_operations([operation(step)])
        check(
            "profile_is_optional",
            "profile" not in default_profile and "profile_sha256" not in default_profile,
            {"fields": sorted(default_profile)},
        )

        iges = root / "sample.igs"
        iges.write_bytes(b"IGES")
        try:
            validate_operations([operation(step, profile, "iges")])
        except ValueError as error:
            check("refuses_format_suffix_mismatch", "needs a .igs or .iges file" in str(error))
        else:
            check("refuses_format_suffix_mismatch", False, {"message": "accepted"})

        for name, broken, expected in (
            ("refuses_missing_input", operation(root / "gone.stp", profile), "does not exist"),
            (
                "refuses_changed_digest",
                {**operation(step, profile), "file_sha256": "0" * 64},
                "does not match the file on disk",
            ),
        ):
            try:
                validate_operations([broken])
            except ValueError as error:
                check(name, expected in str(error), {"message": str(error)[:160]})
            else:
                check(name, False, {"message": "accepted"})

        try:
            validate_operations([operation(step, profile)])
        except ValueError:
            pass  # gate is checked below, not by the schema

        # The gate left UNAVAILABLE_OPERATIONS on 2026-11-13 after this driver's
        # live run passed; a regression must restore the entry, not just this check.
        check(
            "release_gate_is_open_after_the_live_run",
            OP not in capabilities.UNAVAILABLE_OPERATIONS,
            {"gated": OP in capabilities.UNAVAILABLE_OPERATIONS},
        )
        try:
            capabilities.require_available([{"op": OP}])
        except ValueError as error:
            check("registered_operation_is_available", False, {"message": str(error)[:200]})
        else:
            check("registered_operation_is_available", True)

        # The admission rules must keep working on the day the gate is deleted,
        # so they are exercised with the gate lifted in-process only.
        import generic_bridge

        with patch.dict(capabilities.UNAVAILABLE_OPERATIONS, clear=True):
            try:
                generic_bridge.submit([operation(step, profile)], model_id="0" * 32)
            except ValueError as error:
                check("refuses_an_existing_model", "creates its own new part" in str(error))
            else:
                check("refuses_an_existing_model", False, {"message": "accepted"})
            try:
                generic_bridge.submit(
                    [operation(step, profile), {"op": "save"}], model_name="import_probe"
                )
            except ValueError as error:
                check("refuses_a_mixed_plan", "only operation of its plan" in str(error))
            else:
                check("refuses_a_mixed_plan", False, {"message": "accepted"})

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


async def wait_ready(client, budget_seconds: int = 600) -> dict:
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = (await client.call_tool("creo_session_status", {})).structured_content or {}
        if state.get("connected"):
            return state
        await asyncio.sleep(3)
    return state


def receipt_of(state: dict) -> dict:
    """The import receipt, from the job result or the operation list."""
    result = state.get("result") or {}
    if isinstance(result.get(OP), dict):
        return result[OP]
    operations = result.get("operations") or state.get("operations") or []
    for item in operations:
        if isinstance(item, dict) and item.get("op") == OP:
            return item
    return {}


def reload_verified(state: dict) -> bool | None:
    for block in (
        state.get("evidence"),
        (state.get("result") or {}).get("evidence"),
        state.get("result"),
        state,
    ):
        if isinstance(block, dict) and "saved_file_reloaded_and_verified" in block:
            return bool(block["saved_file_reloaded_and_verified"])
    return None


async def one_import(
    client, checks: list[dict], report: dict, file: Path, profile: Path | None, fmt: str
) -> dict:
    """Submit one import and assert what its receipt must prove."""
    from tools.export_elemtree_template import operation_of, submit

    check = checker(checks)
    state = await submit(client, [operation(file, profile, fmt)])
    receipt = operation_of(state, OP) or receipt_of(state)
    report["jobs"].append(
        {
            "format": fmt,
            "file": str(file),
            **{k: state.get(k) for k in ("job_id", "status", "model_id", "revision", "message")},
        }
    )
    report[f"import_{fmt}"] = {
        key: receipt.get(key)
        for key in (
            "create_code",
            "create_code_name",
            "created_model_name",
            "model_type",
            "profile_source",
            "units",
            "feature_count",
            "quilt_count",
            "quilt_closure",
            "area_mm2",
            "area_status",
            "saved_file_reloaded_and_verified",
        )
        if key in receipt
    }
    check(
        f"{fmt}_import_succeeded",
        state.get("status") == "succeeded",
        {"status": state.get("status"), "message": str(state.get("message"))[:300]},
    )
    if state.get("status") != "succeeded":
        return receipt
    check(
        f"{fmt}_create_code_is_zero",
        receipt.get("create_code") == 0,
        {
            "create_code": receipt.get("create_code"),
            "create_code_name": receipt.get("create_code_name"),
        },
    )
    check(
        f"{fmt}_imported_a_quilt",
        isinstance(receipt.get("quilt_count"), int) and receipt["quilt_count"] >= 1,
        {"quilt_count": receipt.get("quilt_count")},
    )
    area = receipt.get("area_mm2")
    check(
        f"{fmt}_area_is_measured",
        isinstance(area, (int, float)) and math.isfinite(area) and area > 0,
        {"area_mm2": area, "area_status": receipt.get("area_status")},
    )
    check(
        f"{fmt}_save_and_reload_verified",
        reload_verified(state) is True,
        {"saved_file_reloaded_and_verified": reload_verified(state)},
    )
    units = receipt.get("units") or {}
    report[f"{fmt}_units"] = units
    check(
        f"{fmt}_units_are_readable",
        isinstance(units.get("name"), str) and bool(units.get("name")),
        {"units": units},
    )
    return receipt


async def case_live(step: Path, profile: Path | None, iges: Path | None) -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from creo_mechdog import capabilities

    report: dict[str, Any] = {"mode": "live", "passed": False, "jobs": [], "checks": []}
    checks: list[dict] = report["checks"]
    check = checker(checks)
    if OP in capabilities.UNAVAILABLE_OPERATIONS:
        report["note"] = (
            "import_geometry is still in UNAVAILABLE_OPERATIONS, so a live run would be "
            "refused before a job. Lift that one entry for THIS run, rerun this driver, and "
            "restore it if any check fails: a pass is what justifies deleting it."
        )
        check("release_gate_lifted", False, {"gate": capabilities.UNAVAILABLE_OPERATIONS[OP][:200]})
        return report
    inputs = [(step, "step")]
    if profile is not None:
        inputs.append((profile, "profile"))
    for path, name in inputs:
        if not path.is_file():
            report["note"] = f"missing {name} file: {path}"
            check(f"{name}_file_exists", False, {"path": str(path)})
            return report
    report["profile_source"] = "explicit" if profile is not None else "creo_default"

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        if not started.get("connected"):
            report["note"] = "the session never reported connected; nothing was submitted"
            check("session_connected", False, {"status": started})
            return report
        check("session_connected", True, {"server_version": started.get("server_version")})
        await one_import(client, checks, report, step, profile, "step")
        if iges is not None and iges.is_file():
            await one_import(client, checks, report, iges, profile, "iges")
        else:
            report["note_iges"] = "no --iges file given; only STEP was imported"
    report["passed"] = bool(checks) and all(item["ok"] for item in checks)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    parser.add_argument("--step", type=Path, help="STEP file to import in live mode")
    parser.add_argument("--iges", type=Path, help="Optional IGES file to import in live mode")
    parser.add_argument(
        "--profile",
        type=Path,
        help="Optional import profile; omitted, Creo's own default import settings are used",
    )
    args = parser.parse_args(argv)
    if args.live and not args.confirm_session_usable:
        raise SystemExit("--live requires --confirm-session-usable")
    if args.live:
        if not args.step:
            raise SystemExit("--live requires --step")
        report = asyncio.run(case_live(args.step, args.profile, args.iges))
    else:
        report = case_offline()
    directory = ROOT / "build" / f"import_geometry_{time.strftime('%Y%m%dT%H%M%S')}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for item in report["checks"]:
        print(f"{'PASS' if item['ok'] else 'FAIL'} {item['check']}")
    print(f"passed: {report['passed']}")
    if report.get("note"):
        print(f"note: {report['note']}")
    print(f"report: {directory / 'report.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
