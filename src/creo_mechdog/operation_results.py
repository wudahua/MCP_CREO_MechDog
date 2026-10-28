"""Terminal operation result projection shared by native and job views (T02).

The native executor publishes one terminal record per requested operation with
a zero-based ``index``, an ``execution_status`` and an ``effect_status``. This
module keeps the persisted job result on the same contract: it only fills the
two status fields for records that predate the native change (legacy jobs and
synthetic fixtures) and never invents records or upgrades unknown outcomes.

Existing ``succeeded`` stays a report of the execution fact. It never implies
that the transaction committed; ``effect_status`` carries that meaning.
"""

from __future__ import annotations

from typing import Any

EXECUTION_STATUSES = ("succeeded", "failed", "not_executed", "unknown")
EFFECT_STATUSES = ("committed", "rolled_back", "no_effect", "unknown")


def _execution_status(op: dict[str, Any], job_status: str, failed_index: int | None) -> str:
    if op.get("execution_status") in EXECUTION_STATUSES:
        return str(op["execution_status"])
    # Legacy record: derive only what the retained evidence states. A failed
    # operation index marks exactly that input; everything else stays unknown
    # unless the whole job succeeded.
    index = op.get("index")
    if op.get("succeeded") is True:
        return "succeeded"
    if isinstance(index, int) and failed_index is not None and index == failed_index:
        return "failed"
    if job_status == "succeeded":
        return "succeeded"
    return "unknown"


def _effect_status(
    op: dict[str, Any],
    execution: str,
    job_status: str,
    rollback_confirmed: bool,
    readonly: bool,
) -> str:
    if op.get("effect_status") in EFFECT_STATUSES:
        return str(op["effect_status"])
    if execution == "not_executed":
        return "no_effect"
    if job_status == "succeeded" and execution == "succeeded":
        # A successful writable plan saved, reloaded and advanced one revision;
        # a read-only plan confirms that the model itself was not written.
        return "no_effect" if readonly else "committed"
    if rollback_confirmed and execution in ("succeeded", "failed"):
        return "rolled_back"
    return "unknown"


def normalize_operations(
    operations: Any,
    *,
    job_status: str,
    rollback_confirmed: bool = False,
    readonly: bool = False,
    failed_index: int | None = None,
) -> list[dict[str, Any]]:
    """Fill index and the two status fields without fabricating outcomes.

    ``operations`` must already be the native record list. The function never
    adds or drops records, so a job that never produced operation results keeps
    an empty list rather than a synthetic success trail.
    """
    if not isinstance(operations, list):
        return []
    normalized: list[dict[str, Any]] = []
    for position, raw in enumerate(operations):
        op = dict(raw) if isinstance(raw, dict) else {}
        if not isinstance(op.get("index"), int):
            op["index"] = position
        execution = _execution_status(op, job_status, failed_index)
        op["execution_status"] = execution
        op["effect_status"] = _effect_status(
            op, execution, job_status, rollback_confirmed, readonly
        )
        normalized.append(op)
    return normalized


