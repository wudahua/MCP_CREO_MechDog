"""Live acceptance for the three cards the 0.23.2 batch could not verify offline.

FEAT-067 (bbox assertions), BUG-121 (read-only plans are not blocked by a saved
baseline) and BUG-122 (no false pre-refusal where the element tree is readable)
all need the real kernel; this driver records what each one actually returned.

  .venv\\Scripts\\python.exe tools\\test_0232_live_acceptance.py --live --confirm-session-usable

Everything runs on the operator's own Creo session. A failure in any check does
not stop the rest, so one run shows every card's state at once.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TERMINAL = {"succeeded", "failed", "unknown_outcome", "unsettled"}
# Creo refuses a second model with a name already in the session, so every run
# owns its models; the suffix stays well inside the 31-character ProMdlName.
RUN_TAG = time.strftime("%H%M%S")


def checker(checks: list[dict]):
    def check(name: str, ok: bool, detail: dict | None = None) -> None:
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    return check


async def call_tool(client, tool: str, arguments: dict) -> dict:
    result = await client.call_tool(tool, arguments)
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text[:600]}
    return {}


async def wait_ready(client, budget_seconds: int = 600) -> dict:
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_session_status", {})
        if state.get("connected"):
            return state
        await asyncio.sleep(3)
    return state


async def submit(
    client,
    operations: list[dict[str, Any]],
    *,
    model_id: str | None = None,
    revision: int | None = None,
    assertions: dict | None = None,
    model_name: str | None = None,
    wait_seconds: int = 900,
) -> dict:
    arguments: dict[str, Any] = {"operations": operations}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    if assertions:
        arguments["assertions"] = assertions
    if model_name:
        arguments["model_name"] = model_name
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:800]}
    deadline = time.monotonic() + wait_seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in TERMINAL:
            break
        await asyncio.sleep(2)
    state["job_id"] = job_id
    return state


def job_record(job_id: str | None) -> dict:
    """The accepted job's own manifest: the compact MCP view drops admission fields."""
    if not job_id:
        return {}
    import bridge

    try:
        return bridge.read_json(bridge.job_path(job_id) / "job.json")
    except (OSError, ValueError):
        return {}


def box_plan(*, offset: float = 0.0, height: float = 10.0, name: str = "box") -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": f"{name}_sketch",
            "plane": "XY",
            "offset": offset,
            "entities": [
                {"type": "rectangle", "name": "outline", "min": [0.0, 0.0], "max": [40.0, 40.0]}
            ],
        },
        {
            "op": "extrude",
            "label": f"{name}_solid",
            "sketch": f"{name}_sketch",
            "depth": height,
            "mode": "add",
        },
    ]


def loft_plan(prefix: str, *, sketches: bool) -> list[dict]:
    def line(label, plane, offset, start, end):
        return {
            "op": "sketch",
            "label": label,
            "plane": plane,
            "offset": offset,
            "entities": [{"type": "line", "name": "g", "start": start, "end": end}],
        }

    plan: list[dict] = []
    if sketches:
        plan.extend(
            [
                line(f"{prefix}_a", "XZ", 0.0, [0.0, 0.0], [40.0, 0.0]),
                line(f"{prefix}_b", "XZ", 20.0, [0.0, 0.0], [40.0, 0.0]),
                line(f"{prefix}_c", "XZ", 40.0, [0.0, 0.0], [40.0, 0.0]),
            ]
        )
    plan.append(
        {
            "op": "surface_loft",
            "label": f"{prefix}_loft",
            "sections": [f"{prefix}_a", f"{prefix}_b", f"{prefix}_c"],
            "interpolation": "smooth",
        }
    )
    return plan


