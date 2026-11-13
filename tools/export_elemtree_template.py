"""BUG-123/B1: export a real boundary-blend element tree as a template.

The Creo 10 feedback (BUG-120) cannot read the boundary blend's element tree at
all (`elemtree_extract=-18`), so the only low-release route is to read a tree that
Creo 12.4 already builds back into the feature (`ProElemtreeFromXMLCreate`). That
needs a real tree first: this driver builds one through the public MCP tools,
dumps it with `creo_dump_feature_tree`, and stores the XML plus a manifest entry.

Offline (default) only validates the shape plan against the published schema and
prints it; nothing connects to Creo.

Usage (PowerShell, repo root):
  .venv\\Scripts\\python.exe tools\\export_elemtree_template.py
  .venv\\Scripts\\python.exe tools\\export_elemtree_template.py --live --confirm-session-usable
  .venv\\Scripts\\python.exe tools\\export_elemtree_template.py --live `
      --confirm-session-usable --shape s3g2
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bridge  # noqa: E402 - the driver reads the accepted job's own manifest

TEMPLATES = ROOT / "templates" / "elemtree"
SECTION_LENGTH_MM = 40.0
SECTION_GAP_MM = 20.0


def sketch(label: str, plane: str, offset: float, name: str, start, end) -> dict[str, Any]:
    return {
        "op": "sketch",
        "label": label,
        "plane": plane,
        "offset": offset,
        "entities": [{"type": "line", "name": name, "start": start, "end": end}],
    }


def shape_plan(shape: str) -> list[dict[str, Any]]:
    """The measured 12.4 recipes, extended to the third guide when asked.

    ``s3g2`` is the live-verified 3-section/2-guide rectangle (1600.0 mm2 on
    2026-11-11); ``s3g3`` adds the middle guide that the bulb feedback needs
    (3 sections + 3 guides); ``plain3`` is the 3-section blend with no second
    direction.
    """
    plan = [
        sketch("sec_a", "XY", 0.0, "a", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch("sec_b", "XY", SECTION_GAP_MM, "b", [0.0, 0.0], [SECTION_LENGTH_MM, 0.0]),
        sketch(
            "sec_c",
            "XY",
            2 * SECTION_GAP_MM,
            "c",
            [0.0, 0.0],
            [SECTION_LENGTH_MM, 0.0],
        ),
    ]
    loft: dict[str, Any] = {
        "op": "surface_loft",
        "label": "template_loft",
        "sections": ["sec_a", "sec_b", "sec_c"],
        "interpolation": "smooth",
    }
    if shape in ("s3g2", "s3g3"):
        plan.append(sketch("guide_left", "XZ", 0.0, "g", [0.0, 0.0], [0.0, 2 * SECTION_GAP_MM]))
        plan.append(
            sketch(
                "guide_right",
                "XZ",
                0.0,
                "g",
                [SECTION_LENGTH_MM, 0.0],
                [SECTION_LENGTH_MM, 2 * SECTION_GAP_MM],
            )
        )
        loft["guides"] = ["guide_left", "guide_right"]
    if shape == "s3g3":
        plan.append(
            sketch(
                "guide_mid",
                "XZ",
                0.0,
                "g",
                [SECTION_LENGTH_MM / 2, 0.0],
                [SECTION_LENGTH_MM / 2, 2 * SECTION_GAP_MM],
            )
        )
        loft["guides"] = ["guide_left", "guide_mid", "guide_right"]
    plan.append(loft)
    return plan


def case_offline(shape: str) -> dict:
    from creo_mechdog.schema import validate_operations

    plan = shape_plan(shape)
    validated = validate_operations(plan)
    loft = validated[-1]
    return {
        "mode": "offline",
        "shape": shape,
        "sections": len(loft["sections"]),
        "guides": len(loft.get("guides") or []),
        "operations": len(validated),
        "plan": validated,
        "note": "schema-admissible; nothing was submitted and no Creo session was touched",
    }


async def wait_ready(client, budget_seconds: int = 600) -> dict:
    """Poll the session probe until the operator's own Creo reports connected.

    The probe is `creo_session_status` (9 s budget, no rebuild) rather than the
    startup coordinator: automatic startup is disabled here and the operator
    launches Creo by hand, so only the connection itself is evidence.
    """
    deadline = time.monotonic() + budget_seconds
    state: dict = {}
    while time.monotonic() < deadline:
        state = (await client.call_tool("creo_session_status", {})).structured_content or {}
        if state.get("connected"):
            return state
        await asyncio.sleep(3)
    return state


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


async def submit(
    client, operations: list[dict], model_id: str | None = None, revision=None
) -> dict:
    arguments: dict[str, Any] = {"operations": operations}
    if model_id:
        arguments["model_id"] = model_id
        arguments["expected_revision"] = revision
    submitted = await call_tool(client, "creo_execute_plan", arguments)
    job_id = submitted.get("job_id")
    if not job_id:
        return {"status": "refused", "message": str(submitted)[:800]}
    deadline = time.monotonic() + 900
    state: dict = {}
    while time.monotonic() < deadline:
        state = await call_tool(client, "creo_get_job", {"job_id": job_id, "detail": "compact"})
        if state.get("status") in ("succeeded", "failed", "unknown_outcome"):
            break
        await asyncio.sleep(2)
    else:
        return {"status": "unsettled", "job_id": job_id}
    view = await call_tool(
        client,
        "creo_get_job",
        {"job_id": job_id, "detail": "compact", "sections": ["operations"]},
    )
    if view.get("operations"):
        state = {**state, **view}
    state["job_id"] = job_id
    return state


def operation_of(state: dict, op: str) -> dict:
    """The operation record with the fields the compact MCP view drops.

    The projection is trimmed on purpose (geometry ids, template details), so the
    accepted job's own manifest is merged over it: the manifest is the full
    native record, the projection is a view of the same job.
    """
    operations = (state.get("result") or {}).get("operations") or state.get("operations") or []
    compact = next((item for item in operations if item.get("op") == op), {})
    job_id = state.get("job_id")
    if not job_id:
        return compact
    try:
        manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    except (OSError, ValueError):
        return compact
    full = [
        item
        for item in (
            (manifest.get("result") or {}).get("operations") or manifest.get("operations") or []
        )
        if isinstance(item, dict) and item.get("op") == op
    ]
    if not full:
        return compact
    return {**compact, **full[0]}


def worker_identity() -> dict:
    """The verified worker identity recorded by the last probe (source provenance)."""
    try:
        health = json.loads((ROOT / "build" / "toolkit_health.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    identity = health.get("worker_build_identity")
    return identity if isinstance(identity, dict) else {}


def write_manifest(entry: dict) -> Path:
    TEMPLATES.mkdir(parents=True, exist_ok=True)
    path = TEMPLATES / "manifest.json"
    document: dict[str, Any] = {"schema": 1, "templates": []}
    if path.is_file():
        document = json.loads(path.read_text(encoding="utf-8"))
    templates = [
        item for item in document.get("templates", []) if item.get("file") != entry["file"]
    ]
    templates.append(entry)
    document["templates"] = sorted(templates, key=lambda item: item["file"])
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def loft_from_job(job_id: str) -> dict:
    """Model/feature/revision and the measured loft record of an accepted job."""
    try:
        manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    except (OSError, ValueError):
        return {}
    operations = (manifest.get("result") or {}).get("operations") or []
    loft = next(
        (op for op in operations if isinstance(op, dict) and op.get("op") == "surface_loft"),
        {},
    )
    return {
        "model_id": manifest.get("model_id"),
        "revision": manifest.get("revision"),
        "loft": loft,
    }


async def case_live(shape: str, from_job: str | None = None) -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from version import VERSION

    report = {
        "mode": "live",
        "shape": shape,
        "version": VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "jobs": [],
        "template": None,
        "reused_model": bool(from_job),
    }
    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        report["session"] = {
            "connected": bool(started.get("connected")),
            "state": started.get("state"),
            "message": str(started.get("message"))[:300],
        }
        if not started.get("connected"):
            report["note"] = "the session never reported connected; nothing was submitted"
            return report

        if from_job:
            # A verified loft from an earlier job is dumped as it is: the tree is
            # identical and no second model is created for the same artifact.
            reused = loft_from_job(from_job)
            model_id = reused.get("model_id")
            revision = reused.get("revision")
            loft = reused.get("loft") or {}
            feature_id = loft.get("feature_id")
            report["loft"] = {
                key: loft.get(key)
                for key in (
                    "feature_id",
                    "create_code",
                    "extract_code",
                    "feature_incomplete",
                    "kernel_completion",
                    "section_count",
                    "guide_count",
                    "surface_area_mm2",
                    "tree_elements_read",
                )
                if key in loft
            }
            report["jobs"].append(
                {"status": "reused", "job_id": from_job, "model_id": model_id, "revision": revision}
            )
            if not model_id or not isinstance(feature_id, int):
                report["note"] = f"job {from_job} carries no surface_loft feature to dump"
                return report
        else:
            build = await submit(client, shape_plan(shape))
            report["jobs"].append(
                {k: build.get(k) for k in ("job_id", "status", "model_id", "revision", "message")}
            )
            loft = operation_of(build, "surface_loft")
            report["loft"] = {
                key: loft.get(key)
                for key in (
                    "feature_id",
                    "create_code",
                    "extract_code",
                    "feature_incomplete",
                    "kernel_completion",
                    "section_count",
                    "guide_count",
                    "surface_area_mm2",
                    "tree_elements_read",
                )
                if key in loft
            }
            feature_id = loft.get("feature_id")
            model_id = build.get("model_id")
            revision = build.get("revision")
            if build.get("status") != "succeeded" or not isinstance(feature_id, int):
                report["note"] = "the template loft did not succeed; no tree was dumped"
                return report

        dump = await submit(
            client, [{"op": "dump_tree", "feature": feature_id}], model_id, revision
        )
        report["jobs"].append(
            {k: dump.get(k) for k in ("job_id", "status", "model_id", "revision", "message")}
        )
        dumped = operation_of(dump, "dump_tree")
        source = dumped.get("file")
        report["dump"] = {k: dumped.get(k) for k in ("file", "effect_status") if k in dumped}
        if dump.get("status") != "succeeded" or not source or not Path(source).is_file():
            report["note"] = "the tree dump did not produce an XML file"
            return report

        data = Path(source).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        plan_loft = shape_plan(shape)[-1]
        name = f"loft_s{len(plan_loft['sections'])}g{len(plan_loft.get('guides') or [])}"
        file_name = f"{name}_creo12.4.xml"
        TEMPLATES.mkdir(parents=True, exist_ok=True)
        destination = TEMPLATES / file_name
        destination.write_bytes(data)
        entry = {
            "file": file_name,
            "template_id": name,
            "sha256": digest,
            "bytes": len(data),
            "sections": len(plan_loft["sections"]),
            "guides": len(plan_loft.get("guides") or []),
            "source": {
                "tool": "creo_dump_feature_tree",
                "creo_release_numeric": started.get("release_numeric")
                or worker_identity().get("release_numeric"),
                "worker_sha256": worker_identity().get("worker_sha256"),
                "worker_source_digest": worker_identity().get("source_digest"),
                "mcp_version": VERSION,
                "model_id": model_id,
                "feature_id": feature_id,
                "job_ids": [item.get("job_id") for item in report["jobs"]],
                "exported_at": report["started_at"],
                "command": "tools/export_elemtree_template.py --live --confirm-session-usable "
                f"--shape {shape}" + (f" --from-job {from_job}" if from_job else ""),
            },
            "measured": report.get("loft", {}),
        }
        manifest = write_manifest(entry)
        report["template"] = entry
        report["manifest"] = str(manifest)
        report["passed"] = True
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="run against the local Creo session")
    parser.add_argument(
        "--confirm-session-usable",
        action="store_true",
        help="operator confirmation for THIS live run (required with --live)",
    )
    parser.add_argument(
        "--shape",
        choices=("s3g3", "s3g2", "plain3"),
        default="s3g3",
        help="template shape to build (default: 3 sections + 3 guides)",
    )
    parser.add_argument(
        "--from-job",
        help="dump the surface_loft of this accepted job instead of building a new model",
    )
    arguments = parser.parse_args(argv)
    if arguments.live and not arguments.confirm_session_usable:
        raise SystemExit("--live requires --confirm-session-usable")
    if not arguments.live:
        print(json.dumps(case_offline(arguments.shape), ensure_ascii=False, indent=2))
        return 0
    result = asyncio.run(case_live(arguments.shape, arguments.from_job))
    directory = ROOT / "build" / f"elemtree_export_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"report: {directory / 'report.json'}")
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
