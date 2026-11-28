"""Explicit owned-model reconciliation. Never replay an uncertain modeling plan."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from creo_mechdog import bridge, creo_startup, inspection_refs, model_registry, panel_session_guard
from creo_mechdog import generic_bridge as general
from creo_mechdog.legacy_recovery import previous_boot_evidence
from creo_mechdog.recovery import process_identity
from creo_mechdog.windows_boot import boot_info

ACTIONS = (
    "restore_baseline",
    "accept_saved",
    "accept_live",
    "abandon_new",
    "ack_no_mutation",
    "ack_failure",
    "confirm_panel_closed",
    "abandon_stalled_recovery",
    "abandon_unknown_recovery",
)
# BUG-110: actions that touch a saved model or its component ownership stay
# limited to parts, sheetmetal and (BUG-157) assemblies; drawings are refused
# because their component ownership cannot be reconciled here. The two
# acknowledgements are metadata-only.
# BUG-131 adds one exception: abandon_new is also valid for a new assembly with
# no saved file and revision 0, because it owns nothing yet.
COMPONENT_ACTIONS = ("restore_baseline", "accept_saved", "accept_live", "abandon_new")
TERMINAL_FAILURE_STATUSES = ("failed", "unknown_outcome")
TOKEN_SECONDS = 600
WORKER_SECONDS = 300
# BUG-157: the native recovery phase budget. restore_baseline defaults to the
# faster identity verification; the phase itself is clamped here and again by
# the executor, so a bad config value can neither disarm nor explode the budget.
RECOVERY_PHASE_SECONDS = 300
RECOVERY_PHASE_MIN_SECONDS = 30
RECOVERY_PHASE_MAX_SECONDS = 1800
RECOVERY_PHASE_MARGIN_SECONDS = 30
RUNNER_CHANNEL_WAIT_SECONDS = 120
HASH_SECONDS = 8
# BUG-146: how long a persisted recovery intent may sit before its absent
# launcher/runner counts as proof that nothing ever started. The runner writes
# runner_identity as its first durable action, before it waits for the channel,
# so this window covers process creation and the first JSON write only.
STALLED_INTENT_SECONDS = 120
SNAPSHOT_SECONDS = 12
MAX_FILE_BYTES = 1024**3


class RecoveryRefused(ValueError):
    """A recovery evidence check failed at a known execution boundary."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def recovery_phase_seconds(model: dict | None = None, budget_seconds: int | None = None) -> int:
    """BUG-157/BUG-166: native recovery phase budget, clamped to 30-900 s.

    Uses explicit per-call ``budget_seconds`` when supplied; otherwise starts
    from ``config.json['recovery_phase_seconds']`` (default 300 s) and raises
    the floor for high-edge models (e.g. >2,700 edges -> up to 900 s) so a
    large model's recovery is never clipped by a fixed 90 s constant.
    """
    if budget_seconds is not None:
        if isinstance(budget_seconds, bool) or not isinstance(budget_seconds, int):
            raise ValueError(
                f"budget_seconds must be an integer from {RECOVERY_PHASE_MIN_SECONDS} "
                f"to {RECOVERY_PHASE_MAX_SECONDS}"
            )
        if not RECOVERY_PHASE_MIN_SECONDS <= budget_seconds <= RECOVERY_PHASE_MAX_SECONDS:
            raise ValueError(
                f"budget_seconds must be between {RECOVERY_PHASE_MIN_SECONDS} "
                f"and {RECOVERY_PHASE_MAX_SECONDS}"
            )
        return budget_seconds
    try:
        value = int(bridge.config().get("recovery_phase_seconds", RECOVERY_PHASE_SECONDS))
    except (TypeError, ValueError):
        value = RECOVERY_PHASE_SECONDS
    edges = 0
    features = 0
    surfaces = 0
    if isinstance(model, dict):
        summary = inspection_refs.summary_of(model)
        counts = summary.get("counts") if isinstance(summary, dict) else None
        if isinstance(counts, dict):
            if isinstance(counts.get("edges"), int):
                edges = counts["edges"]
            if isinstance(counts.get("features"), int):
                features = counts["features"]
            if isinstance(counts.get("surfaces"), int):
                surfaces = counts["surfaces"]
    edge_floor = 120 + edges // 15 if edges > 0 else 0
    feature_floor = 120 + features // 2 if features > 0 else 0
    surface_floor = 120 + surfaces // 4 if surfaces > 0 else 0
    adaptive_floor = min(RECOVERY_PHASE_MAX_SECONDS, max(edge_floor, feature_floor, surface_floor))
    return min(RECOVERY_PHASE_MAX_SECONDS, max(RECOVERY_PHASE_MIN_SECONDS, value, adaptive_floor))


def _binding(snapshot: dict) -> str:
    # Windows can remove an exited process object after the last open handle
    # closes. Both observations prove the same recorded owner has stopped.
    stable = {
        # BUG-146: the stalled-intent diagnosis carries an age that changes on
        # every read; it is not an identity, so it never binds an evidence token.
        **{key: value for key, value in snapshot.items() if key != "stalled_recovery"},
        "owners": [
            {
                "job_id": owner["job_id"],
                "stopped": owner["stopped"],
                "runner": owner["runner"].get("recorded"),
                "worker": owner["worker"].get("recorded"),
                "stop_evidence": owner.get("stop_evidence"),
            }
            for owner in snapshot["owners"]
        ],
    }
    return digest(stable)


def identity(file: Path, deadline: float | None = None) -> dict:
    """Bounded streaming hash; a missing/unreadable/oversized file is never trusted."""
    deadline = min(deadline or float("inf"), time.monotonic() + HASH_SECONDS)
    if file.is_symlink() or any(p.is_symlink() or p.is_junction() for p in file.parents):
        raise ValueError("Recovery evidence cannot traverse links")
    before = file.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError("Recovery evidence exceeds the 1 GiB hash budget")
    sha = hashlib.sha256()
    with file.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if time.monotonic() > deadline:
                raise ValueError("Recovery evidence hash budget exceeded; no action accepted")
            sha.update(chunk)
    after = file.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Recovery evidence changed while hashing")
    return {"path": str(file.resolve()), "size_bytes": after.st_size, "sha256": sha.hexdigest()}


def owned_file(model: dict, value: str) -> Path:
    output = general.model_path(model["model_id"]) / "output"
    file = Path(value)
    if not file.is_absolute() or file.parent.resolve() != output.resolve():
        raise ValueError("Selected source is outside this model's managed output")
    extension = {"assembly": "asm", "drawing": "drw"}.get(model.get("model_type"), "prt")
    if not re.fullmatch(re.escape(model["model_name"]) + rf"\.{extension}\.\d+", file.name, re.I):
        raise ValueError("Selected source does not match the owned native model name")
    return file


READ_BUDGET_BYTES = 16 * 1024 * 1024

# File families this module reads under one budget (BUG-077): job manifests,
# request manifests, native results/checkpoints and recovery side records.
_READ_KINDS = {
    "job.json": "job_manifest",
    "request.json": "request_manifest",
    "native_result.json": "native_result",
    "native_checkpoint.json": "native_checkpoint",
    "native_owner.json": "native_owner",
}


class RecoveryMetadataBudgetExceeded(ValueError):
    """A recovery metadata read exceeded its budget; the error text is JSON."""

    def __init__(
        self,
        *,
        file: Path,
        failed_stage: str,
        metadata_kind: str,
        job_id: str | None = None,
        model_id: str | None = None,
    ):
        actual = file.stat().st_size if file.is_file() else None
        try:
            shown = str(file.resolve().relative_to(bridge.ROOT))
        except (OSError, ValueError):
            shown = str(file)
        self.payload = {
            "reason_code": "RECOVERY_METADATA_BUDGET_EXCEEDED",
            "metadata_kind": metadata_kind,
            "path": shown,
            "actual_bytes": actual,
            "budget_bytes": READ_BUDGET_BYTES,
            "failed_stage": failed_stage,
            "job_id": job_id,
            "model_id": model_id,
            "recovery": (
                "Keep the oversized file unchanged for diagnosis; run "
                "creo_registry_health to list oversized or unmigrated entries, then "
                "creo_migrate_registry (inspect, then apply) to split legacy inline "
                "records into detail sidecars. Do not delete the file, edit it by "
                "hand, or raise the budget to hide the error"
            ),
        }
        super().__init__(json.dumps(self.payload, ensure_ascii=False))


def _read(
    file: Path,
    *,
    failed_stage: str = "recovery_metadata_read",
    job_id: str | None = None,
    model_id: str | None = None,
) -> dict | None:
    if file.is_file() and file.stat().st_size > READ_BUDGET_BYTES:
        raise RecoveryMetadataBudgetExceeded(
            file=file,
            failed_stage=failed_stage,
            metadata_kind=_READ_KINDS.get(file.name, "recovery_metadata"),
            job_id=job_id,
            model_id=model_id,
        )
    return bridge.read_json(file) if file.is_file() else None


def _directory(model_id: str) -> Path:
    directory = general.model_path(model_id) / "reconciliation"
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("Reconciliation directory cannot be a link")
    directory.mkdir(exist_ok=True)
    return directory


def _baseline_hash(model: dict) -> str | None:
    """Use recorded successful output, never bless current file bytes as a baseline."""
    if model.get("part_sha256"):
        return model["part_sha256"]
    current = model
    seen = set()
    model_id = model.get("model_id")
    for _ in range(16):
        job_id = current.get("last_job")
        if not job_id or job_id in seen:
            break
        seen.add(job_id)
        directory = bridge.job_path(job_id)
        job = (
            _read(
                directory / "job.json",
                failed_stage="baseline_history_read",
                job_id=job_id,
                model_id=model_id,
            )
            or {}
        )
        result = job.get("result") or {}
        if job.get("status") == "succeeded" and result.get("part_file") == model.get("part_file"):
            return result.get("sha256")
        current = (
            _read(
                directory / "request.json",
                failed_stage="baseline_history_read",
                job_id=job_id,
                model_id=model_id,
            )
            or {}
        ).get("model", {})
    return None


def validate_baseline(model: dict) -> None:
    if not model.get("part_file"):
        raise ValueError(
            "model_reconciliation_required: no verified saved baseline; inspect creo_reconcile_model"
        )
    expected = _baseline_hash(model)
    if not expected or identity(owned_file(model, model["part_file"]))["sha256"] != expected:
        raise ValueError(
            "model_reconciliation_required: saved baseline identity is unverified or changed"
        )


def admission_failure_message(message: str) -> str:
    """BUG-121: name the action a writable plan needs after a baseline compare.

    The native admission compare reports the symptom ("Saved feature/body count
    changed") and the caller is left to guess that read-only reads are unaffected
    and which reconciliation action unblocks an edit. The native text is kept and
    the actionable part is appended once; a message that already names the tool is
    returned unchanged.
    """
    if not isinstance(message, str) or not message.startswith("model_reconciliation_required:"):
        return message
    if "creo_reconcile_model" in message:
        return message
    return (
        message + " Action: read-only reads (creo_export_model, creo_dump_feature_tree, "
        "creo_measure_*) are not gated by this compare; to keep editing, run "
        "creo_reconcile_model to see the available actions and apply one (restore_baseline keeps "
        "the saved file, accept_saved adopts the file the GUI saved), then retry with the "
        "revision it returns."
    )


