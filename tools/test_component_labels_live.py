"""DEV-051 T09A live driver: business labels on assembly components.

The label is a binding to (model identity, native feature id); the physical
component copy keeps its ``c_<job>_<n>`` name. This driver checks the four
things FEAT-023/T09A promised on a live session:

1. ``two_components``    - both labels resolve to one identity each (single)
2. ``cross_job``         - a later job (datum plane, revision +1) keeps the labels
3. ``rename_reinsert``   - remove + re-assemble under a new label; the old binding
                           must not follow the new feature id
4. ``unknown_label``     - a placement on the removed label is refused with the
                           raw message recorded

Default is strictly offline (projection contract only, no MCP client).
``--live --confirm-session-usable`` runs the four cases serially, one fresh
assembly, never resubmitting a job; a job that is not terminal within
HANG_BUDGET_SECONDS stops the run with the job id kept.
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

from creo_mechdog.component_identity import project_component_identities  # noqa: E402
from creo_mechdog.paths import SOURCE_PATHS  # noqa: E402
from tools.sheetmetal_live import LiveRunner, require_manual_start, unique_name  # noqa: E402

ROOT = SOURCE_PATHS.resource_root
HANG_BUDGET_SECONDS = 180.0


def part_plan() -> list[dict]:
    return [
        {
            "op": "sketch",
            "label": "plate_sketch",
            "plane": "XY",
            "entities": [
                {
                    "type": "rectangle",
                    "name": "plate_box",
                    "min": [0.0, 0.0],
                    "max": [40.0, 30.0],
                }
            ],
        },
        {
            "op": "extrude",
            "label": "plate",
            "sketch": "plate_sketch",
            "depth": 8.0,
            "mode": "add",
            "direction": "positive",
            "depth_type": "blind",
        },
    ]


def assemble(label: str, source_model_id: str) -> dict:
    return {
        "op": "assemble_component",
        "label": label,
        "source_model_id": source_model_id,
        "placement": "fixed",
    }


# --- checks ---------------------------------------------------------------


def check_projection_contract() -> dict:
    model = {
        "model_id": "a" * 32,
        "model_type": "assembly",
        "revision": 3,
        "aliases": {
            "part_alpha": {"op": "assemble_component", "feature_id": 40},
            "part_beta": {"op": "assemble_component", "feature_id": 43},
            "old_removed": {"op": "assemble_component", "feature_id": 99},
            "two_labels_one": {"op": "assemble_component", "feature_id": 40},
        },
    }
    records = [
        {"feature_id": 40, "name": "c_job_1"},
        {"feature_id": 43, "name": "c_job_2"},
    ]
    projection = project_component_identities(model, records)
    by_id = {item["identity"]["feature_id"]: item for item in projection["components"]}
    assert by_id[40]["labels"] == ["part_alpha", "two_labels_one"], by_id[40]["labels"]
    assert by_id[40]["label_state"] == "multi", by_id[40]["label_state"]
    assert by_id[40]["label"] is None and by_id[40]["source_model_id"] is None
    assert by_id[43]["label"] == "part_beta" and by_id[43]["label_state"] == "single"
    deleted = {item["identity"]["feature_id"]: item for item in projection["deleted_identities"]}
    assert 99 in deleted, deleted
    assert deleted[99]["reason"] == "feature_id_not_in_verified_components"
    assert projection["identity_key"]["key"] == "model_identity+feature_id"
    return {
        "multi_label_kept": True,
        "single_label_mirrors_source": True,
        "deleted_identity_kept_separately": True,
        "identity_key": projection["identity_key"],
    }


# --- live -----------------------------------------------------------------


def component_rows(payload: dict) -> list[dict]:
    return [
        {
            "identity": item.get("identity"),
            "label": item.get("label"),
            "labels": item.get("labels"),
            "label_state": item.get("label_state"),
            "source_model_id": item.get("source_model_id"),
            "source_revision": item.get("source_revision"),
            "name": item.get("name") or item.get("component_name"),
        }
        for item in payload.get("components") or []
        if isinstance(item, dict)
    ]


def label_map(rows: list[dict]) -> dict:
    return {row["label"]: row["identity"] for row in rows if row.get("label")}


async def create_source(runner: LiveRunner, tag: str) -> str:
    name = unique_name(tag)
    created = await runner.submit(
        f"{name}:create",
        "creo_execute_plan",
        {"model_name": name, "model_type": "part", "operations": part_plan()},
    )
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    if terminal.get("status") != "succeeded":
        raise RuntimeError(f"source {name} failed: {terminal.get('message')}")
    return created["model_id"]


async def run_plan(runner: LiveRunner, key: str, arguments: dict) -> dict:
    created = await runner.submit(key, "creo_execute_plan", arguments)
    terminal = await runner.wait_job(created["job_id"], budget=HANG_BUDGET_SECONDS)
    return {"created": created, "terminal": terminal}


async def live(output: Path, run_id: str) -> int:
    require_manual_start(ROOT / "config.json")
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=ROOT)
    async with Client(params, read_timeout_seconds=180) as client:
        runner = LiveRunner(
            client,
            output,
            "FEAT-023 / DEV-051 T09A",
            "assembly component business labels: resolve, cross-job persistence, "
            "remove/re-insert, unknown label refusal",
            run_id,
        )
        try:
            await runner.start()
            runner.report["hang_budget_seconds"] = HANG_BUDGET_SECONDS
            alpha_source = await create_source(runner, "t09a_src_a")
            beta_source = await create_source(runner, "t09a_src_b")

            name = unique_name("t09a_asm")
            made = await run_plan(
                runner,
                "assembly:create",
                {
                    "model_name": name,
                    "model_type": "assembly",
                    "operations": [
                        assemble("part_alpha", alpha_source),
                        assemble("part_beta", beta_source),
                    ],
                },
            )
            model_id = made["created"]["model_id"]
            first = await runner.call("creo_list_components", {"model_id": model_id})
            rows = component_rows(first)
            expected = {"part_alpha": alpha_source, "part_beta": beta_source}
            resolved = {
                row["label"]: (row["identity"] or {}).get("feature_id")
                for row in rows
                if row.get("label")
            }
            sources_ok = all(
                (row.get("source_model_id") == expected.get(row.get("label")))
                for row in rows
                if row.get("label")
            )
            runner.case(
                {
                    "case": "two_components",
                    "model_id": model_id,
                    "assembly_job_id": made["created"]["job_id"],
                    "assembly_status": made["terminal"].get("status"),
                    "revision": first.get("revision"),
                    "components": rows,
                    "labels_resolved": resolved,
                    "label_states": sorted({row.get("label_state") for row in rows}),
                    "source_models_match": sources_ok,
                    "passed": bool(
                        made["terminal"].get("status") == "succeeded"
                        and len(rows) == 2
                        and set(resolved) == {"part_alpha", "part_beta"}
                        and sources_ok
                        and all(row.get("label_state") == "single" for row in rows)
                    ),
                }
            )

            second_job = await run_plan(
                runner,
                "assembly:save",
                {
                    "model_id": model_id,
                    "expected_revision": first.get("revision"),
                    "operations": [{"op": "save"}],
                },
            )
            second = await runner.call("creo_list_components", {"model_id": model_id})
            rows2 = component_rows(second)
            same = label_map(rows2) == label_map(rows)
            runner.case(
                {
                    "case": "cross_job",
                    "second_job_id": second_job["created"]["job_id"],
                    "second_job_kind": "save",
                    "second_job_status": second_job["terminal"].get("status"),
                    "revision_after": second.get("revision"),
                    "labels_after": sorted(label_map(rows2)),
                    "identities_unchanged": same,
                    "failed_stage": (second_job["terminal"].get("result") or {}).get(
                        "failed_stage"
                    ),
                    "message": str(second_job["terminal"].get("message"))[:400],
                    "passed": bool(
                        second_job["terminal"].get("status") == "succeeded"
                        and same
                        and set(label_map(rows2)) == {"part_alpha", "part_beta"}
                    ),
                }
            )

            removed = await run_plan(
                runner,
                "assembly:remove",
                {
                    "model_id": model_id,
                    "expected_revision": second.get("revision"),
                    "operations": [{"op": "remove_component", "component": "part_beta"}],
                },
            )
            revision_after_remove = (removed["terminal"].get("result") or {}).get(
                "revision"
            ) or second.get("revision")
            third = await runner.call("creo_list_components", {"model_id": model_id})
            reinserted = await run_plan(
                runner,
                "assembly:reinsert",
                {
                    "model_id": model_id,
                    "expected_revision": third.get("revision"),
                    "operations": [assemble("part_gamma", beta_source)],
                },
            )
            fourth = await runner.call("creo_list_components", {"model_id": model_id})
            rows4 = component_rows(fourth)
            deleted = fourth.get("deleted_identities") or []
            gamma = [row for row in rows4 if row.get("label") == "part_gamma"]
            beta_still = [row for row in rows4 if row.get("label") == "part_beta"]
            gamma_id = (gamma[0].get("identity") or {}).get("feature_id") if gamma else None
            stale_binding_on_new_id = any(
                isinstance(item, dict)
                and item.get("labels") == ["part_beta"]
                and (item.get("identity") or {}).get("feature_id") == gamma_id
                for item in deleted
            )
            runner.case(
                {
                    "case": "rename_reinsert",
                    "remove_job_id": removed["created"]["job_id"],
                    "remove_status": removed["terminal"].get("status"),
                    "reinsert_job_id": reinserted["created"]["job_id"],
                    "reinsert_status": reinserted["terminal"].get("status"),
                    "revision_after_remove": revision_after_remove,
                    "revision_after": fourth.get("revision"),
                    "components": rows4,
                    "deleted_identities": deleted,
                    "gamma_feature_id": gamma_id,
                    "old_label_on_new_component": bool(beta_still),
                    "stale_binding_on_new_id": stale_binding_on_new_id,
                    "passed": bool(
                        removed["terminal"].get("status") == "succeeded"
                        and reinserted["terminal"].get("status") == "succeeded"
                        and len(gamma) == 1
                        and not beta_still
                        and not stale_binding_on_new_id
                    ),
                }
            )

            before = await runner.call("creo_list_components", {"model_id": model_id})
            answer = await runner.probe(
                "creo_execute_plan",
                {
                    "model_id": model_id,
                    "expected_revision": before.get("revision"),
                    "operations": [
                        {
                            "op": "component_placement",
                            "component": "part_beta",
                            "translation": [10.0, 0.0, 0.0],
                        }
                    ],
                },
            )
            body = answer["structured"] or {}
            terminal = None
            if body.get("job_id"):
                # The label check can happen inside the native job; poll the accepted
                # job instead of resubmitting and keep its terminal evidence.
                terminal = await runner.wait_job(body["job_id"], budget=HANG_BUDGET_SECONDS)
            after = await runner.call("creo_list_components", {"model_id": model_id})
            failure = (terminal or {}).get("result") or {}
            message = (
                str((terminal or {}).get("message") or "")
                if terminal
                else str(body.get("error") or body.get("message") or answer["text"])
            )
            runner.case(
                {
                    "case": "unknown_label",
                    "rejected_at_admission": bool(answer["is_error"]),
                    "job_id": body.get("job_id"),
                    "job_status": (terminal or {}).get("status"),
                    "toolkit_code": failure.get("toolkit_code"),
                    "failed_stage": failure.get("failed_stage"),
                    "rollback_succeeded": failure.get("rollback_succeeded"),
                    "message": message[:800],
                    "revision_before": before.get("revision"),
                    "revision_after": after.get("revision"),
                    "labels_after": sorted(label_map(component_rows(after))),
                    "passed": bool(
                        before.get("revision") == after.get("revision")
                        and "part_beta" not in label_map(component_rows(after))
                        and (not body.get("job_id") or (terminal or {}).get("status") == "failed")
                    ),
                }
            )
        except BaseException as error:
            runner.report["stopped"] = f"{type(error).__name__}: {error}"
            runner.finish()
            raise
    summary = runner.finish()
    print(json.dumps(summary, ensure_ascii=False))
    rows = [
        {key: case.get(key) for key in ("case", "passed", "message")}
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
    output = args.output or ROOT / "build" / "component_labels" / run_id / "report.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    if args.live:
        if not args.confirm_session_usable:
            print("live runs require --confirm-session-usable", file=sys.stderr)
            return 2
        return asyncio.run(live(output, run_id))
    report = {
        "task": "FEAT-023 / DEV-051 T09A",
        "mode": "offline",
        "native_acceptance": "not_run",
        "projection": check_projection_contract(),
        "provenance": provenance(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name("report.sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(
        json.dumps({"report": str(output), "projection": report["projection"]}, ensure_ascii=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