def annotate_native_result(
    result: dict[str, Any], *, readonly: bool, inputs: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Normalize an accepted native result before it is persisted on the job."""
    operations = result.get("operations")
    if not isinstance(operations, list):
        # No operation record exists (for example the worker never delivered a
        # result). Do not synthesize executed outcomes; leave the field absent.
        return result
    failed_index = result.get("failed_operation_index")
    result["operations"] = normalize_operations(
        operations,
        job_status="succeeded" if result.get("success") else "failed",
        rollback_confirmed=result.get("rollback_succeeded") is True,
        readonly=readonly,
        failed_index=failed_index if isinstance(failed_index, int) else None,
    )
    if inputs is not None:
        annotate_profiles(result, inputs)
        annotate_arc_geometry(result, inputs)
        annotate_feature_state(result, inputs)
    return result


def annotate_feature_state(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Project each feature_state input's target detail onto its own record.

    T02 keeps one terminal record per input; the per-target before/after list
    is a specialized field of that single record. The native executor owns the
    detail, so a missing list stays missing and is never fabricated here.
    """
    from creo_mechdog import feature_state

    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") != "feature_state":
            continue
        source = inputs[position] if position < len(inputs) else None
        if not (isinstance(source, dict) and source.get("op") == "feature_state"):
            continue
        targets = source.get("targets")
        if isinstance(targets, list):
            feature_state.project_operation(operation, targets)
    return result


def _profile_summary(entities: list[dict[str, Any]]) -> dict[str, Any]:
    from creo_mechdog.profile_diagnostics import analyze_profile

    report = analyze_profile(entities)
    return {
        "source": "input",
        "analysis": report["analysis"],
        "arc_geometry": report.get("arc_geometry", []),
        "entity_count": report["entity_count"],
        "contour_count": report["contour_count"],
        "closed_contour_count": report["closed_contour_count"],
        "open_contour_count": report["open_contour_count"],
        "material_area_mm2": report["material_area_mm2"],
        "categories": {name: entry["count"] for name, entry in report["categories"].items()},
    }


def _source_for(
    operation: dict[str, Any], inputs: list[dict[str, Any]], position: int
) -> dict[str, Any] | None:
    """Locate the input record behind one operation result, if it is unambiguous."""

    def same_label(item: dict[str, Any]) -> bool:
        # Geometry updates carry no label on either side while the native
        # record reports the empty string (FEAT-034/T02).
        return str(item.get("label") or "") == str(operation.get("label") or "")

    source = inputs[position] if position < len(inputs) else None
    if not (
        isinstance(source, dict) and source.get("op") == operation.get("op") and same_label(source)
    ):
        matches = [
            item
            for item in inputs
            if isinstance(item, dict) and item.get("op") == operation.get("op") and same_label(item)
        ]
        source = matches[0] if len(matches) == 1 else None
    return source if isinstance(source, dict) else None


def annotate_profiles(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach the analytic input contour report to every sketch result (T06).

    The native section summary is a separate field supplied by the executor;
    this report describes the supplied coordinates and never replaces it.
    """
    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") != "sketch":
            continue
        source = _source_for(operation, inputs, position)
        entities = source.get("entities") if isinstance(source, dict) else None
        if not isinstance(entities, list) or not entities:
            continue
        try:
            operation["profile"] = _profile_summary(entities)
        except (KeyError, TypeError, ValueError):
            # Diagnostics must never turn a delivered native result into a
            # failure; record that the input report is unavailable instead.
            operation["profile"] = {"source": "input", "analysis": "unavailable"}
    return result


_ARC_ACTUAL_FIELDS = (
    "query_code",
    "frame",
    "start_uv",
    "end_uv",
    "start_tangent_uv",
    "end_tangent_uv",
    "dir",
    "sweep_deg",
)
_ARC_MEASURED_FIELDS = (
    "start_uv",
    "end_uv",
    "start_tangent_uv",
    "end_tangent_uv",
    "dir",
    "sweep_deg",
)


def _unknown_arc_actual(query_code: Any = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"source": "unknown", "query_code": query_code, "frame": None}
    entry.update({key: None for key in _ARC_ACTUAL_FIELDS if key not in entry})
    return entry


def project_arc_echo(entities: list[dict[str, Any]], measured: Any) -> list[dict[str, Any]]:
    """Project the executor's measured arc geometry onto the input arcs (FEAT-034).

    Reported values are only ever the executor's own query result (``source=
    "native"``) or explicitly unknown with the raw query code. Requested input
    values are never echoed here as measured geometry.
    """
    by_name: dict[str, dict[str, Any]] = {}
    if isinstance(measured, list):
        for item in measured:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                by_name[item["name"]] = item
    projection: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict) or entity.get("type") != "arc":
            continue
        name = str(entity.get("name"))
        record = by_name.get(name)
        if isinstance(record, dict) and record.get("source") in ("native", "unknown"):
            entry = {"name": name, "source": record["source"]}
            entry.update({key: record.get(key) for key in _ARC_ACTUAL_FIELDS})
            if entry["source"] == "native" and any(
                entry[key] is None for key in _ARC_MEASURED_FIELDS
            ):
                entry = {"name": name, **_unknown_arc_actual(record.get("query_code"))}
            projection.append(entry)
        else:
            projection.append({"name": name, **_unknown_arc_actual()})
    return projection


def annotate_arc_geometry(result: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach the measured arc echo to sketch creation and update records."""
    operations = result.get("operations")
    if not isinstance(operations, list) or not isinstance(inputs, list):
        return result
    for position, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("op") not in (
            "sketch",
            "update_sketch_geometry",
        ):
            continue
        source = _source_for(operation, inputs, position)
        entities = source.get("entities") if isinstance(source, dict) else None
        if not isinstance(entities, list) or not entities:
            continue
        operation["arc_geometry"] = project_arc_echo(entities, operation.get("arc_geometry"))
    return result
