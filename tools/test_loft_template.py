"""BUG-123/B3: the template route must build the same surface as the built tree.

The loader reads `templates/elemtree/loft_s3g3_creo12.4.xml`, replaces only its
six curve references and creates the feature. This driver builds the same 3+3
shape twice - once from the hand-built tree, once from the template - and compares
the measured surface, so a template that drifted or a loader that mis-orders the
holders cannot pass unnoticed.

Offline (default) checks the schema contract only. Live needs the operator's
confirmation for THIS run:

  .venv\\Scripts\\python.exe tools\\test_loft_template.py
  .venv\\Scripts\\python.exe tools\\test_loft_template.py --live --confirm-session-usable
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "templates" / "elemtree" / "loft_s3g3_creo12.4.xml"
RELATIVE_TOLERANCE = 1e-6


def shape_plan(template: dict | None = None, *, sketches: bool = True) -> list[dict[str, Any]]:
    """Three 40 mm sections 20 mm apart plus three straight guides that span them.

    The same recipe the template was exported from: every curve lies in the y = 0
    plane, so both routes must produce the 40 x 40 mm rectangle (1600.0 mm2).
    """

    def sketch(label, plane, offset, start, end):
        return {
            "op": "sketch",
            "label": label,
            "plane": plane,
            "offset": offset,
            "entities": [{"type": "line", "name": "g", "start": start, "end": end}],
        }

    # The second job in the same model must not resend the sketches: labels are
    # unique per model and re-sending them is refused before any job exists.
    plan = (
        [
            sketch("sec_a", "XY", 0.0, [0.0, 0.0], [40.0, 0.0]),
            sketch("sec_b", "XY", 20.0, [0.0, 0.0], [40.0, 0.0]),
            sketch("sec_c", "XY", 40.0, [0.0, 0.0], [40.0, 0.0]),
            sketch("guide_left", "XZ", 0.0, [0.0, 0.0], [0.0, 40.0]),
            sketch("guide_mid", "XZ", 0.0, [20.0, 0.0], [20.0, 40.0]),
            sketch("guide_right", "XZ", 0.0, [40.0, 0.0], [40.0, 40.0]),
        ]
        if sketches
        else []
    )
    loft: dict[str, Any] = {
        "op": "surface_loft",
        "label": "loft_template_path" if template else "loft_built_path",
        "sections": ["sec_a", "sec_b", "sec_c"],
        "guides": ["guide_left", "guide_mid", "guide_right"],
        "interpolation": "smooth",
    }
    if template:
        loft["template"] = template
    plan.append(loft)
    return plan


def case_offline() -> dict:
    import hashlib

    from creo_mechdog.schema import validate_operations

    checks: list[dict] = []
    digest = hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()

    def check(name: str, ok: bool, detail: dict | None = None):
        checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})})

    template = {"file": str(TEMPLATE), "sha256": digest}
    validated = validate_operations(shape_plan(template))
    check("schema_accepts_template", validated[-1]["template"]["sha256"] == digest)

    for name, broken, expected in (
        ("refuses_wrong_digest", {**template, "sha256": "0" * 64}, "does not match"),
        (
            "refuses_missing_file",
            {"file": str(TEMPLATE.parent / "no_such_template.xml")},
            "does not exist",
        ),
        ("refuses_non_xml", {"file": str(TEMPLATE.with_suffix(".prt"))}, "must be the XML"),
    ):
        try:
            validate_operations(shape_plan(broken))
        except ValueError as error:
            check(name, expected in str(error), {"message": str(error)[:160]})
        else:
            check(name, False, {"message": "accepted"})

    with_boundary = shape_plan(template)
    with_boundary[-1]["boundary_conditions"] = [
        {"boundary": "first_section", "condition": "tangent"}
    ]
    try:
        validate_operations(with_boundary)
    except ValueError as error:
        check(
            "refuses_boundary_conditions", "TAN_COND" in str(error), {"message": str(error)[:160]}
        )
    else:
        check("refuses_boundary_conditions", False, {"message": "accepted"})

    return {"mode": "offline", "passed": all(item["ok"] for item in checks), "checks": checks}


async def case_live() -> dict:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    from tools.export_elemtree_template import operation_of, submit, wait_ready

    report: dict[str, Any] = {"mode": "live", "passed": False, "jobs": [], "checks": []}

    def check(name: str, ok: bool, detail: dict | None = None):
        report["checks"].append(
            {"check": name, "ok": bool(ok), **({"detail": detail} if detail else {})}
        )

    async with Client(
        StdioServerParameters(command=sys.executable, args=[str(ROOT / "server.py")], cwd=str(ROOT))
    ) as client:
        started = await wait_ready(client)
        if not started.get("connected"):
            report["note"] = "the session never reported connected; nothing was submitted"
            return report

        built = await submit(client, shape_plan())
        report["jobs"].append(
            {k: built.get(k) for k in ("job_id", "status", "model_id", "revision", "message")}
        )
        built_loft = operation_of(built, "surface_loft")
        report["built"] = {
            key: built_loft.get(key)
            for key in (
                "feature_id",
                "create_code",
                "surface_area_mm2",
                "quilt_count",
                "quilt_closed_native",
                "tree_source",
            )
            if key in built_loft
        }
        check(
            "built_path_succeeded",
            built.get("status") == "succeeded",
            {"status": built.get("status"), "message": str(built.get("message"))[:200]},
        )
        if built.get("status") != "succeeded":
            return report

        model_id = built.get("model_id")
        revision = built.get("revision")
        template = {
            "file": str(TEMPLATE),
            "sha256": hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
        }
        templated = await submit(client, shape_plan(template, sketches=False), model_id, revision)
        report["jobs"].append(
            {k: templated.get(k) for k in ("job_id", "status", "model_id", "revision", "message")}
        )
        template_loft = operation_of(templated, "surface_loft")
        report["template"] = {
            key: template_loft.get(key)
            for key in (
                "feature_id",
                "create_code",
                "extract_code",
                "feature_incomplete",
                "surface_area_mm2",
                "quilt_count",
                "quilt_closed_native",
                "tree_source",
                "template",
                "sections",
                "guides",
                "guide_count",
                "section_count",
            )
            if key in template_loft
        }
        check(
            "template_path_succeeded",
            templated.get("status") == "succeeded",
            {"status": templated.get("status"), "message": str(templated.get("message"))[:300]},
        )
        check(
            "template_route_is_reported",
            template_loft.get("tree_source") == "template_xml",
            {"tree_source": template_loft.get("tree_source")},
        )
        check(
            "template_reports_its_counts",
            (template_loft.get("template") or {}).get("sections") == 3
            and (template_loft.get("template") or {}).get("guides") == 3,
            {"template": template_loft.get("template")},
        )

        built_area = built_loft.get("surface_area_mm2")
        template_area = template_loft.get("surface_area_mm2")
        if isinstance(built_area, (int, float)) and isinstance(template_area, (int, float)):
            relative = abs(template_area - built_area) / abs(built_area) if built_area else None
            report["areas"] = {
                "built": built_area,
                "template": template_area,
                "relative_difference": relative,
            }
            check(
                "areas_match",
                relative is not None and relative <= RELATIVE_TOLERANCE,
                {"built": built_area, "template": template_area},
            )
        else:
            check("areas_match", False, {"built": built_area, "template": template_area})

        # Two negative cases: a template whose curve array is gone must be refused
        # on the shape contract, and a file that is not readable XML must fail with
        # the parse code. Neither may leave a half-read feature behind.
        current = templated.get("revision", revision)
        with tempfile.TemporaryDirectory() as directory:
            for kind in ("shape", "garbage"):
                path = Path(directory) / f"broken_{kind}.xml"
                if kind == "shape":
                    text = TEMPLATE.read_text(encoding="utf-8")
                    text = re.sub(
                        r"<PRO_E_BNBLN_1DIR\b.*?</PRO_E_BNBLN_1DIR>",
                        "",
                        text,
                        count=1,
                        flags=re.DOTALL,
                    )
                    path.write_text(text, encoding="utf-8")
                    expected = "TEMPLATE_SHAPE_MISMATCH"
                else:
                    path.write_text('<?xml version="1.0"?><PRO_E_FEATURE_TREE', encoding="utf-8")
                    expected = "TEMPLATE_TREE_LOAD_FAILED"
                plan = shape_plan({"file": str(path)}, sketches=False)
                plan[-1]["label"] = f"loft_broken_{kind}"
                bad = await submit(client, plan, model_id, current)
                current = bad.get("revision", current)
                report["jobs"].append({k: bad.get(k) for k in ("job_id", "status", "message")})
                bad_loft = operation_of(bad, "surface_loft")
                report[f"broken_{kind}"] = {
                    key: bad_loft.get(key)
                    for key in ("create_code", "template", "feature_id")
                    if key in bad_loft
                }
                text = json.dumps(bad, ensure_ascii=False)
                check(
                    f"{kind}_template_is_refused",
                    bad.get("status") == "failed",
                    {"status": bad.get("status"), "message": str(bad.get("message"))[:300]},
                )
                check(
                    f"{kind}_template_reports_{'shape' if kind == 'shape' else 'parse'}",
                    expected in text,
                    {"expected": expected, "message": str(bad.get("message"))[:300]},
                )
                check(
                    f"{kind}_template_created_no_feature",
                    bad_loft.get("feature_id") is None,
                    {"feature_id": bad_loft.get("feature_id")},
                )

    report["passed"] = all(item["ok"] for item in report["checks"])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm-session-usable", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.live and not arguments.confirm_session_usable:
        raise SystemExit("--live requires --confirm-session-usable")
    if not TEMPLATE.is_file():
        raise SystemExit(f"template is missing: {TEMPLATE}")
    result = case_offline() if not arguments.live else asyncio.run(case_live())
    if arguments.live:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        directory = ROOT / "build" / f"loft_template_{stamp}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"report: {directory / 'report.json'}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