def _stopped(recorded: dict | None) -> dict:
    if (
        not isinstance(recorded, dict)
        or type(recorded.get("pid")) is not int
        or recorded["pid"] <= 0
    ):
        return {"stopped": False, "reason": "No recorded process identity"}
    observed = process_identity(recorded["pid"])
    if observed.get("alive") is False:
        stopped = True
    elif (
        observed.get("alive") is True
        and type(recorded.get("created")) is int
        and recorded["created"] > 0
        and type(observed.get("created")) is int
        and observed["created"] > 0
    ):
        stopped = recorded["created"] != observed["created"]
    else:
        stopped = False
    return {"recorded": recorded, "observed": observed, "stopped": stopped}


def _legacy_identity_incomplete(recorded: dict | None) -> bool:
    """Missing PID/creation fields may use reboot proof; malformed values may not."""
    if recorded is None:
        return True
    if not isinstance(recorded, dict):
        return False
    pid, created = recorded.get("pid"), recorded.get("created")
    missing_pid = pid is None
    missing_created = created is None or (type(created) is int and created == 0)
    return (
        (missing_pid or type(pid) is int and pid > 0)
        and (missing_created or type(created) is int and created > 0)
        and (missing_pid or missing_created)
    )


def _age_seconds(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - moment).total_seconds())


def _stalled_intent(directory: Path, job: dict) -> dict:
    """BUG-146: prove that a persisted recovery intent never started anything.

    0.34.0 feedback: a recovery job stayed ``queued``/``intent_persisted`` while
    its owner PID was gone, and every action reported "cannot be proven
    stopped", so the model was unrecoverable even though its disk baseline was
    healthy. A job that never recorded a runner, never reported a started
    worker and has no native identity cannot be stopped by a live process *if*
    the process that wrote the intent is provably gone. Nothing is assumed:

    * a started worker or any native file keeps the ordinary identity rules --
      this proof never overrides a record;
    * a recorded runner is not trusted either way: it must be provably exited
      (gone, or the same PID with a different creation time) before the intent
      counts as stalled. A live or unreadable runner keeps the job protected;
    * the launcher identity must be present and readable; a live launcher with
      the same creation time protects the job, and a reused PID (same number,
      different creation time) counts as exited;
    * the intent must be older than the runner's own first-write window.
    """
    if job.get("kind") != "reconciliation":
        return {"proven": False, "reason": "not_a_recovery_intent"}
    # Both stages are still before the native worker: a runner that died after
    # reserving the channel (``waiting_for_channel``) is exactly as stuck as one
    # that died before its first write, and the real 2026-11-21 case landed
    # there.
    if job.get("stage") not in ("intent_persisted", "waiting_for_channel"):
        return {"proven": False, "reason": "stage_advanced"}
    if job.get("status") not in ("queued", "waiting_for_channel"):
        return {"proven": False, "reason": "job_is_not_pending"}
    if job.get("worker_started") is not False:
        return {"proven": False, "reason": "worker_start_undetermined"}
    runner = job.get("runner_identity")
    runner_exited = False
    if runner is not None:
        if (
            not isinstance(runner, dict)
            or type(runner.get("pid")) is not int
            or type(runner.get("created")) is not int
            or runner["pid"] <= 0
            or runner["created"] <= 0
        ):
            return {"proven": False, "reason": "runner_identity_unreadable", "runner": runner}
        seen_runner = process_identity(runner["pid"])
        if seen_runner.get("alive") is None:
            return {
                "proven": False,
                "reason": "runner_identity_unreadable",
                "runner": runner,
                "runner_observed": seen_runner,
            }
        if seen_runner.get("alive") and seen_runner.get("created") == runner["created"]:
            return {
                "proven": False,
                "reason": "runner_still_alive",
                "runner": runner,
                "runner_observed": seen_runner,
            }
        runner_exited = True
    for name in ("native_owner.json", "native_checkpoint.json", "native_result.json"):
        if (directory / name).is_file():
            return {"proven": False, "reason": f"{name}_present"}
    launcher = job.get("launched_by")
    if (
        not isinstance(launcher, dict)
        or type(launcher.get("pid")) is not int
        or launcher["pid"] <= 0
        or type(launcher.get("created")) is not int
        or launcher["created"] <= 0
    ):
        # Intents written before this field existed stay protected; the reboot
        # evidence chain is their only route.
        return {"proven": False, "reason": "launcher_identity_unavailable"}
    observed = process_identity(launcher["pid"])
    if observed.get("alive") is None:
        return {
            "proven": False,
            "reason": "launcher_identity_unreadable",
            "launcher": launcher,
            "observed": observed,
        }
    reused = bool(observed.get("alive")) and observed.get("created") != launcher["created"]
    if observed.get("alive") and not reused:
        return {
            "proven": False,
            "reason": "launcher_still_alive",
            "launcher": launcher,
            "observed": observed,
        }
    age = _age_seconds(job.get("created_at"))
    if age is None:
        return {"proven": False, "reason": "intent_age_unknown"}
    if age < STALLED_INTENT_SECONDS:
        return {
            "proven": False,
            "reason": "within_startup_window",
            "age_seconds": round(age, 3),
        }
    return {
        "proven": True,
        "job_id": job.get("job_id"),
        "basis": (
            "runner_exited"
            if runner_exited
            else ("launcher_pid_reused" if reused else "launcher_exited")
        ),
        "stage": job.get("stage"),
        "runner": runner,
        "launcher": launcher,
        "observed": observed,
        "age_seconds": round(age, 3),
        "grace_seconds": STALLED_INTENT_SECONDS,
        "evidence": (
            "No started worker and no native file were recorded, every recorded process "
            "identity (runner and launcher) is provably gone, so nothing can still be "
            "executing this intent"
            if runner_exited
            else (
                "No runner identity, no started worker and no native file were recorded; the "
                "process that persisted the intent is provably gone, so nothing can still be "
                "executing it"
            )
        ),
        "limits": (
            "This proves the intent never started; it never accepts a model state, changes a "
            "revision or releases the model's own pending job"
        ),
    }


def _owners(
    job_id: str,
    boot_reader: Callable[[], dict | None] | None = None,
    *,
    read_metadata: Callable[[Path], dict | None] | None = None,
) -> dict:
    directory = bridge.job_path(job_id)
    reader = read_metadata or _read
    job = reader(directory / "job.json") or {}
    runner = _stopped(job.get("runner_identity"))
    owner = (
        reader(directory / "native_owner.json")
        if (directory / "native_owner.json").is_file()
        else None
    )
    checkpoint = (
        (reader(directory / "native_checkpoint.json") or {})
        if (directory / "native_checkpoint.json").is_file()
        else {}
    )
    worker_identity = owner or (
        {"pid": checkpoint["native_pid"]} if checkpoint.get("native_pid") else None
    )
    if owner:
        worker = _stopped(owner)
    else:
        if job.get("worker_started") is False and runner["stopped"]:
            worker = {"stopped": True, "reason": "Runner ended before native worker started"}
        elif job.get("worker_terminated_on_timeout") is True and runner["stopped"]:
            worker = {
                "stopped": True,
                "reason": "Native worker was terminated by runner on timeout",
            }
        elif (
            job.get("worker_started") is None
            and runner["stopped"]
            and job.get("stage")
            in (
                "queued",
                "intent_persisted",
                "waiting_for_channel",
                "building_worker",
                "cancel_requested",
            )
            and not any(
                (directory / name).exists()
                for name in (
                    "native_owner.json",
                    "native_checkpoint.json",
                    "native_result.json",
                    "worker.log",
                    "native.log",
                )
            )
        ):
            worker = {
                "stopped": True,
                "reason": "Runner ended before starting any native worker (no ownership artifact)",
            }
        elif checkpoint.get("native_pid"):
            worker = _stopped({"pid": checkpoint["native_pid"]})
        else:
            # A runner without native ownership evidence may have died between
            # spawning a legacy worker and persisting its PID. Do not guess.
            worker = {"stopped": False, "reason": "Native owner identity is unavailable"}
    result = {
        "job_id": job_id,
        "runner": runner,
        "worker": worker,
        "stopped": runner["stopped"] and worker["stopped"],
    }
    # BUG-146: a recovery intent that provably never started is stopped by
    # definition. The proof is recorded either way so a client can see why an
    # intent is still protected instead of only reading "cannot be proven".
    stalled = _stalled_intent(directory, job)
    result["stalled_intent"] = stalled
    if not result["stopped"] and stalled["proven"]:
        runner.update(stopped=True, reason="The recovery intent never started a runner")
        worker.update(stopped=True, reason="The recovery intent never started a worker")
        result["stopped"] = True
    # A complete but live/unreadable recorded identity never gets a time-based override.
    missing_runner = not runner["stopped"] and _legacy_identity_incomplete(
        job.get("runner_identity")
    )
    missing_worker = not worker["stopped"] and _legacy_identity_incomplete(worker_identity)
    eligible = (runner["stopped"] or missing_runner) and (worker["stopped"] or missing_worker)
    if not result["stopped"] and eligible:
        proof = previous_boot_evidence(directory, job, (boot_reader or boot_info)())
        if proof["stopped"]:
            result["stop_evidence"] = proof
            for missing, value in ((missing_runner, runner), (missing_worker, worker)):
                if missing:
                    value.update(stopped=True, reason="Historical owner predates verified OS boot")
            result["stopped"] = runner["stopped"] and worker["stopped"]
        else:
            result["reason"] = proof["reason"]
            result["guidance"] = (
                "Preserve job/model files. Missing legacy identities require all job records "
                "to predate an independently verified Windows boot. After an operator-controlled "
                "restart, inspect again; no action can bypass uncertain ownership."
            )
    return result


def _deployment(deadline: float) -> str:
    names = (
        "bridge.py",
        "server.py",
        "src/creo_mechdog/bridge.py",
        "src/creo_mechdog/server.py",
        "src/creo_mechdog/generic_bridge.py",
        "version.py",
        "src/creo_mechdog/reconciliation.py",
        "src/creo_mechdog/legacy_recovery.py",
        "src/creo_mechdog/windows_boot.py",
        "src/creo_mechdog/adoption.py",
        "src/creo_mechdog/file_adoption.py",
        "native/adoption_source.h",
        "native/inspection_sidecar.h",
        "native/generic.cpp",
        # FEAT-058: the deployment identity has to move with the planar wall,
        # otherwise a service running new wall code reports the old fingerprint.
        "src/creo_mechdog/native_planar_wall.py",
        "native/planar_wall.cpp",
        "native/planar_wall.h",
        "native/result_delivery.h",
        "native/worker_result_delivery.h",
        "native/recovery_deadline.h",
        "src/creo_mechdog/blend_callback.py",
        "native/worker.cpp",
        "native/blend_create.cpp",
        "native/blend_sync.cpp",
        "native/blend_loader.cpp",
        "native/callback_runtime.h",
        "native/callback_api.h",
        "native/callback_identity.h",
    )
    values = [identity(bridge.ROOT / name, deadline) for name in names]
    setup = bridge.ROOT / "build/blend_callback_setup.json"
    values.append(identity(setup, deadline) if setup.is_file() else {"callback": "not_prepared"})
    worker = bridge.ROOT / "build/creo_worker.exe"
    values.append(identity(worker, deadline) if worker.is_file() else {"worker": "not_built"})
    return digest(values)


def _cached_boot_reader() -> Callable[[], dict | None]:
    observations = []

    def read() -> dict | None:
        if not observations:
            observations.append(boot_info())
        return observations[0]

    return read