async def feat067(client, checks: list[dict], report: dict) -> None:
    """A known 40 x 40 x 10 box must pass, and a wrong box must fail the job."""
    check = checker(checks)
    passed = await submit(
        client,
        box_plan(),
        assertions={"bbox_mm": {"min": [0.0, 0.0, 0.0], "max": [40.0, 40.0, 10.0]}},
        model_name=f"ai_bbox_{RUN_TAG}",
    )
    report["feat067_pass"] = {
        k: passed.get(k) for k in ("job_id", "status", "model_id", "revision", "message")
    }
    check(
        "feat067_true_bbox_passes",
        passed.get("status") == "succeeded",
        {"status": passed.get("status"), "message": str(passed.get("message"))[:300]},
    )
    if passed.get("status") != "succeeded":
        return
    model_id, revision = passed.get("model_id"), passed.get("revision")
    failed = await submit(
        client,
        box_plan(offset=10.0, height=5.0, name="box2"),
        model_id=model_id,
        revision=revision,
        assertions={"bbox_mm": {"min": [0.0, 0.0, 0.0], "max": [40.0, 40.0, 10.0]}},
    )
    report["feat067_fail"] = {k: failed.get(k) for k in ("job_id", "status", "revision", "message")}
    check(
        "feat067_wrong_bbox_fails_the_job",
        failed.get("status") == "failed",
        {"status": failed.get("status"), "message": str(failed.get("message"))[:300]},
    )
    check(
        "feat067_failure_names_the_assertion",
        "Bounding box assertion failed" in str(failed.get("message")),
        {"message": str(failed.get("message"))[:300]},
    )
    after = await call_tool(
        client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
    )
    identity = after.get("identity") if isinstance(after.get("identity"), dict) else {}
    revision_after = after.get("revision", identity.get("revision"))
    report["feat067_after_failed_job"] = {
        "revision": revision_after,
        "failed_job_revision": failed.get("revision"),
        "identity_status": identity.get("status") or after.get("identity_status"),
    }
    check(
        "feat067_failed_job_left_the_model_unchanged",
        revision_after in (None, revision) and failed.get("revision") in (None, revision),
        {"revision_before": revision, "revision_after": revision_after},
    )
    report["feat067_model_id"] = model_id


async def feat067_area(client, checks: list[dict], report: dict) -> None:
    """A 40 x 40 x 10 box is 4800 mm2 of surface; a wrong expectation fails."""
    check = checker(checks)
    passed = await submit(
        client,
        box_plan(),
        assertions={"surface_area_mm2": 4800.0, "surface_area_tolerance_mm2": 0.5},
        model_name=f"ai_area_{RUN_TAG}",
    )
    report["feat067_area_pass"] = {
        k: passed.get(k) for k in ("job_id", "status", "model_id", "revision", "message")
    }
    check(
        "feat067_true_area_passes",
        passed.get("status") == "succeeded",
        {"status": passed.get("status"), "message": str(passed.get("message"))[:300]},
    )
    if passed.get("status") != "succeeded":
        return
    model_id, revision = passed.get("model_id"), passed.get("revision")
    failed = await submit(
        client,
        box_plan(offset=10.0, height=5.0, name="box2"),
        model_id=model_id,
        revision=revision,
        assertions={"surface_area_mm2": 4800.0, "surface_area_tolerance_mm2": 0.5},
    )
    report["feat067_area_fail"] = {
        k: failed.get(k) for k in ("job_id", "status", "revision", "message")
    }
    check(
        "feat067_wrong_area_fails_the_job",
        failed.get("status") == "failed",
        {"status": failed.get("status"), "message": str(failed.get("message"))[:300]},
    )
    check(
        "feat067_area_failure_names_the_assertion",
        "Surface area assertion failed" in str(failed.get("message")),
        {"message": str(failed.get("message"))[:300]},
    )
    after = await call_tool(
        client, "creo_inspect_model", {"model_id": model_id, "detail": "compact"}
    )
    identity = after.get("identity") if isinstance(after.get("identity"), dict) else {}
    revision_after = after.get("revision", identity.get("revision"))
    report["feat067_area_after_failed_job"] = {
        "revision": revision_after,
        "failed_job_revision": failed.get("revision"),
    }
    check(
        "feat067_area_failed_job_left_the_model_unchanged",
        revision_after in (None, revision) and failed.get("revision") in (None, revision),
        {"revision_before": revision, "revision_after": revision_after},
    )
    report["feat067_area_model_id"] = model_id


