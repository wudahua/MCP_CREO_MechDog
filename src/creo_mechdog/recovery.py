"""Read-only evidence for uncertain jobs; evidence never authorizes replay or unlocking."""

from __future__ import annotations

import ctypes
import hashlib
import json
from ctypes import wintypes
from pathlib import Path


def process_identity(pid: int) -> dict:
    """Use process creation time to distinguish a live runner from a reused PID."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    times = kernel.GetProcessTimes
    times.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    exit_code = kernel.GetExitCodeProcess
    exit_code.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    handle = open_process(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        return {"pid": pid, "alive": False if error == 87 else None, "windows_error": error}
    try:
        created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
        code = wintypes.DWORD()
        if not times(handle, created, exited, system, user) or not exit_code(handle, code):
            return {"pid": pid, "alive": None, "windows_error": ctypes.get_last_error()}
        return {
            "pid": pid,
            "created": (created.dwHighDateTime << 32) | created.dwLowDateTime,
            "alive": code.value == 259,
        }
    finally:
        close(handle)


def file_identity(path: Path) -> dict:
    try:
        size = path.stat().st_size
        if size > 16 * 1024 * 1024:
            return {
                "path": str(path),
                "exists": True,
                "size_bytes": size,
                "sha256": None,
                "hash_not_computed": "File exceeds the 16 MiB diagnostic read budget",
            }
        data = path.read_bytes()
        return {"path": str(path), "exists": True, "sha256": hashlib.sha256(data).hexdigest()}
    except OSError as exc:
        return {
            "path": str(path),
            "exists": None if path.exists() else False,
            "error": type(exc).__name__,
        }


def completion_review(
    native_result: dict | None,
    checkpoint: dict | None,
    runner_alive: bool | None,
    model_available: bool | None,
) -> dict:
    """Summarize what the leftover evidence supports about an uncertain job.

    FEAT-018 / 2026-11-10 0.19.3 feedback (A-P3): after a watchdog timeout the
    caller had to read the native result, the checkpoint and the saved file
    separately before guessing whether anything was actually built. This block
    answers one question only — *what does the evidence support* — and never
    authorizes a replay, a revision bump or a status change.
    """
    success = None
    verified = None
    delivery = None
    revision = None
    if isinstance(native_result, dict):
        if isinstance(native_result.get("success"), bool):
            success = native_result["success"]
        if isinstance(native_result.get("saved_file_reloaded_and_verified"), bool):
            verified = native_result["saved_file_reloaded_and_verified"]
        if isinstance(native_result.get("revision"), int):
            revision = native_result["revision"]
    if isinstance(checkpoint, dict):
        if isinstance(checkpoint.get("delivery_complete"), bool):
            delivery = checkpoint["delivery_complete"]
        if verified is None and isinstance(
            checkpoint.get("saved_file_reloaded_and_verified"), bool
        ):
            verified = checkpoint["saved_file_reloaded_and_verified"]
        if success is None and isinstance(checkpoint.get("success"), bool):
            success = checkpoint["success"]
    signals = {
        "native_result_success": success,
        "saved_file_reloaded_and_verified": verified,
        "checkpoint_delivery_complete": delivery,
        "runner_alive": runner_alive,
        "model_currently_available": model_available,
        "reported_revision": revision,
    }
    if runner_alive is True:
        verdict, action, why = (
            "still_running",
            "wait_for_runner",
            "A recorded runner process for this job is still alive; a second submission "
            "cannot own the channel and would only be refused",
        )
    elif success is False:
        verdict, action, why = (
            "not_completed",
            "operator_reconciliation",
            "The native result reports failure; follow the failure receipts instead of "
            "accepting the current model state",
        )
    elif success is True and verified is True and runner_alive is False:
        verdict, action, why = (
            "likely_completed",
            "inspect_saved_file_then_reconcile_accept_live",
            "The native result reports success and a verified save/reload, and no runner is "
            "alive; a fresh read-only inspect of the saved file can confirm the geometry "
            "before an explicit accept_live",
        )
    elif success is True:
        verdict, action, why = (
            "partially_confirmed",
            "inspect_saved_file_then_operator_reconciliation",
            "The native result reports success but not a verified save/reload; the saved file "
            "must be inspected before any reconciliation action",
        )
    else:
        verdict, action, why = (
            "insufficient_evidence",
            "operator_reconciliation",
            "No native result records this job's outcome; keep the pending reservation and "
            "reconcile from the model and checkpoint on disk",
        )
    return {
        "read_only": True,
        "authorizes_replay": False,
        "authorizes_revision_change": False,
        "verdict": verdict,
        "suggested_next_action": action,
        "signals": signals,
        "why": why,
        "note": (
            "This summary never accepts a model state or clears the reservation; "
            "creo_reconcile_model still requires a fresh evidence token and an explicit action"
        ),
    }


def _bounded_native_result(directory: Path) -> dict | None:
    """Read the leftover native result without exceeding the diagnostic budget."""
    path = directory / "native_result.json"
    try:
        if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def job_evidence(directory: Path, manifest: dict, model: dict | None = None) -> dict:
    """Do not mutate jobs/models, infer cancellation, or promote a checkpoint to success."""
    result = {
        "job_id": manifest["job_id"],
        "model_id": manifest.get("model_id"),
        "automatic_replay_allowed": False,
        "native_result_present": (directory / "native_result.json").is_file(),
        "next_steps": (
            "Do not resubmit or clear pending_job. Inspect this job's native result/checkpoint, "
            "runner identity and saved file in Creo; preserve the original model/checkpoint. "
            "Use creo_session_status and explicit startup retry to recheck the channel. "
            "A connected channel does not resolve this job or commit its revision. "
            "If the result cannot be verified, operator reconciliation is required. "
            "completion_review summarizes what the leftover evidence supports; it never "
            "authorizes a replay, a revision change or clearing the reservation."
        ),
    }
    runner = manifest.get("runner_identity")
    if runner:
        current = process_identity(runner["pid"])
        result["runner"] = {
            "recorded": runner,
            "observed": current,
            "same_process": current.get("created") == runner.get("created")
            if current.get("created") and runner.get("created")
            else None,
        }
    else:
        result["runner"] = {"observed": None, "reason": "No recorded process creation identity"}
    checkpoint = directory / "native_checkpoint.json"
    checkpoint_data = None
    if checkpoint.is_file():
        try:
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            checkpoint_data = data if isinstance(data, dict) else None
            result["native_checkpoint"] = {
                **file_identity(checkpoint),
                **{
                    key: data[key]
                    for key in (
                        "native_pid",
                        "completion_stage",
                        "delivery_complete",
                        "success",
                        "toolkit_code",
                        "message",
                        "part_file",
                        "saved_file_reloaded_and_verified",
                        "disconnect_code",
                        "disconnect_budget_seconds",
                        "rollback_succeeded",
                    )
                    if key in data
                },
                "authoritative_job_success": False,
            }
        except (OSError, ValueError, TypeError):
            result["native_checkpoint"] = {"readable": False}
    if model:
        resolution = model.get("reconciliation")
        result["resolution"] = resolution
        result["model_currently_available"] = model.get("status") == "ready" and not (
            model.get("pending_job") or model.get("recovery_pending")
        )
        result["model"] = {
            key: model.get(key) for key in ("status", "revision", "pending_job", "last_job")
        }
        if model.get("part_file"):
            result["saved_baseline"] = file_identity(Path(model["part_file"]))
    observed = result.get("runner", {}).get("observed")
    result["completion_review"] = completion_review(
        _bounded_native_result(directory),
        checkpoint_data,
        observed.get("alive") if isinstance(observed, dict) else None,
        result.get("model_currently_available"),
    )
    return result