def _snapshot(model_id: str) -> dict:
    deadline = time.monotonic() + SNAPSHOT_SECONDS
    model = general.model_info(model_id)
    if (
        Path(model["output_directory"]).resolve()
        != (general.model_path(model_id) / "output").resolve()
    ):
        raise ValueError("Model output registration is not owned")
    job_ids = list(
        dict.fromkeys(
            j
            for j in (
                model.get("recovery_pending"),
                model.get("pending_job"),
                model.get("last_job"),
            )
            if j
        )
    )
    files = []
    owners = []
    candidate = None
    stalled_recovery = None
    verified_boot = _cached_boot_reader()

    for job_id in job_ids:
        directory = bridge.job_path(job_id)
        job = (
            _read(
                directory / "job.json",
                failed_stage="recovery_snapshot",
                job_id=job_id,
                model_id=model_id,
            )
            or {}
        )
        request = (
            _read(
                directory / "request.json",
                failed_stage="recovery_snapshot",
                job_id=job_id,
                model_id=model_id,
            )
            or {}
        )
        if job.get("model_id") != model_id or request.get("model", {}).get("model_id") != model_id:
            raise ValueError("Job evidence is not bound to this model")
        owners.append(_owners(job_id, verified_boot))
        if model.get("recovery_pending") == job_id:
            stalled_recovery = owners[-1].get("stalled_intent")
        for name in (
            "job.json",
            "request.json",
            "native_checkpoint.json",
            "native_result.json",
            "native_owner.json",
        ):
            file = directory / name
            if file.is_file():
                files.append(identity(file, deadline))
        for name in ("native_result.json", "native_checkpoint.json"):
            # Oversized raw native files are skipped, not fatal: the split job
            # manifest result (references only) can still supply the candidate
            # (BUG-077). Both sources are checked below in order.
            try:
                raw_results = [
                    _read(
                        directory / name,
                        failed_stage="recovery_snapshot",
                        job_id=job_id,
                        model_id=model_id,
                    )
                ]
            except RecoveryMetadataBudgetExceeded:
                raw_results = []
            sources = []
            if isinstance(job.get("result"), dict):
                sources.append(("job.json", job["result"]))
            sources.extend((name, value) for value in raw_results if value is not None)
            for evidence_name, result in sources:
                if not isinstance(result, dict):
                    continue
                if (
                    candidate is None
                    and result.get("success")
                    and result.get("saved_file_reloaded_and_verified")
                    and result.get("part_file")
                    and (result.get("inspection") or result.get("inspection_ref"))
                ):
                    try:
                        file = owned_file(model, result["part_file"])
                        candidate = {
                            "job_id": job_id,
                            "evidence": evidence_name,
                            "identity": identity(file, deadline),
                            # New results carry a controlled reference (BUG-076);
                            # legacy results inline the payload. Keep whichever
                            # form exists; consumers resolve both.
                            "inspection": result.get("inspection"),
                            "inspection_ref": result.get("inspection_ref"),
                            "aliases": result.get("aliases", {}),
                            "aliases_ref": result.get("aliases_ref"),
                        }
                        warnings = inspection_refs.warnings_of(result)
                        if warnings:
                            candidate["inspection_warnings"] = warnings
                        # A recorded reference whose sidecar was removed is not
                        # published as readable; the candidate keeps its identity
                        # and reports why the payload is unavailable (DEV-048 T02).
                        if candidate.get("inspection_ref") is not None:
                            try:
                                inspection_refs.verify_ref(candidate["inspection_ref"])
                            except inspection_refs.InspectionRefInvalid as error:
                                candidate.pop("inspection_ref", None)
                                inspection_refs.add_warning(
                                    candidate,
                                    stage="verified",
                                    reason_code="inspection_ref_invalid",
                                    fallback_status="not_attempted",
                                    message=(
                                        "Recorded inspection reference is no longer "
                                        f"readable: {error}"
                                    ),
                                )
                    except (OSError, ValueError) as error:
                        candidate = {"error": str(error)}
    baseline = None
    if model.get("part_file"):
        try:
            baseline = {
                "identity": identity(owned_file(model, model["part_file"]), deadline),
                "expected_sha256": _baseline_hash(model),
            }
            baseline["verified"] = baseline["identity"]["sha256"] == baseline["expected_sha256"]
        except (OSError, ValueError) as error:
            baseline = {"verified": False, "error": str(error)}
    if time.monotonic() > deadline:
        raise ValueError("Recovery snapshot exceeded its 12 second budget")
    return {
        "model": model,
        "owners": owners,
        "files": files,
        "baseline": baseline,
        "candidate": candidate,
        "stalled_recovery": stalled_recovery,
        "deployment": _deployment(deadline),
        "runtime_selection": digest(
            {key: bridge.config().get(key) for key in ("creo_root", "creo_session_id")}
        ),
    }


def _job_status(job_id: object) -> str | None:
    """Status of one job record, or None when it cannot be read."""
    if not isinstance(job_id, str) or not bridge.JOB_ID.fullmatch(job_id):
        return None
    try:
        return bridge.get_job(job_id, "compact").get("status")
    except (OSError, ValueError):
        return None


def _pending_job_status(model: dict) -> str | None:
    """Status of the model's pending job, or None when it cannot be read."""
    return _job_status(model.get("pending_job"))


def _readonly_pending(model: dict) -> dict | None:
    """BUG-149: name the exit for a reservation held by a read-only job.

    A read-only plan only inspects, so a model that still names one as
    ``pending_job`` has no geometry to reconcile - the reservation is metadata
    that ``creo_cancel_job`` retires without native work. That path is reported
    here because this is the tool an operator opens when the model looks stuck,
    and the ordinary recovery actions cannot clear it.
    """
    job_id = model.get("pending_job")
    if not isinstance(job_id, str) or not bridge.JOB_ID.fullmatch(job_id):
        return None
    try:
        manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("readonly") is not True:
        return None
    return {
        "job_id": job_id,
        "job_status": manifest.get("status"),
        "readonly_source": manifest.get("readonly_source"),
        "reason": (
            "The pending job was read-only: it could not change geometry, the revision or the "
            "saved file, so the model has no unknown outcome to reconcile"
        ),
        "next_step": (
            "creo_cancel_job with this job_id retires the reservation once no recorded runner or "
            "worker of that job is alive; it performs no native work"
        ),
    }


def _panel_guard_state(model: dict, owners: list[dict] | None = None) -> dict:
    """The resident panel guard as it applies to this model.

    BUG-120/D4.4 + BUG-199: a guard blocks every Toolkit entry, including the
    actions above, so the only way out is an action that takes no Toolkit call.
    It stays model-scoped: the operator confirms a panel that a job of this model
    opened, once that job reached a terminal status OR all recorded owners
    (starting from runner_identity) are provably stopped so nothing can still
    drive the dialog.
    """
    guard = panel_session_guard.inspect(bridge.ROOT)
    if guard is None:
        return {"active": False, "job_id": None, "status": None, "available": False}
    if guard.get("status") != "active":
        return {
            "active": True,
            "readable": False,
            "job_id": None,
            "status": None,
            "available": False,
            "reason": guard.get("reason"),
        }
    job_id = guard.get("job_id")
    mine = guard.get("model_id") == model.get("model_id")
    owners_recorded = False
    owners_stopped = False
    if mine and isinstance(job_id, str) and bridge.JOB_ID.fullmatch(job_id):
        try:
            guard_job = bridge.read_json(bridge.job_path(job_id) / "job.json")
        except (OSError, ValueError):
            guard_job = None
        if isinstance(guard_job, dict) and isinstance(guard_job.get("runner_identity"), dict):
            owners_recorded = True
            matched = next(
                (entry for entry in (owners or []) if entry.get("job_id") == job_id),
                None,
            )
            if matched is None:
                matched = _owners(job_id)
            owners_stopped = bool(matched.get("stopped"))
    return {
        "active": True,
        "readable": True,
        "job_id": job_id,
        "model_id": guard.get("model_id"),
        "profile_id": guard.get("profile_id"),
        "since": guard.get("created_at"),
        "status": _job_status(job_id),
        "mine": mine,
        "owners_recorded": owners_recorded,
        "owners_stopped": owners_stopped,
    }


def _recovery_wait(snapshot: dict) -> dict | None:
    """BUG-146: say why a reserved recovery job has not advanced.

    0.34.0 feedback reported only ``queued``/``intent_persisted`` for six
    minutes. This block names the observed cause and the one action that fits,
    and never claims the model's own outcome was decided.
    """
    job_id = snapshot["model"].get("recovery_pending")
    if not job_id:
        return None
    stalled = snapshot.get("stalled_recovery") or {}
    if stalled.get("proven"):
        basis = stalled.get("basis")
        return {
            "job_id": job_id,
            "state": "stalled_intent_proven",
            "reason": (
                "The recovery runner exited before a native worker started, and nothing else "
                "holds the intent"
                if basis == "runner_exited"
                else (
                    "The recovery intent never started a runner or worker, and the process that "
                    "persisted it is gone"
                )
            ),
            "detail": {
                key: stalled.get(key)
                for key in (
                    "basis",
                    "stage",
                    "age_seconds",
                    "grace_seconds",
                    "runner",
                    "launcher",
                    "observed",
                )
                if stalled.get(key) is not None
            },
            "next_step": (
                "abandon_stalled_recovery with confirm_stalled_recovery=true closes this intent "
                "without touching the model's pending job, revision, file or session"
            ),
        }
    reason = stalled.get("reason") or "The recovery intent's ownership is still unproven"
    rec_status = _job_status(job_id)
    if rec_status in ("failed", "unknown_outcome", "aborted", "cancelled"):
        return {
            "job_id": job_id,
            "state": "terminal_unconfirmed",
            "job_status": rec_status,
            "reason": (
                f"Recovery job {job_id} already ended with terminal status {rec_status!r} while "
                "holding recovery_pending"
            ),
            "detail": {
                key: stalled.get(key)
                for key in (
                    "stage",
                    "age_seconds",
                    "grace_seconds",
                    "runner",
                    "runner_observed",
                    "launcher",
                    "observed",
                )
                if stalled.get(key) is not None
            },
            "next_step": (
                "Do not poll creo_get_job further (the recovery job is already terminal). "
                "Once all recorded owners are stopped, call creo_reconcile_model with "
                "action='restore_baseline' (default verify_mode='identity', or pass a larger "
                "budget_seconds up to 1800) or release recovery_pending via "
                "action='abandon_unknown_recovery' with confirm_unknown_recovery=true"
            ),
        }
    next_step = {
        "stage_advanced": (
            "The job advanced past the pre-worker stages, so its runner is the only source of "
            "truth now: poll creo_get_job and read its stage"
        ),
        "runner_still_alive": (
            "The recorded runner process is still alive; poll the job until it exits or reports "
            "a terminal stage"
        ),
        "launcher_still_alive": (
            "The process that persisted this intent is still alive; a retry from that client is "
            "the shortest route"
        ),
        "within_startup_window": (
            "The intent is younger than the startup window; poll again after the grace period "
            "before concluding it is stuck"
        ),
    }.get(
        reason,
        "Poll the job; while a recorded process identity is alive or unreadable no action can "
        "prove the intent stopped",
    )
    return {
        "job_id": job_id,
        "state": "protected",
        "reason": reason,
        "detail": {
            key: stalled.get(key)
            for key in (
                "stage",
                "age_seconds",
                "grace_seconds",
                "runner",
                "runner_observed",
                "launcher",
                "observed",
            )
            if stalled.get(key) is not None
        },
        "next_step": next_step,
    }


