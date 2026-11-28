"""Persistent hold on the Creo session while a resident panel may still be open (D4.4).

A resident panel surface loft opens real Creo UI. The worker process that started it
can die, a stdio server can restart, or a job can be force-cancelled — none of those
prove the dialog closed. While that is unproven, another model must not run native
work in the same session: the dialog belongs to the session, not to one ``model_id``,
so the existing per-model pending job and the Toolkit claim are not enough (both are
cleared on termination).

This module owns one guard record per session:

- ``reserve`` registers the job that is about to open UI. It is idempotent for that
  job and refuses a second holder, because one panel owns the session.
- ``require_clear`` is the gate every Toolkit entry calls with its job id. The
  owning job passes; anything else is refused with the holder's identity. Local
  work that never talks to Creo (for example compiling the executor) is exempt.
- ``retire`` releases the guard only on positive evidence: the panel was observed
  closed, the old Creo session provably ended, or no UI was ever started. A dead
  pid, an expired token, a stale marker or ``ack_failure``/``abandon_new`` never
  releases it here; those keep the old model-level semantics and leave the session
  protection in place.

The record lives next to ``toolkit.lock`` and is read on every Toolkit entry, so a
guard written by a previous server process keeps protecting the session after a
restart. Nothing here connects to Creo, retries, or clears protection by itself.

Three retires exist and nothing else may release a guard:

- the native exit observation in the job result (the panel backend reporting a closed
  dialog with evidence);
- a runner that provably never started, so no dialog could have opened;
- ``creo_reconcile_model(action="confirm_panel_closed", confirm_panel_closed=true)``,
  which a human runs after checking Creo. It goes through the reconcile evidence
  token, so the token expires like every other recovery token and the confirmed
  record keeps the job, nonce, profile, digest and who confirmed it. It frees the
  session protection only; the model's own unknown outcome stays unknown and still
  needs its own reconcile action.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

GUARD_FILE = "panel_session_guard.json"

#: Toolkit entries that cannot disturb a dialog: building the executor reads no
#: part and calls no Toolkit function that a panel would care about.
EXEMPT_OPERATIONS = ("build_native",)

REQUIRED_FIELDS = ("job_id", "nonce", "profile_id", "mode", "created_at")

#: Evidence that legitimately ends the protection. Each key is a positive
#: observation, never an inference from a dead process or a missing file.
CLOSING_EVIDENCE = ("ui_closed_confirmed", "session_ended_confirmed", "no_ui_started_confirmed")

ROOT = Path(__file__).resolve().parents[2]


class PanelSessionLocked(RuntimeError):
    """A resident panel may still hold the Creo session; native work is refused."""

    def __init__(self, message: str, holder: dict | None = None):
        super().__init__(message)
        self.holder = holder or {}


def guard_path(root: Path | None = None) -> Path:
    return (Path(root) if root is not None else ROOT) / GUARD_FILE


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read(root: Path | None) -> dict | None:
    path = guard_path(root)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
    except OSError as exc:
        return {"status": "unknown", "reason": f"the panel guard cannot be read: {exc}"}
    try:
        record = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"status": "unknown", "reason": f"the panel guard is not valid JSON: {exc}"}
    if not isinstance(record, dict):
        return {"status": "unknown", "reason": "the panel guard is not a JSON object"}
    missing = [field for field in REQUIRED_FIELDS if not record.get(field)]
    if missing:
        return {
            "status": "unknown",
            "reason": "the panel guard is missing " + ", ".join(missing),
        }
    return record


def inspect(root: Path | None = None) -> dict | None:
    """The active guard, ``None`` when there is none, or an ``unknown`` record.

    An unreadable guard is reported as unknown rather than absent: treating it as
    absent would let the next job run beside a dialog nobody can rule out.
    """
    record = _read(root)
    if record is None or record.get("status") == "unknown":
        return record
    if record.get("state") == "retired":
        return None
    return {**record, "status": "active"}


def summary(root: Path | None = None) -> dict | None:
    """The guard as a client may see it: who holds the session and how to release it.

    The nonce stays out of this view: it is the binding between a job and its own
    marker files, and nothing outside the job needs it. What a client needs is the
    holder's identity, whether the Toolkit channel is blocked, and the one supported
    way to end that block.
    """
    record = inspect(root)
    if record is None:
        return None
    if record.get("status") == "unknown":
        return {
            "state": "unknown",
            "blocks_toolkit": True,
            "reason": record.get("reason"),
            "release": (
                "An unreadable guard cannot be retired by a tool: confirm in Creo that no panel is "
                f"open, then remove {guard_path(root)}"
            ),
        }
    return {
        "state": "active",
        "job_id": record.get("job_id"),
        "model_id": record.get("model_id"),
        "profile_id": record.get("profile_id"),
        "mode": record.get("mode"),
        "since": record.get("created_at"),
        "blocks_toolkit": True,
        "release": (
            "Only a native exit observation, or creo_reconcile_model with "
            "action=confirm_panel_closed and confirm_panel_closed=true for this model, retires "
            "the guard; a dead pid, a cancelled job or an acknowledgement do not"
        ),
    }


def _write_guard_record(target: Path, record: dict) -> None:
    from creo_mechdog import bridge

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        bridge._replace_json(temporary, target)
    except BaseException:
        bridge._unlink_with_retry(temporary)
        raise


def reserve(
    job_id: str,
    *,
    nonce: str,
    profile_id: str,
    mode: str,
    model_id: str | None,
    executor_identity: object = None,
    root: Path | None = None,
    pid: int | None = None,
) -> dict:
    """Register the job that is about to open UI, or return its existing guard."""
    if not job_id or not nonce or not profile_id or not mode:
        raise ValueError("a panel guard needs the job id, nonce, profile id and mode")
    current = inspect(root)
    if current is not None:
        if current.get("status") == "unknown":
            raise PanelSessionLocked(
                f"A previous resident panel cannot be ruled out ({current.get('reason')}). "
                "No native work was started. Confirm in Creo that no panel is open, then "
                f"remove {guard_path(root)} before starting another panel run; an unreadable "
                "guard cannot be retired by a tool.",
                current,
            )
        if current["job_id"] != job_id:
            raise PanelSessionLocked(
                "Another resident panel job still owns the Creo session: "
                f"job_id={current['job_id']}, profile_id={current.get('profile_id')}, "
                f"model_id={current.get('model_id')}, since {current.get('created_at')}. "
                "A new job cannot start beside it; creo_reconcile_model on that model with "
                "action=confirm_panel_closed releases it once the panel is confirmed closed.",
                current,
            )
        return current
    record = {
        "job_id": job_id,
        "nonce": nonce,
        "profile_id": profile_id,
        "mode": mode,
        "model_id": model_id,
        # Which executor opened the panel. The callback *generation* is not readable
        # from Python yet (it arrives with the protocol-4 backend); this records the
        # worker facts a recovery path will need to match, and never releases anything.
        "executor_identity": executor_identity if isinstance(executor_identity, dict) else None,
        "created_at": _now(),
        "pid": pid if isinstance(pid, int) else os.getpid(),
        "state": "active",
    }
    target = guard_path(root)
    _write_guard_record(target, record)
    return {**record, "status": "active"}


def require_clear(
    *,
    job_id: str | None = None,
    operation: str = "native_operation",
    root: Path | None = None,
) -> None:
    """Refuse this Toolkit entry while a panel guard is active for another job."""
    if operation in EXEMPT_OPERATIONS:
        return
    current = inspect(root)
    if current is None:
        return
    if current.get("status") == "unknown":
        raise PanelSessionLocked(
            "A resident panel guard exists but cannot be read "
            f"({current.get('reason')}); the Creo session is treated as protected until a human "
            f"checks it and removes {guard_path(root)}. Native work was refused and no Toolkit "
            "call was made.",
            current,
        )
    if job_id and current["job_id"] == job_id:
        return
    raise PanelSessionLocked(
        "A resident panel may still be open in this Creo session: "
        f"job_id={current['job_id']}, profile_id={current.get('profile_id')}, "
        f"model_id={current.get('model_id')}, since {current.get('created_at')}. Native work is "
        "refused for every model until that exit is confirmed; local job and log queries stay "
        "available. creo_reconcile_model with action=confirm_panel_closed on that model releases "
        "this protection once a human has confirmed the panel is closed. No Toolkit call was "
        "made.",
        current,
    )


def retire(
    job_id: str,
    *,
    reason: str,
    evidence: object,
    root: Path | None = None,
) -> dict:
    """Release the guard only for the holder and only on positive evidence."""
    current = inspect(root)
    if current is None:
        raise ValueError(f"no active panel guard to retire for job {job_id}; nothing was changed")
    if current.get("status") == "unknown":
        raise PanelSessionLocked(
            f"The panel guard cannot be read ({current.get('reason')}); retire it through the "
            "documented recovery, not by rewriting the file",
            current,
        )
    if current["job_id"] != job_id:
        raise ValueError(
            f"the active panel guard belongs to job {current['job_id']}, not {job_id}; only the "
            "holder or the documented recovery may retire it"
        )
    if not isinstance(evidence, dict) or not any(
        evidence.get(key) is True for key in CLOSING_EVIDENCE
    ):
        raise ValueError(
            "retiring a panel guard needs confirmed evidence that the panel is closed "
            f"({', '.join(CLOSING_EVIDENCE)}); a dead pid, an expired token or a stale marker "
            "does not prove the dialog closed. The guard stays active."
        )
    record = {
        **{key: value for key, value in current.items() if key != "status"},
        "state": "retired",
        "retired_at": _now(),
        "retire_reason": reason,
        "retire_evidence": evidence,
    }
    target = guard_path(root)
    _write_guard_record(target, record)
    return record