async def bug121(client, checks: list[dict], report: dict) -> None:
    """A read-only plan on an existing model keeps working and says why it is read-only."""
    check = checker(checks)
    created = await submit(client, box_plan(name="ro"), model_name=f"ai_ro_{RUN_TAG}")
    report["bug121_create"] = {k: created.get(k) for k in ("job_id", "status", "model_id")}
    if created.get("status") != "succeeded":
        check("bug121_model_created", False, {"status": created.get("status")})
        return
    check("bug121_model_created", True)
    model_id, revision = created.get("model_id"), created.get("revision")
    exported = await submit(
        client, [{"op": "export", "format": "step"}], model_id=model_id, revision=revision
    )
    manifest = job_record(exported.get("job_id"))
    report["bug121_export"] = {
        k: exported.get(k) for k in ("job_id", "status", "message", "revision") if k in exported
    } | {"readonly": manifest.get("readonly"), "readonly_source": manifest.get("readonly_source")}
    check(
        "bug121_read_only_export_succeeds",
        exported.get("status") == "succeeded",
        {"status": exported.get("status"), "message": str(exported.get("message"))[:300]},
    )
    check(
        "bug121_read_only_source_is_recorded",
        manifest.get("readonly") is True
        and manifest.get("readonly_source") == "inspection_only_plan",
        {
            "readonly": manifest.get("readonly"),
            "readonly_source": manifest.get("readonly_source"),
        },
    )
    report["bug121_model_id"] = model_id


async def bug122(client, checks: list[dict], report: dict) -> None:
    """Two lofts in one model must both run where the element tree is readable."""
    check = checker(checks)
    first = await submit(client, loft_plan("l1", sketches=True), model_name=f"ai_reuse_{RUN_TAG}")
    report["bug122_first"] = {k: first.get(k) for k in ("job_id", "status", "model_id")}
    check(
        "bug122_first_loft_succeeds",
        first.get("status") == "succeeded",
        {"status": first.get("status"), "message": str(first.get("message"))[:300]},
    )
    if first.get("status") != "succeeded":
        return
    model_id, revision = first.get("model_id"), first.get("revision")
    second = await submit(
        client, loft_plan("l2", sketches=True), model_id=model_id, revision=revision
    )
    report["bug122_second"] = {
        k: second.get(k) for k in ("job_id", "status", "message", "revision")
    }
    check(
        "bug122_second_loft_is_not_refused",
        second.get("status") == "succeeded",
        {"status": second.get("status"), "message": str(second.get("message"))[:300]},
    )
    check(
        "bug122_no_prerefusal_message",
        "refused before a job" not in str(second.get("message")),
        {"message": str(second.get("message"))[:300]},
    )
    report["bug122_model_id"] = model_id


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    report: dict[str, Any] = {"mode": "live", "passed": False, "checks": []}
    checks: list[dict] = report["checks"]
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        if not started.get("connected"):
            report["note"] = "the session never reported connected; nothing was submitted"
            return report
        report["session"] = {
            k: started.get(k) for k in ("server_version", "release_numeric", "worker_sha256")
        }
        for name, run in (
            ("feat067", feat067),
            ("feat067_area", feat067_area),
            ("bug121", bug121),
            ("bug122", bug122),
        ):
            try:
                await run(client, checks, report)
            except Exception as error:  # one card's failure must not hide the others
                checker(checks)(f"{name}_ran", False, {"error": f"{type(error).__name__}: {error}"})
    report["passed"] = bool(checks) and all(item["ok"] for item in checks)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--confirm-session-usable", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_session_usable:
        raise SystemExit("--live requires --confirm-session-usable")
    report = asyncio.run(case_live())
    directory = ROOT / "build" / f"live_acceptance_{time.strftime('%Y%m%dT%H%M%S')}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for item in report["checks"]:
        print(f"{'PASS' if item['ok'] else 'FAIL'} {item['check']}")
    print(f"passed: {report['passed']}")
    print(f"report: {directory / 'report.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