def _actions(snapshot: dict, live: dict | None) -> dict:
    model = snapshot["model"]
    # BUG-131 live cancel: a job cancelled before the worker started releases
    # pending_job and may leave no job evidence at all, so owners is empty.
    # There is then no runner/worker to stop; requiring a non-empty owner list
    # turned a successful cancel into "cannot be proven stopped" and blocked
    # every recovery action. Empty owners is vacuously stopped.
    stopped = all(owner["stopped"] for owner in snapshot["owners"])
    baseline = snapshot["baseline"] or {}
    candidate = snapshot["candidate"] or {}
    health = inspection_refs.summary_of(live).get("healthy") is True
    model_type = model.get("model_type", "part")
    part_family = model_type in ("part", "sheetmetal")
    # BUG-157: an assembly may be restored to its verified baseline and may
    # accept a saved/live state; drawings keep refusing every component action.
    recovery_supported = part_family or model_type == "assembly"
    uncommitted = not model.get("part_file") and model.get("revision") == 0
    # BUG-131: a brand-new assembly has no committed geometry and no component
    # ownership to preserve, so erasing it is exactly abandon_new's contract.
    # A committed assembly keeps the part/sheetmetal limit for erasure.
    abandon_supported = part_family or (model_type == "assembly" and uncommitted)
    # An assembly always has component dependencies, so admission reads the
    # owned-directory answer instead of the part-level "dependency free" one.
    dependencies_ok = (
        (
            bool(live.get("dependency_free"))
            if part_family
            else live.get("dependencies_owned") is True
        )
        if live
        else False
    )
    conditions = {
        "restore_baseline": baseline.get("verified")
        and bool(model.get("inspection") or model.get("inspection_ref")),
        "accept_saved": bool(candidate.get("identity"))
        and candidate.get("identity", {}).get("path") != model.get("part_file"),
        "accept_live": live
        and live.get("loaded")
        and live.get("owned")
        and health
        and live.get("millimeter_units")
        and dependencies_ok,
        "abandon_new": uncommitted,
    }
    action_supported = {
        "restore_baseline": recovery_supported,
        "accept_saved": recovery_supported,
        "accept_live": recovery_supported,
        "abandon_new": abandon_supported,
    }
    if model.get("status") == "adopt_pending":
        # Adoption requires explicit confirmation, not recovery acceptance of
        # its saved candidate (including an uncertain partially prepared copy).
        for action in ("restore_baseline", "accept_saved", "accept_live"):
            conditions[action] = False
    states = {
        action: {
            "available": bool(
                stopped and action_supported[action] and ok and model.get("status") != "abandoned"
            ),
            "reason": (
                "Previous runner/worker is active or cannot be proven stopped"
                if not stopped
                else (
                    "Drawing reconciliation is not supported; preserve component ownership"
                    if model_type == "drawing"
                    else "Abandoning a committed assembly is refused; restore its verified "
                    "baseline instead"
                )
                if not action_supported[action]
                else "Model is already abandoned"
                if model.get("status") == "abandoned"
                else (
                    "restore_baseline requires a verified baseline file and its recorded "
                    "inspection; the current part_file does not match the baseline hash"
                    if action == "restore_baseline" and model_type == "assembly"
                    else "Required baseline/candidate/owned healthy live evidence is unavailable"
                )
                if not ok
                else "Explicit apply with matching evidence and idempotency key required"
            ),
        }
        for action, ok in conditions.items()
    }
    # BUG-105: a failed job that provably changed nothing may be acknowledged
    # back to ready without native work. This is a metadata transaction only,
    # so assembly/drawing models are eligible too: component ownership is never
    # touched. Any contrary evidence keeps the model unrecoverable here.
    # BUG-131: a new assembly whose only job already ended in failure still owns
    # that job as pending_job, so requiring no pending job left it with no exit.
    # The reservation blocks only while it can still finish; a terminal failure
    # on an uncommitted assembly is exactly what these acknowledgements accept.
    recoverable_new_assembly = (
        model.get("model_type") == "assembly"
        and uncommitted
        and not model.get("recovery_pending")
        and _pending_job_status(model) in TERMINAL_FAILURE_STATUSES
    )
    pending = bool(model.get("pending_job") or model.get("recovery_pending"))
    pending_blocks = pending and not recoverable_new_assembly
    ack_ready = (
        model.get("status") == "failed"
        and not pending_blocks
        and model.get("rollback_status") != "failed"
        and baseline.get("verified") is True
    )
    states["ack_no_mutation"] = {
        "available": bool(stopped and ack_ready),
        "reason": (
            "Previous runner/worker is active or cannot be proven stopped"
            if not stopped
            else "Only a failed model can acknowledge zero mutation"
            if model.get("status") != "failed"
            else "Model still owns a pending or recovery job"
            if pending_blocks
            else "Rollback of the failed job did not succeed; zero mutation cannot be proven"
            if model.get("rollback_status") == "failed"
            else "Checkpoint identity is unavailable or has changed; zero mutation cannot be proven"
            if baseline.get("verified") is not True
            else "Explicit apply with confirm_zero_mutation=true, matching evidence and an "
            "idempotency key required"
        ),
    }
    # BUG-110: a failed job whose model must not re-own its components had no
    # other exit than hand-editing model.json. This acknowledgement records that
    # the failure is accepted and puts the model back to ready; it is metadata
    # only, so assembly/drawing models are eligible, and it never claims the disk
    # state was verified.
    ack_failure_ready = (
        model.get("status") in TERMINAL_FAILURE_STATUSES
        and not pending_blocks
        and model.get("rollback_status") != "failed"
    )
    states["ack_failure"] = {
        "available": bool(stopped and ack_failure_ready),
        "reason": (
            "Previous runner/worker is active or cannot be proven stopped"
            if not stopped
            else "Only a model whose last job ended in failure can acknowledge a failure"
            if model.get("status") not in TERMINAL_FAILURE_STATUSES
            else "Model still owns a pending or recovery job"
            if pending_blocks
            else "Rollback of the failed job did not succeed; inspect before acknowledging"
            if model.get("rollback_status") == "failed"
            else "Explicit apply with confirm_failure_ack=true, matching evidence and an "
            "idempotency key required"
        ),
    }
    guard = _panel_guard_state(model, snapshot.get("owners"))
    # BUG-146: a recovery intent that provably never started a runner or worker
    # holds recovery_pending forever, and every other action reports it as an
    # owner that "cannot be proven stopped". Closing it is metadata only: the
    # model's own pending job, revision, saved file and session stay protected.
    stalled = snapshot.get("stalled_recovery") or {}
    stalled_target = bool(
        stalled.get("proven")
        and stalled.get("job_id")
        and model.get("recovery_pending") == stalled.get("job_id")
    )
    states["abandon_stalled_recovery"] = {
        "available": bool(stopped and stalled_target),
        "reason": (
            "Previous runner/worker is active or cannot be proven stopped"
            if not stopped
            else "No recovery intent is provably stalled; this action only closes an intent "
            "that recorded no started worker and no native file, whose stage is still before "
            "the worker, and whose recorded runner and launcher are provably gone"
            if not stalled_target
            else "Explicit apply with confirm_stalled_recovery=true, matching evidence and an "
            "idempotency key required"
        ),
        "stalled_intent": stalled or None,
    }
    terminal = general.CANCEL_TERMINAL_STATUSES
    # BUG-166: operator exit when a recovery job itself ended in terminal
    # unknown_outcome/failed/aborted/cancelled and still holds recovery_pending
    # (for example after recovery_phase_timeout or a Creo restart), so
    # abandon_stalled_recovery (pre-worker only) and ack_failure (requires no
    # recovery_pending) cannot fire. Metadata-only: clears recovery_pending,
    # never advances revision or modifies disk files, and records
    # disk_state_verified=false / session_state_verified=false.
    rec_job_id = model.get("recovery_pending")
    rec_job_status = _job_status(rec_job_id) if rec_job_id else None
    has_saved_file = bool(model.get("part_file"))
    baseline_ok = (not has_saved_file) or (baseline.get("verified") is True)
    unknown_rec_eligible = bool(
        rec_job_id
        and rec_job_status in ("failed", "unknown_outcome", "aborted", "cancelled")
        and baseline_ok
    )
    states["abandon_unknown_recovery"] = {
        "available": bool(stopped and unknown_rec_eligible),
        "reason": (
            "Previous runner/worker is active or cannot be proven stopped"
            if not stopped
            else "No recovery_pending reservation is held on this model"
            if not rec_job_id
            else f"Recovery job {rec_job_id} has status {rec_job_status!r}; wait until it reaches "
            "a terminal failed/unknown_outcome/aborted/cancelled status"
            if rec_job_status not in ("failed", "unknown_outcome", "aborted", "cancelled")
            else "Saved baseline checkpoint hash is missing or does not match; inspect the file "
            "before releasing recovery_pending"
            if not baseline_ok
            else "Explicit apply with confirm_unknown_recovery=true, matching evidence and an "
            "idempotency key required; clears recovery_pending without advancing revision or "
            "modifying files (disk_state_verified=false)"
        ),
        "recovery_job_id": rec_job_id,
        "recovery_job_status": rec_job_status,
        "baseline_hash_verified": baseline.get("verified") if has_saved_file else None,
    }
    panel_job_done_or_dead = guard.get("status") in terminal or (
        guard.get("owners_recorded") is True and guard.get("owners_stopped") is True
    )
    states["confirm_panel_closed"] = {
        "available": bool(
            guard.get("active")
            and guard.get("readable")
            and guard.get("mine")
            and panel_job_done_or_dead
        ),
        "reason": (
            "No resident panel guard holds the Creo session"
            if not guard.get("active")
            else "The panel guard cannot be read; a tool cannot retire it"
            if not guard.get("readable")
            else f"The active panel guard belongs to model {guard.get('model_id')!r}; confirm "
            "the panel on that model"
            if not guard.get("mine")
            else "The panel job has not reached a terminal status, so the dialog may still be "
            "driven; retry after the job ends"
            if not panel_job_done_or_dead
            else "Explicit apply with confirm_panel_closed=true, matching evidence, and all "
            "recorded owners stopped (job still non-terminal; cancel/reconcile pending_job "
            "afterwards if needed)"
            if guard.get("status") not in terminal
            else "Explicit apply with confirm_panel_closed=true, matching evidence and an "
            "idempotency key required"
        ),
    }
    return states


def _native_request(model: dict, choice: dict, budget_seconds: int | None = None) -> dict:
    # Reference-first view: a split registry record sends aliases/inspection
    # as controlled references; a legacy inline record keeps its payload
    # (BUG-077).
    view = dict(model)
    for key in model_registry.DETAIL_KEYS:
        if f"{key}_ref" in view:
            view.pop(key, None)
    return {
        "new": False,
        "model": view,
        "operations": [],
        "readonly": True,
        "template_file": "",
        "components": {},
        "reconciliation": choice,
        # BUG-157/BUG-166: assembly dependencies are owned when they live under
        # the managed models root; the phase budget adapts to edge count or an
        # explicit per-call budget_seconds and is clamped by the executor.
        "managed_root": str(bridge.ROOT / "models"),
        "recovery_phase_seconds": recovery_phase_seconds(model, budget_seconds),
    }


