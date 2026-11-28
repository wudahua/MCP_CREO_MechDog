"""Compact response projections for status polling tools (FEAT-095)."""

from __future__ import annotations

from typing import Any

_COMMON_KEYS = (
    "server_version",
    "state",
    "phase",
    "connection_state",
    "connected",
    "readiness",
    "readiness_phase",
    "startup_in_progress",
    "message",
    "failure_code",
    "reason",
    "diagnosis",
    "terminal_reason",
    "retry_id",
    "retry_allowed",
    "retry_blocked_by",
    "coordinator_running",
    "stale",
    "verified_at",
    "checked_at",
    "mode",
    "channel_policy",
    "job_id",
    "blocking_job_id",
    "blocking_model_id",
    "blocking_operation",
    "retry_after_seconds",
    "next_steps",
    "next_action",
    "instruction",
    "connection_guidance",
    "affected_operations",
    "unaffected_alternatives",
    "recovery_steps",
    "callback_advisory",
    "registry_file",
    "persistent_registration_config",
    "artifact_status",
)


def _compact_panel_guard(guard: object) -> dict[str, Any] | None:
    if not isinstance(guard, dict):
        return None
    return {
        key: guard[key]
        for key in ("model_id", "job_id", "profile_id", "state", "status", "reason", "created_at")
        if key in guard
    } or None


def _compact_session_health(health: object) -> dict[str, Any] | None:
    if not isinstance(health, dict):
        return None
    conn = health.get("connection_health")
    save = health.get("save_health")
    compact: dict[str, Any] = {}
    for key in ("status", "reason", "summary"):
        if key in health:
            compact[key] = health[key]
    if isinstance(conn, dict):
        compact["connection_health"] = {
            k: conn[k]
            for k in ("status", "toolkit_code", "observed_at", "age_seconds")
            if k in conn
        }
    if isinstance(save, dict):
        compact["save_health"] = {
            k: save[k]
            for k in ("status", "observed_at", "failed_count", "recent_failure_count")
            if k in save
        }
    return compact or None


def _compact_process_snapshot(snapshot: object) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    processes = snapshot.get("processes")
    compact: dict[str, Any] = {}
    for key in ("available", "reason", "uncertain", "count"):
        if key in snapshot:
            compact[key] = snapshot[key]
    if isinstance(processes, list):
        compact["process_count"] = len(processes)
    return compact or None


def compact_status_response(payload: dict[str, Any], *, tool_name: str) -> dict[str, Any]:
    """Return a bounded compact view of startup/session/callback status payloads.

    Preserves actionable identity, blockers, failure codes/reasons, panel lock
    context, and next steps while omitting multi-kilobyte histories, generation
    inventories, and duplicated nested snapshots.
    """
    if not isinstance(payload, dict):
        return {"detail": "compact", "tool": tool_name}
    out: dict[str, Any] = {"detail": "compact"}
    for key in _COMMON_KEYS:
        if key in payload and payload[key] is not None:
            out[key] = payload[key]
    guard = _compact_panel_guard(payload.get("panel_session_guard"))
    if guard is not None:
        out["panel_session_guard"] = guard
    elif isinstance(payload.get("startup"), dict):
        nested_guard = _compact_panel_guard(payload["startup"].get("panel_session_guard"))
        if nested_guard is not None:
            out["panel_session_guard"] = nested_guard
    if "next_steps" not in out and isinstance(payload.get("startup"), dict):
        nested_steps = payload["startup"].get("next_steps")
        if nested_steps:
            out["next_steps"] = nested_steps
    health = _compact_session_health(payload.get("session_health"))
    if health is not None:
        out["session_health"] = health
    proc = _compact_process_snapshot(payload.get("creo_process_snapshot"))
    if proc is not None:
        out["creo_process_snapshot"] = proc
    busy = payload.get("busy")
    if isinstance(busy, dict):
        out["busy"] = {
            k: busy[k]
            for k in (
                "job_id",
                "model_id",
                "operation",
                "blocking_job_id",
                "blocking_model_id",
                "blocking_operation",
                "retry_after_seconds",
            )
            if k in busy
        }
    native = payload.get("native")
    if isinstance(native, dict):
        out["native"] = {
            k: native[k]
            for k in ("connected", "connection_state", "toolkit_code", "release_numeric")
            if k in native
        }
    update = payload.get("update")
    if isinstance(update, dict):
        out["update"] = {
            k: update[k] for k in ("status", "current_version", "latest_version") if k in update
        }
    inv = payload.get("generation_inventory")
    if isinstance(inv, dict):
        out["generation_inventory_summary"] = {
            k: inv[k]
            for k in ("generation_count", "payload_generation_count", "current_generation_key")
            if k in inv
        }
    out["full_detail_hint"] = (
        f"Pass detail='full' to {tool_name} for full diagnostics and inventories."
    )
    return out