def _native(directory: Path, manifest: dict) -> dict:
    manifest["worker_started"] = False
    exe = bridge.build_native()
    manifest.update(stage="reconciling_native_model", status="running")
    bridge.write_json(directory / "job.json", manifest, durable=True)
    # BUG-157: the executor owns the recovery phase budget; this wrapper must
    # not terminate a healthy worker before that budget expires.
    timeout = bridge.utility_worker_timeout_seconds(default_seconds=WORKER_SECONDS)
    try:
        phase = int(bridge.read_json(directory / "request.json").get("recovery_phase_seconds", 0))
    except (OSError, ValueError, TypeError):
        phase = 0
    if phase > 0:
        timeout = max(timeout, phase + RECOVERY_PHASE_MARGIN_SECONDS)
    with (directory / "worker.log").open("wb") as log:
        manifest["worker_started"] = True
        bridge.write_json(directory / "job.json", manifest, durable=True)
        proc = subprocess.run(
            [str(exe), "generic", str(directory)],
            cwd=directory,
            env=bridge.native_environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            creationflags=bridge.HIDDEN,
        )
    result = _read(directory / "native_result.json")
    if result:
        inspection_refs.split_result(result, directory)
        manifest["result"] = result
        warnings = inspection_refs.warnings_of(result)
        if warnings:
            manifest["inspection_warnings"] = warnings
    if (
        not result
        or result.get("delivery_complete") is not True
        or result.get("disconnect_code") != 0
    ):
        checkpoint = _read(directory / "native_checkpoint.json") or {}
        stage = (result or {}).get("completion_stage") or checkpoint.get("completion_stage")
        budget = (result or {}).get("phase_budget_seconds") or checkpoint.get(
            "phase_budget_seconds"
        )
        if stage == "recovery_phase_timeout":
            budget_text = f" ({budget} s)" if budget is not None else ""
            raise RuntimeError(
                f"Recovery outcome is unconfirmed (recovery_phase_timeout{budget_text}); "
                "reservation retained; retry restore_baseline with verify_mode='identity' or "
                "a larger budget_seconds (up to 1800), or release recovery_pending with "
                "abandon_unknown_recovery"
            )
        raise RuntimeError(
            "Recovery outcome is unconfirmed; reservation retained; inspect native checkpoint"
        )
    if proc.returncode != 0 or not result.get("success"):
        raise RuntimeError(result.get("message", "Native recovery failed; reservation retained"))
    return result


def _live(model: dict, budget_seconds: int | None = None) -> dict:
    with bridge.toolkit_lock(operation="reconciliation_preflight", model_id=model["model_id"]):
        job_id = uuid.uuid4().hex
        directory = bridge.job_path(job_id)
        (directory / "output").mkdir(parents=True)
        manifest = {
            "job_id": job_id,
            "kind": "reconciliation_preflight",
            "model_id": model["model_id"],
            "status": "running",
            "created_at": bridge.now(),
        }
        bridge.write_json(
            directory / "request.json",
            _native_request(model, {"action": "inspect"}, budget_seconds=budget_seconds),
        )
        try:
            result = _native(directory, manifest)
            manifest.update(status="succeeded", result=result)
            live = dict(result["live"])
            warnings = inspection_refs.warnings_of(result)
            if warnings:
                live["inspection_warnings"] = warnings
            return live
        except Exception as error:
            manifest.update(status="failed", message=str(error))
            return {"confirmed": False, "reason": str(error)}
        finally:
            manifest["finished_at"] = bridge.now()
            bridge.write_json(directory / "job.json", manifest)


def inspect(model_id: str, live: bool = False, budget_seconds: int | None = None) -> dict:
    snapshot = _snapshot(model_id)
    phase_budget = recovery_phase_seconds(snapshot["model"], budget_seconds)
    realtime = _live(snapshot["model"], budget_seconds=budget_seconds) if live else None
    # A model/worker may have changed while a live query held the channel.
    if _binding(snapshot) != _binding(_snapshot(model_id)):
        raise ValueError("Evidence changed during preflight; inspect again")
    token = uuid.uuid4().hex
    record = {"snapshot": snapshot, "live": realtime, "created": time.time(), "token": token}
    directory = _directory(model_id)
    bridge.write_json(directory / f"evidence-{token}.json", record)
    model = snapshot["model"]
    candidate = snapshot["candidate"]
    if candidate and (candidate.get("inspection") or candidate.get("inspection_ref")):
        candidate = {
            **{
                key: value
                for key, value in candidate.items()
                if key not in ("inspection", "inspection_ref", "aliases")
            },
            "inspection": inspection_refs.summary_of(candidate),
        }
    visible_live = realtime
    if realtime and (realtime.get("inspection") or realtime.get("inspection_ref")):
        # The visible copy is a summary; the evidence record keeps the full
        # payload (or its controlled reference) for a later apply.
        visible_live = {
            **realtime,
            "inspection_summary": inspection_refs.summary_of(realtime),
        }
        visible_live.pop("inspection", None)
    return {
        "model_id": model_id,
        "status": model["status"],
        "revision": model["revision"],
        "pending_job": model.get("pending_job"),
        "recovery_pending": model.get("recovery_pending"),
        "original_job_id": model.get("pending_job") or model.get("last_job"),
        "baseline": snapshot["baseline"],
        "candidate": candidate,
        "owners": snapshot["owners"],
        "stalled_recovery": snapshot.get("stalled_recovery"),
        "recovery_wait": _recovery_wait(snapshot),
        # BUG-149: a read-only reservation has its own one-call exit; every
        # action in ``actions`` requires evidence about a mutation that this
        # kind of job can never have made.
        "readonly_pending": _readonly_pending(model),
        "live": visible_live,
        "actions": _actions(snapshot, realtime),
        # BUG-120/D4.4: a resident panel that may still be open holds the whole Creo
        # session, so the state is reported here as well as in the action list.
        "panel_session_guard": panel_session_guard.summary(bridge.ROOT),
        "evidence_token": token,
        "evidence_at": bridge.now(),
        "expires_in_seconds": TOKEN_SECONDS,
        "resolution": model.get("reconciliation"),
        "automatic_replay_allowed": False,
        "budgets": {
            "snapshot_seconds": SNAPSHOT_SECONDS,
            "file_hash_seconds": HASH_SECONDS,
            # BUG-157/BUG-166: native recovery phase budget adapts to edge count
            # or an explicit per-call budget_seconds and matches _native().
            "native_phase_seconds": phase_budget,
            "disconnect_seconds": 20,
            "outer_seconds": max(WORKER_SECONDS, phase_budget + RECOVERY_PHASE_MARGIN_SECONDS),
        },
    }


def _journal(model_id: str, key: str) -> Path:
    return _directory(model_id) / f"intent-{digest(key)}.json"


def _finish(record: dict) -> dict:
    """Materialize a durable commit; never invoke Toolkit or overwrite later edits."""
    model = general.model_info(record["model_id"])
    after = record["model_after"]
    if record.get("kind") in ("ack_no_mutation", "ack_failure"):
        # Metadata-only transaction: a later revision means someone else edited
        # the model in between, so the acknowledgement must not overwrite it.
        if model.get("revision") != after.get("revision"):
            raise ValueError("Model revision changed after the acknowledgement; inspect again")
        model_registry.write_model(general.model_path(record["model_id"]), after)
        return record["job_after"]
    if model.get("recovery_pending") == record["job_id"]:
        if (
            identity(bridge.job_path(record["job_id"]) / "native_result.json")
            != record["result_identity"]
        ):
            raise ValueError("Committed native evidence changed; keep recovery protection")
        source = after["reconciliation"].get("source_identity")
        if source and identity(Path(source["path"])) != source:
            raise ValueError("Committed saved model changed; keep recovery protection")
        model_registry.write_model(general.model_path(record["model_id"]), after)
    elif (model.get("reconciliation") or {}).get("recovery_id") != record["job_id"]:
        raise ValueError("Committed recovery conflicts with current registry; preserve audit")
    return record["job_after"]


def resume_committed(job_id: str) -> dict | None:
    """Polling may finish a committed metadata transaction, never native execution."""
    manifest = bridge.read_json(bridge.job_path(job_id) / "job.json")
    if (
        manifest.get("kind") != "reconciliation"
        or manifest.get("status") == "succeeded"
        or not manifest.get("model_id")
        or not manifest.get("idempotency_key")
    ):
        return None
    file = _journal(manifest["model_id"], manifest["idempotency_key"])
    record = _read(file)
    if not record or record.get("state") != "committed":
        return None
    try:
        with bridge.toolkit_lock(
            operation="finish_reconciliation_commit", job_id=job_id, model_id=manifest["model_id"]
        ):
            terminal = _finish(record)
    except bridge.ToolkitBusy:
        return {
            **manifest,
            "commit_pending": True,
            "message": "Durable recovery commit awaits metadata materialization; poll this job",
        }
    except (OSError, ValueError) as error:
        return {
            **manifest,
            "status": "unknown_outcome",
            "commit_pending": True,
            "recovery_required": True,
            "message": str(error),
        }
    bridge.write_json(bridge.job_path(job_id) / "job.json", terminal, durable=True)
    return terminal


def _validate_evidence(
    model_id: str, token: str, revision: int, pending: str | None, action: str
) -> dict:
    if not bridge.JOB_ID.fullmatch(token):
        raise ValueError("Invalid evidence_token")
    record = _read(_directory(model_id) / f"evidence-{token}.json")
    if not record or time.time() - record["created"] > TOKEN_SECONDS:
        raise ValueError("Evidence token is missing or expired; inspect again")
    current = general.model_info(model_id)
    if current.get("recovery_pending") and current.get("recovery_pending") != record["snapshot"][
        "model"
    ].get("recovery_pending"):
        raise bridge.ToolkitBusy(
            holder={
                "job_id": current["recovery_pending"],
                "model_id": model_id,
                "operation": "reconcile_model",
            }
        )
    snapshot = _snapshot(model_id)
    model = snapshot["model"]
    if model["revision"] != revision:
        raise ValueError(
            f"Stale expected_revision: model revision is {model['revision']}, "
            f"expected {revision}; inspect again"
        )
    if model.get("pending_job") != pending:
        raise ValueError(
            "Stale expected_pending_job_id: model pending_job is "
            f"{model.get('pending_job')!r}, expected {pending!r}; inspect again"
        )
    if _binding(snapshot) != _binding(record["snapshot"]):
        raise ValueError("Stale evidence: registry, files, deployment or process identity changed")
    action_state = _actions(snapshot, record["live"])[action]
    if not action_state["available"]:
        raise ValueError(action_state["reason"])
    return record


def _ack_model_after(
    current: dict,
    job_id: str,
    record: dict,
    idempotency_key: str,
    *,
    action: str = "ack_no_mutation",
    prior_job_status: str | None = None,
    outcome_uncertain: bool = False,
) -> dict:
    """Registry-only transition from failed to ready with an audit block."""
    acknowledged_at = bridge.now()
    prior_job = current.get("pending_job") or current.get("last_job")
    baseline = record["snapshot"].get("baseline") or {}
    audit = {
        "recovery_id": job_id,
        "action": action,
        "original_job_id": prior_job,
        "prior_status": current.get("status"),
        "prior_rollback_status": current.get("rollback_status"),
        "evidence_token": record.get("token"),
        "idempotency_key": idempotency_key,
        "checkpoint_identity": baseline.get("identity"),
        "original_plan_completion_confirmed": False,
        "source_identity": None,
        "acknowledged_at": acknowledged_at,
        "resolved_at": acknowledged_at,
    }
    if action == "ack_failure":
        # BUG-110: state plainly what was and was not verified. The acknowledgement
        # accepts the failure; it does not claim the disk or component state.
        audit.update(
            prior_job_status=prior_job_status,
            outcome_uncertain=outcome_uncertain,
            disk_state_verified=False,
            component_ownership_preserved=True,
        )
    return {
        **current,
        "status": "ready",
        "pending_job": None,
        "recovery_pending": None,
        "updated_at": acknowledged_at,
        "reconciliation": audit,
    }


def _retire_panel_guard(model_id: str, record: dict, idempotency_key: str) -> dict:
    """Release the session guard after a human confirmed the panel is closed.

    The evidence names the guard's own job, nonce and profile plus the reconcile
    token that was current when the operator looked, so a later reader can tell which
    guard was retired and on whose word. The model's unknown outcome is untouched.
    """
    guard = panel_session_guard.inspect(bridge.ROOT)
    if not isinstance(guard, dict) or guard.get("status") != "active":
        raise ValueError(
            "No active resident panel guard to retire; nothing was changed. The Toolkit "
            "channel is already usable again."
        )
    if guard.get("model_id") != model_id:
        raise ValueError(
            f"The active panel guard belongs to model {guard.get('model_id')!r}, not {model_id!r}; "
            "confirm the panel on the model whose job opened it"
        )
    guard_state = _panel_guard_state(record["snapshot"]["model"], record["snapshot"].get("owners"))
    try:
        retired = panel_session_guard.retire(
            guard["job_id"],
            reason="a human confirmed the resident panel is closed",
            evidence={
                "ui_closed_confirmed": True,
                "operator_confirmed": True,
                "evidence_token": record.get("token"),
                "idempotency_key": idempotency_key,
                "confirmed_via": "creo_reconcile_model.confirm_panel_closed",
                "guard_nonce": guard.get("nonce"),
                "guard_profile_id": guard.get("profile_id"),
                "guard_model_id": guard.get("model_id"),
                "job_status_at_confirm": guard_state.get("status"),
                "owners_stopped": guard_state.get("owners_stopped"),
            },
            root=bridge.ROOT,
        )
    except panel_session_guard.PanelSessionLocked as exc:
        raise ValueError(str(exc)) from None
    model = record["snapshot"]["model"]
    return {
        "model_id": model_id,
        "action": "confirm_panel_closed",
        "panel_session_guard": {
            "state": "retired",
            "job_id": retired.get("job_id"),
            "profile_id": retired.get("profile_id"),
            "retired_at": retired.get("retired_at"),
        },
        "revision": model.get("revision"),
        "status": model.get("status"),
        "pending_job": model.get("pending_job"),
        "model_unchanged": True,
        "automatic_replay_allowed": False,
        "message": (
            "The panel guard is retired, so Toolkit entries are no longer refused. The model's "
            "own outcome was not touched: its status, revision and pending job are unchanged, so "
            "if it is still unknown_outcome finish it with its own reconciliation action after "
            "checking the geometry."
        ),
    }


def _abandon_stalled_intent(
    model_id: str, record: dict, idempotency_key: str, arguments: dict
) -> dict:
    """BUG-146: close one recovery intent that provably never started.

    Metadata only: it records the intent as failed, releases ``recovery_pending``
    and leaves ``pending_job``, the revision, the saved file and every session
    protection exactly as they were.

    The order is deliberate: the reservation is released before the job record is
    rewritten, so an interrupted call can only leave an orphan job record -- never
    a reservation pointing at a terminal job that would look "unproven" again.
    The idempotency journal is recorded last because this action has no external
    side effect to protect: both writes are re-verifiable from the model record,
    and a replayed key returns the recorded result.
    """
    snapshot = record["snapshot"]
    job_id = snapshot["model"].get("recovery_pending")
    stalled = snapshot.get("stalled_recovery") or {}
    if not job_id or not stalled.get("proven") or stalled.get("job_id") != job_id:
        raise ValueError("No provably stalled recovery intent is reserved; inspect again")
    directory = bridge.job_path(job_id)
    manifest = _read(directory / "job.json") or {}
    if manifest.get("model_id") != model_id:
        raise ValueError("Recovery job evidence is not bound to this model")
    model = general.model_info(model_id)
    if model.get("recovery_pending") != job_id:
        raise ValueError("Recovery reservation changed; inspect again")
    if model.get("revision") != snapshot["model"]["revision"]:
        raise ValueError("Model revision changed after inspection; inspect again")
    finished = bridge.now()
    journal = _journal(model_id, idempotency_key)
    released = {**model, "recovery_pending": None, "updated_at": finished}
    model_registry.write_model(general.model_path(model_id), released)
    terminal = {
        **manifest,
        "status": "failed",
        "stage": "intent_abandoned",
        "reason": "recovery_intent_never_started",
        "failure_phase": "before_native",
        "finished_at": finished,
        "recovery_pending_released": True,
        "abandoned_intent": stalled,
        "message": (
            "Recovery intent abandoned: it recorded no started worker and no native file, "
            f"its stage was {stalled.get('stage') or 'pre-worker'}, and every recorded process "
            f"identity is gone ({stalled.get('basis')}). The model, its saved file, revision, "
            "pending job and session protection were not touched"
        ),
    }
    bridge.write_json(directory / "job.json", terminal, durable=True)
    result = {
        "model_id": model_id,
        "action": "abandon_stalled_recovery",
        "job_id": job_id,
        "status": "failed",
        "stage": "intent_abandoned",
        "revision": released.get("revision"),
        "pending_job": released.get("pending_job"),
        "recovery_pending": None,
        "model_unchanged": True,
        "recovery_pending_released": True,
        "original_plan_replayed": False,
        "stalled_intent": stalled,
        "message": (
            "The stalled recovery intent is closed and recovery_pending is released. The "
            "original pending job and revision are unchanged, so the model still needs its own "
            "reconciliation action after inspecting the geometry"
        ),
    }
    bridge.write_json(
        journal,
        {
            "state": "committed",
            "action": "abandon_stalled_recovery",
            "model_id": model_id,
            "job_id": job_id,
            "arguments": arguments,
            "evidence": record,
            "model_after": released,
            "job_after": result,
            "created_at": finished,
        },
        durable=True,
    )
    return result


def _abandon_unknown_recovery(
    model_id: str, record: dict, idempotency_key: str, arguments: dict
) -> dict:
    """BUG-166: release recovery_pending after a terminal failed/unknown recovery job.

    Metadata-only operator exit when a previous recovery job itself reached a
    terminal unknown_outcome/failed/aborted/cancelled status (e.g. timeout or
    session restart) while all recorded owners are proven stopped. Clears
    ``recovery_pending`` and returns the model to ``ready`` when ``pending_job``
    is null, never advancing revision or touching files, and records explicit
    ``disk_state_verified=false`` and ``session_state_verified=false`` in the
    reconciliation audit block.
    """
    snapshot = record["snapshot"]
    job_id = snapshot["model"].get("recovery_pending")
    if not job_id:
        raise ValueError("No recovery_pending reservation is held on this model; inspect again")
    rec_status = _job_status(job_id)
    if rec_status not in ("failed", "unknown_outcome", "aborted", "cancelled"):
        raise ValueError(
            f"Recovery job {job_id} has status {rec_status!r}; cannot abandon until terminal"
        )
    baseline = snapshot.get("baseline") or {}
    has_saved_file = bool(snapshot["model"].get("part_file"))
    if has_saved_file and baseline.get("verified") is not True:
        raise ValueError("Baseline file hash is not verified; inspect the file before releasing")
    model = general.model_info(model_id)
    if model.get("recovery_pending") != job_id:
        raise ValueError("Recovery reservation changed; inspect again")
    if model.get("revision") != snapshot["model"]["revision"]:
        raise ValueError("Model revision changed after inspection; inspect again")
    finished = bridge.now()
    journal = _journal(model_id, idempotency_key)
    prior_status = model.get("status")
    next_status = (
        "ready"
        if model.get("pending_job") is None and prior_status in ("unknown_outcome", "ready")
        else prior_status
    )
    audit = {
        "action": "abandon_unknown_recovery",
        "abandoned_recovery_job_id": job_id,
        "prior_recovery_job_status": rec_status,
        "prior_model_status": prior_status,
        "baseline_hash_verified": baseline.get("verified") if has_saved_file else None,
        "disk_state_verified": False,
        "session_state_verified": False,
        "idempotency_key": idempotency_key,
        "at": finished,
    }
    released = {
        **model,
        "status": next_status,
        "recovery_pending": None,
        "reconciliation": audit,
        "updated_at": finished,
    }
    model_registry.write_model(general.model_path(model_id), released)
    result = {
        "model_id": model_id,
        "action": "abandon_unknown_recovery",
        "job_id": job_id,
        "abandoned_recovery_job_id": job_id,
        "prior_recovery_job_status": rec_status,
        "status": next_status,
        "stage": "unknown_recovery_abandoned",
        "revision": released.get("revision"),
        "pending_job": released.get("pending_job"),
        "recovery_pending": None,
        "recovery_pending_released": True,
        "baseline_hash_verified": audit["baseline_hash_verified"],
        "disk_state_verified": False,
        "session_state_verified": False,
        "original_plan_replayed": False,
        "reconciliation": audit,
        "message": (
            "Released recovery_pending from terminal recovery job without advancing revision or "
            "modifying saved files (disk_state_verified=false, session_state_verified=false). "
            "Verify the model in Creo or run creo_refresh_model before making further edits."
        ),
    }
    bridge.write_json(
        journal,
        {
            "state": "committed",
            "action": "abandon_unknown_recovery",
            "model_id": model_id,
            "job_id": job_id,
            "arguments": arguments,
            "evidence": record,
            "model_after": released,
            "job_after": result,
            "created_at": finished,
        },
        durable=True,
    )
    return result


class RecoverySessionAbsent(ValueError):
    def __init__(self, model_id: str, action: str):
        self.payload = {
            "status": "rejected",
            "reason": "no_creo_session",
            "failure_phase": "before_native",
            "worker_started": False,
            "model_id": model_id,
            "action": action,
            "message": "No Creo process is running in this Windows session. "
            "Call creo_startup_status(retry=true), then inspect the model again.",
        }
        super().__init__(json.dumps(self.payload, ensure_ascii=False))


def _check_recovery_session(model_id: str, action: str) -> None:
    # An explicit session may be reachable beyond this process inventory.
    try:
        settings = creo_startup.Settings.load()
        if settings.selected:
            return
        observed = creo_startup.inventory(settings)
    except (ValueError, OSError, RuntimeError):
        return
    if observed.get("uncertain") is False and observed.get("processes") == []:
        raise RecoverySessionAbsent(model_id, action)


def apply(
    model_id: str,
    action: str,
    expected_revision: int,
    expected_pending_job_id: str | None,
    evidence_token: str,
    idempotency_key: str,
    confirm_zero_mutation: bool = False,
    confirm_failure_ack: bool = False,
    confirm_panel_closed: bool = False,
    confirm_stalled_recovery: bool = False,
    confirm_unknown_recovery: bool = False,
    budget_seconds: int | None = None,
    verify_mode: str | None = None,
) -> dict:
    if (
        action not in ACTIONS
        or isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 0
    ):
        raise ValueError("Valid action and nonnegative expected_revision are required")
    if action == "ack_no_mutation" and confirm_zero_mutation is not True:
        raise ValueError(
            "ack_no_mutation records that the failed job changed nothing; inspect the failed "
            "job and the checkpoint, then pass confirm_zero_mutation=true to acknowledge"
        )
    if action == "ack_failure" and confirm_failure_ack is not True:
        raise ValueError(
            "ack_failure records that the failed job is accepted as failed and makes the model "
            "ready again without touching its revision, files or components; inspect the failed "
            "job and the model in Creo, then pass confirm_failure_ack=true to acknowledge"
        )
    if action == "confirm_panel_closed" and confirm_panel_closed is not True:
        raise ValueError(
            "confirm_panel_closed releases the session-wide protection that a resident panel may "
            "still hold, which refuses every native job for every model until it is released. "
            "Check in Creo that no panel or dialog from this job is open (and that the old Creo "
            "session ended if you closed Creo), then pass confirm_panel_closed=true. It never "
            "changes the model's status, revision or pending job."
        )
    if action == "abandon_stalled_recovery" and confirm_stalled_recovery is not True:
        raise ValueError(
            "abandon_stalled_recovery closes one recovery intent that provably never started a "
            "runner or worker (no runner identity, worker_started=false, no native file, launcher "
            "process gone). Inspect the job and pass confirm_stalled_recovery=true to record it as "
            "failed and release recovery_pending; the model's pending job, revision, saved file and "
            "session protection are not touched."
        )
    if action == "abandon_unknown_recovery" and confirm_unknown_recovery is not True:
        raise ValueError(
            "abandon_unknown_recovery releases a recovery_pending reservation held by a terminal "
            "failed/unknown_outcome recovery job once all recorded owners are proven stopped. "
            "Inspect the baseline file and pass confirm_unknown_recovery=true; revision and files "
            "are not changed and disk_state_verified=false is recorded."
        )
    if verify_mode is not None:
        if verify_mode not in ("identity", "full"):
            raise ValueError("verify_mode must be 'identity' or 'full'")
        if action != "restore_baseline":
            raise ValueError("verify_mode is only valid with action='restore_baseline'")
    if budget_seconds is not None:
        # Validate budget bounds up front before touching locks or journals.
        recovery_phase_seconds(None, budget_seconds)
    if expected_pending_job_id is not None and (
        not isinstance(expected_pending_job_id, str)
        or not bridge.JOB_ID.fullmatch(expected_pending_job_id)
    ):
        # An empty or malformed value is a request defect, never model staleness.
        raise ValueError(
            "expected_pending_job_id must be the pending job id returned by inspect, "
            f"or null when inspect returned pending_job=null; received {expected_pending_job_id!r}"
        )
    if not isinstance(idempotency_key, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{8,80}", idempotency_key
    ):
        raise ValueError(
            "idempotency_key must contain 8–80 letters, digits, underscores or hyphens"
        )
    arguments = {
        "model_id": model_id,
        "action": action,
        "expected_revision": expected_revision,
        "expected_pending_job_id": expected_pending_job_id,
        "evidence_token": evidence_token,
    }
    if action == "ack_no_mutation":
        # Recorded so a replay with the flag omitted is recognized as the same
        # acknowledged request instead of starting a second transaction.
        arguments["confirm_zero_mutation"] = True
    if action == "ack_failure":
        arguments["confirm_failure_ack"] = True
    if action == "confirm_panel_closed":
        arguments["confirm_panel_closed"] = True
    if action == "abandon_stalled_recovery":
        arguments["confirm_stalled_recovery"] = True
    if action == "abandon_unknown_recovery":
        arguments["confirm_unknown_recovery"] = True
    if budget_seconds is not None:
        arguments["budget_seconds"] = budget_seconds
    if verify_mode is not None:
        arguments["verify_mode"] = verify_mode
    file = _journal(model_id, idempotency_key)
    # A duplicate query does not contend for Toolkit or repeat native work.
    existing = _read(file)
    if existing:
        if existing["arguments"] != arguments:
            raise ValueError("Idempotency key already belongs to another recovery request")
        if existing.get("state") == "committed" and action in (
            "abandon_stalled_recovery",
            "abandon_unknown_recovery",
        ):
            # A metadata-only acknowledgement records its own result; there is no
            # native commit to resume and no job to poll.
            return existing["job_after"]
        resume_committed(existing["job_id"])
        return bridge.get_job(existing["job_id"], "compact")
    if action == "confirm_panel_closed":
        # BUG-120/D4.4: metadata only, and deliberately outside the Toolkit lock —
        # the guard this action retires is exactly what refuses that lock. Nothing
        # about the model's status, revision or pending job changes here.
        record = _validate_evidence(
            model_id, evidence_token, expected_revision, expected_pending_job_id, action
        )
        return _retire_panel_guard(model_id, record, idempotency_key)
    if action == "abandon_stalled_recovery":
        # Metadata only: no worker, no Toolkit call and no channel admission, so
        # a stalled intent can be closed even while Creo itself is unusable.
        record = _validate_evidence(
            model_id, evidence_token, expected_revision, expected_pending_job_id, action
        )
        return _abandon_stalled_intent(model_id, record, idempotency_key, arguments)
    if action == "abandon_unknown_recovery":
        # BUG-166: metadata only, no worker or Toolkit call, so an operator can
        # release a dead recovery_pending reservation even after a Creo restart.
        record = _validate_evidence(
            model_id, evidence_token, expected_revision, expected_pending_job_id, action
        )
        return _abandon_unknown_recovery(model_id, record, idempotency_key, arguments)
    launch_error = None
    try:
        with bridge.toolkit_lock(operation="submit_reconciliation", model_id=model_id):
            # Check again under the one cross-process admission lock.
            if file.exists():
                raise bridge.ToolkitBusy(
                    "Recovery request was concurrently accepted; poll its recovery job"
                )
            holder = bridge.admission_holder()
            if holder:
                raise bridge.ToolkitBusy(holder=holder)
            record = _validate_evidence(
                model_id, evidence_token, expected_revision, expected_pending_job_id, action
            )
            if action in ("restore_baseline", "accept_live"):
                _check_recovery_session(model_id, action)
            model = record["snapshot"]["model"]
            job_id = uuid.uuid4().hex
            directory = bridge.job_path(job_id)
            (directory / "output").mkdir(parents=True)
            choice = {"action": action}
            # BUG-166: bind session_fingerprint only when accepting live
            # in-memory state (accept_live) or when fresh live preflight
            # evidence was just captured in the current session. Disk-backed
            # restore_baseline / accept_saved and uncommitted abandon_new must
            # remain executable after a Creo restart; native still verifies
            # owned origin, file SHA256 and geometry before mutating anything.
            session = (record.get("live") or {}).get("session_fingerprint")
            if not session and action == "accept_live":
                session = next(
                    (
                        owner["worker"].get("recorded", {}).get("session_fingerprint")
                        for owner in record["snapshot"]["owners"]
                        if owner["worker"].get("recorded", {}).get("session_fingerprint")
                    ),
                    None,
                )
            if session:
                choice["session_fingerprint"] = session
            if action == "restore_baseline":
                choice.update(source_file=model["part_file"])
                choice.update(inspection_refs.request_field(model, "source_inspection"))
                # BUG-157/BUG-166: default to fast identity mode (name/type/
                # units/feature count/volume); callers may opt into full mode.
                choice["verify_mode"] = verify_mode or "identity"
            elif action == "accept_saved":
                candidate = record["snapshot"]["candidate"]
                choice.update(source_file=candidate["identity"]["path"])
                choice.update(inspection_refs.request_field(candidate, "source_inspection"))
                # The accepted candidate's aliases may be a controlled reference
                # (split job result) or a legacy inline payload; exactly one
                # form travels to the executor (BUG-077).
                model = {**model}
                model.pop("aliases", None)
                model.pop("aliases_ref", None)
                if candidate.get("aliases_ref"):
                    model["aliases_ref"] = candidate["aliases_ref"]
                elif candidate.get("aliases"):
                    model["aliases"] = candidate["aliases"]
            elif action == "accept_live":
                choice.update(inspection_refs.request_field(record["live"], "live_inspection"))
            manifest = {
                "job_id": job_id,
                "recovery_id": job_id,
                "kind": "reconciliation",
                "model_id": model_id,
                "status": "queued",
                "action": action,
                "idempotency_key": idempotency_key,
                "created_at": bridge.now(),
                "stage": "intent_persisted",
                "worker_started": False,
                # BUG-146: the runner writes runner_identity as its first durable
                # action. If it never does, this launcher identity is what proves
                # the intent cannot still be executing (PID + creation time).
                "launched_by": process_identity(os.getpid()),
                "revision": model["revision"],
                "message": "Recovery accepted; poll this job_id; original plan will not be replayed",
            }
            if action in ("ack_no_mutation", "ack_failure"):
                # Metadata transaction only: no worker, no Toolkit, no file
                # write. The journal commit is durable before the registry is
                # updated so polling can finish an interrupted acknowledgement.
                current = general.model_info(model_id)
                expected_statuses = (
                    ("failed",) if action == "ack_no_mutation" else TERMINAL_FAILURE_STATUSES
                )
                if (
                    current.get("revision") != model["revision"]
                    or current.get("status") not in expected_statuses
                ):
                    raise ValueError("Model changed while acknowledging the failure; inspect again")
                prior_job_id = current.get("pending_job") or current.get("last_job")
                prior_job_status = None
                if prior_job_id:
                    try:
                        prior_job_status = bridge.get_job(prior_job_id, "compact").get("status")
                    except (OSError, ValueError):
                        prior_job_status = None
                if action == "ack_failure" and prior_job_status not in TERMINAL_FAILURE_STATUSES:
                    raise ValueError(
                        "Last job is not a terminal failure; inspect the model before acknowledging"
                    )
                after = _ack_model_after(
                    current,
                    job_id,
                    record,
                    idempotency_key,
                    action=action,
                    prior_job_status=prior_job_status,
                    outcome_uncertain=prior_job_status == "unknown_outcome",
                )
                acknowledged_at = after["reconciliation"]["resolved_at"]
                manifest.update(
                    status="succeeded",
                    stage=(
                        "metadata_acknowledged"
                        if action == "ack_no_mutation"
                        else "failure_acknowledged"
                    ),
                    revision=after["revision"],
                    finished_at=acknowledged_at,
                    message=(
                        "Zero-mutation acknowledgement recorded; no worker started and no model "
                        "file was touched"
                        if action == "ack_no_mutation"
                        else "Failure acknowledgement recorded; no worker started, and the "
                        "revision, model file and component bindings were left untouched"
                    ),
                    recovery={
                        "prior_status": current.get("status"),
                        "prior_job_id": prior_job_id,
                        "prior_job_status": prior_job_status,
                        "evidence_token": evidence_token,
                        "acknowledged_at": acknowledged_at,
                    },
                )
                intent = {
                    "state": "committed",
                    "kind": action,
                    "model_id": model_id,
                    "job_id": job_id,
                    "arguments": arguments,
                    "evidence": record,
                    "model_after": after,
                    "job_after": manifest,
                    "created_at": acknowledged_at,
                }
                bridge.write_json(
                    directory / "job.json",
                    {**manifest, "status": "running", "stage": "metadata_acknowledging"},
                    durable=True,
                )
                bridge.write_json(file, intent, durable=True)
                model_registry.write_model(general.model_path(model_id), after)
                bridge.write_json(directory / "job.json", manifest, durable=True)
                return manifest
            request = _native_request(model, choice, budget_seconds=budget_seconds)
            intent = {
                "state": "intent",
                "model_id": model_id,
                "job_id": job_id,
                "arguments": arguments,
                "evidence": record,
                "created_at": bridge.now(),
            }
            bridge.write_json(directory / "request.json", request, durable=True)
            bridge.write_json(directory / "job.json", manifest, durable=True)
            bridge.write_json(file, intent, durable=True)
            reserved = general.model_info(model_id)
            reserved["recovery_pending"] = job_id  # Original pending_job remains unchanged.
            model_registry.write_model(general.model_path(model_id), reserved)
            try:
                with (directory / "runner.log").open("ab") as log:
                    process, detached_from_job = bridge.spawn_detached_runner(
                        [sys.executable, str(bridge.ROOT / "bridge.py"), "run-job", job_id],
                        cwd=bridge.ROOT,
                        log_file=log,
                        popen=subprocess.Popen,
                    )
                manifest["runner_detached_from_job"] = detached_from_job
                if process is not None and isinstance(getattr(process, "pid", None), int):
                    manifest["runner_pid"] = process.pid
                bridge.write_json(directory / "job.json", manifest, durable=True)
            except Exception as error:
                _record_failure(
                    job_id,
                    manifest,
                    file,
                    RecoveryRefused("runner_start_failed", str(error)),
                    locked=True,
                )
                launch_error = error
            if launch_error is None:
                bridge.write_channel_claim(
                    job_id,
                    model_id=model_id,
                    operation="reconcile_model",
                    runner_pid=process.pid,
                )
                return manifest
    except Exception as error:
        if launch_error is None:
            raise
        manifest["channel_finalization_error"] = str(error)
    bridge.write_json(directory / "job.json", manifest, durable=True)
    raise launch_error


def run(job_id: str, manifest: dict) -> None:
    directory = bridge.job_path(job_id)
    file = _journal(manifest["model_id"], manifest["idempotency_key"])
    failure_recorded = False
    try:
        with bridge.toolkit_lock(
            wait_seconds=RUNNER_CHANNEL_WAIT_SECONDS,
            operation="reconcile_model",
            job_id=job_id,
            model_id=manifest["model_id"],
        ):
            try:
                intent = bridge.read_json(file)
                manifest = _run_locked(job_id, manifest, intent, file)
            except Exception as error:
                if not _record_failure(job_id, manifest, file, error, locked=True):
                    return
                failure_recorded = True
    except Exception as error:
        if failure_recorded:
            manifest["channel_finalization_error"] = str(error)
        elif not _record_failure(job_id, manifest, file, error, locked=False):
            return
    bridge.write_json(directory / "job.json", manifest, durable=True)


def _run_locked(job_id: str, manifest: dict, intent: dict, file: Path) -> dict:
    if intent["state"] == "committed":
        return _finish(intent)
    directory = bridge.job_path(job_id)
    # Revalidate every byte after admission, ignoring only our reservation.
    old = intent["evidence"]["snapshot"]
    bridge.build_native()
    current_model = general.model_info(manifest["model_id"])
    if current_model.get("recovery_pending") != job_id:
        raise RecoveryRefused(
            "reservation_changed", "Recovery reservation no longer belongs to this intent"
        )
    # Reconstruct using original job set, not this active runner.
    _check_execution(intent, current_model)
    result = _native(directory, manifest)
    _check_execution(intent, current_model)
    request = bridge.read_json(directory / "request.json")
    after = {**current_model}
    action = manifest["action"]
    source = None
    if action != "abandon_new":
        if not result.get("saved_file_reloaded_and_verified"):
            raise ValueError("Recovery did not verify a saved/reloaded native model")
        source = identity(owned_file(after, result["part_file"]))
        result["sha256"] = source["sha256"]
        if action == "restore_baseline" and source != old["baseline"]["identity"]:
            raise ValueError("Baseline file changed during recovery")
        after.update(
            status="ready",
            part_file=result["part_file"],
            part_sha256=source["sha256"],
            updated_at=bridge.now(),
        )
        # Registry keeps the summary plus the controlled reference; the aliases
        # arrive inline or as a reference and either form persists through
        # model_registry.write_model (BUG-076/077). BUG-157: identity recovery
        # never claims a full inspection, so the recorded baseline
        # inspection/aliases are preserved instead of being cleared.
        if result.get("verification") != "identity":
            after.pop("aliases", None)
            after.pop("aliases_ref", None)
            for key in ("aliases", "aliases_ref"):
                if key in result:
                    after[key] = result[key]
        after.update(
            {
                key: result[key]
                for key in ("inspection_ref", "inspection_summary", "inspection")
                if key in result
            }
        )
        if action != "restore_baseline":
            after["revision"] += 1
    else:
        after.update(status="abandoned", abandoned_at=bridge.now())
    after.update(
        pending_job=None,
        recovery_pending=None,
        reconciliation={
            "recovery_id": job_id,
            "action": action,
            "original_job_id": current_model.get("pending_job") or current_model.get("last_job"),
            "original_plan_completion_confirmed": False,
            "source_identity": source,
            "resolved_at": bridge.now(),
        },
    )
    manifest.update(
        status="succeeded",
        stage="reconciliation_committed",
        result=result,
        revision=after["revision"],
        finished_at=bridge.now(),
        message="Explicit recovery committed; original job history preserved",
    )
    # Recovery displayed or erased a model; keep the session record accurate
    # (FEAT-043). Informational only, never a condition of the commit.
    try:
        from creo_mechdog.session_models import record_session_change

        if action == "abandon_new":
            record_session_change(
                "creo_reconcile_model",
                f"abandon_new erased unproven copy {manifest.get('model_id')}",
                {"action": action, "model_id": manifest.get("model_id")},
            )
        else:
            record_session_change(
                "creo_reconcile_model",
                f"{action} displayed {manifest.get('model_id')}",
                {"action": action, "model_id": manifest.get("model_id")},
            )
    except (OSError, ValueError):
        pass
    intent.update(
        state="verified",
        model_after=after,
        job_after=manifest,
        result_identity=identity(directory / "native_result.json"),
        request=request,
    )
    bridge.write_json(file, intent, durable=True)
    intent["state"] = "committed"  # Durable decision precedes materialization.
    bridge.write_json(file, intent, durable=True)
    _finish(intent)
    return manifest


def _record_failure(
    job_id: str, manifest: dict, file: Path, error: Exception, *, locked: bool
) -> bool:
    # A committed decision is recoverable by polling; do not replace it with
    # a contradictory failure or release protection before materialization.
    persisted = _read(file) or {}
    if persisted.get("state") == "committed":
        return False
    started = bool(manifest.get("worker_started"))
    refused = isinstance(error, RecoveryRefused) and not started
    manifest.update(
        status="unknown_outcome" if started else "failed",
        stage="reconciliation_refused" if refused else "reconciliation_unconfirmed",
        reason=error.reason
        if isinstance(error, RecoveryRefused)
        else "native_outcome_unconfirmed"
        if started
        else "recovery_execution_failed",
        failure_phase="native_worker_started"
        if started
        else "before_native"
        if locked
        else "channel_admission",
        message=str(error),
        recovery_required=True,
        recovery_pending_released=False,
        finished_at=bridge.now(),
    )
    if started:
        manifest["message"] += (
            "; native worker dispatch began and may have started; "
            "recovery action outcome is not confirmed; protection retained"
        )
    elif locked:
        try:
            model = general.model_info(manifest["model_id"])
            if model.get("recovery_pending") == job_id:
                model["recovery_pending"] = None
                model_registry.write_model(general.model_path(manifest["model_id"]), model)
                manifest["recovery_pending_released"] = True
        except (OSError, ValueError) as cleanup_error:
            # The failed attempt never authorizes clearing another reservation,
            # and a failed cleanup must remain visible for operator inspection.
            manifest["recovery_pending_cleanup_error"] = str(cleanup_error)
    if isinstance(error, bridge.ToolkitBusy):
        manifest["busy"] = error.payload
    return True


def _check_execution(intent: dict, current: dict) -> None:
    """Re-read original evidence under the channel lock before any native work."""
    original = intent["evidence"]["snapshot"]
    normalized = {**current}
    normalized.pop("recovery_pending", None)
    expected = {**original["model"]}
    expected.pop("recovery_pending", None)
    # Compare control semantics, not storage form: a record whose inline
    # details were split into sidecars is the same record (BUG-077).
    if model_registry.semantic_view(normalized) != model_registry.semantic_view(expected):
        raise RecoveryRefused("model_changed", "Model changed after recovery admission")
    if _deployment(time.monotonic() + SNAPSHOT_SECONDS) != original["deployment"]:
        raise RecoveryRefused(
            "deployment_changed", "Deployment changed after recovery admission; inspect again"
        )
    if (
        digest({key: bridge.config().get(key) for key in ("creo_root", "creo_session_id")})
        != original["runtime_selection"]
    ):
        raise RecoveryRefused(
            "session_selection_changed", "Creo session selection changed after recovery admission"
        )
    for file in original["files"]:
        if identity(Path(file["path"])) != file:
            raise RecoveryRefused(
                "job_evidence_changed", "Original job evidence changed after admission"
            )
    verified_boot = _cached_boot_reader()
    for owner in original["owners"]:
        observed = _owners(owner["job_id"], verified_boot)
        if not observed["stopped"]:
            raise RecoveryRefused(
                "original_worker_unconfirmed",
                "Original worker is active or cannot be proven stopped",
            )
        if observed.get("stop_evidence") != owner.get("stop_evidence"):
            raise RecoveryRefused(
                "job_evidence_changed", "Original owner reboot evidence changed after admission"
            )
    for source in (original.get("baseline"), original.get("candidate")):
        if (
            source
            and source.get("identity")
            and identity(Path(source["identity"]["path"])) != source["identity"]
        ):
            raise RecoveryRefused(
                "source_changed", "Selected source changed after recovery admission"
            )


def reconcile(
    model_id: str,
    mode: str = "inspect",
    live: bool = False,
    action: str | None = None,
    expected_revision: int | None = None,
    expected_pending_job_id: str | None = None,
    evidence_token: str | None = None,
    idempotency_key: str | None = None,
    confirm_zero_mutation: bool = False,
    confirm_failure_ack: bool = False,
    confirm_panel_closed: bool = False,
    confirm_stalled_recovery: bool = False,
    confirm_unknown_recovery: bool = False,
    budget_seconds: int | None = None,
    verify_mode: str | None = None,
) -> dict:
    if mode == "inspect":
        if action is not None:
            raise ValueError("Selecting an action requires mode=apply")
        return inspect(model_id, live, budget_seconds=budget_seconds)
    if (
        mode != "apply"
        or action is None
        or expected_revision is None
        or evidence_token is None
        or idempotency_key is None
    ):
        raise ValueError(
            "apply requires action, expected_revision, evidence_token and idempotency_key; "
            "expected_pending_job_id must equal inspect's pending_job "
            "(null or omitted when inspect returned no pending job)"
        )
    return apply(
        model_id,
        action,
        expected_revision,
        expected_pending_job_id,
        evidence_token,
        idempotency_key,
        confirm_zero_mutation,
        confirm_failure_ack,
        confirm_panel_closed,
        confirm_stalled_recovery,
        confirm_unknown_recovery,
        budget_seconds,
        verify_mode,
    )
