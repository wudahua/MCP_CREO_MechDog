"""Persistent owned models and composable general feature jobs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import bridge
from schema import validate_operations,Assertions

MODELS=bridge.ROOT / "models"

def model_path(model_id: str) -> Path:
    if not bridge.JOB_ID.fullmatch(model_id): raise ValueError("Invalid model_id")
    path=MODELS / model_id
    if path.is_symlink() or path.is_junction(): raise ValueError("Model directories cannot be links")
    return path

def model_info(model_id: str) -> dict:
    path=model_path(model_id)/"model.json"
    if not path.is_file(): raise ValueError("Unknown model_id; use creo_new_part or creo_execute_plan")
    return bridge.read_json(path)

def list_models(limit: int=10) -> dict:
    if not 1<=limit<=50: raise ValueError("limit must be 1–50")
    paths=sorted(MODELS.glob("*/model.json"),key=lambda p:p.stat().st_mtime,reverse=True)
    return {"models":[bridge.read_json(p) for p in paths[:limit]]}

def submit(operations: list[dict], model_id: str | None=None, model_name: str | None=None,
           expected_revision: int | None=None, assertions: dict | None=None, readonly: bool=False) -> dict:
    operations=validate_operations(operations)
    assertions=Assertions.model_validate(assertions or {}).model_dump(exclude_none=True)
    if readonly and any(op["op"] not in ("dump_tree","export") for op in operations): raise ValueError("Read-only requests may only inspect/export")
    with bridge.toolkit_lock():
        new=model_id is None
        if new:
            if model_name is not None and not bridge.MODEL_NAME.fullmatch(model_name): raise ValueError("Invalid model_name")
            model_id=uuid.uuid4().hex
            path=model_path(model_id)
            (path/"output").mkdir(parents=True)
            model={"model_id":model_id,"model_name":model_name or f"ai_part_{model_id[:12]}",
                   "revision":0,"created_at":bridge.now(),"status":"new","aliases":{},
                   "output_directory":str(path/"output"),"part_file":None}
            if len(model["output_directory"])>220: raise ValueError("Project path is too long for Creo Toolkit")
        else:
            path=model_path(model_id)
            model=model_info(model_id)
            if model.get("pending_job"): raise ValueError(f"Model has pending job {model['pending_job']}; poll it first")
            if model["status"]!="ready": raise ValueError("Model is not ready; inspect its last job before recovery")
            if expected_revision is None and not readonly: raise ValueError("Provide expected_revision from creo_inspect_model to prevent stale edits")
            if expected_revision is not None and expected_revision!=model["revision"]: raise ValueError(f"Stale revision: current model revision is {model['revision']}")
        duplicate=set(model["aliases"]).intersection(op["label"] for op in operations if "label" in op)
        if duplicate: raise ValueError(f"Feature labels already exist: {sorted(duplicate)}")
        job_id=uuid.uuid4().hex
        directory=bridge.job_path(job_id)
        directory.mkdir(parents=True)
        (directory/"output").mkdir()
        model["pending_job"]=job_id
        bridge.write_json(path/"model.json",model)
        request={"new":new,"model":model,"operations":operations,"readonly":readonly,
                 "template_file":str(Path(bridge.config()["creo_root"])/"Common Files/templates/mmns_part_solid_abs.prt"),
                 "assertions":assertions or {}}
        manifest={"job_id":job_id,"kind":"generic","model_id":model_id,"status":"queued",
                  "created_at":bridge.now(),"operations":operations,"job_directory":str(directory),
                  "output_directory":str(directory/"output"),"message":"Poll creo_get_job with this job_id; do not resubmit the operation"}
        bridge.write_json(directory/"request.json",request)
        bridge.write_json(directory/"job.json",manifest)
        try:
            with (directory/"runner.log").open("ab") as log:
                subprocess.Popen([sys.executable,str(bridge.ROOT/"bridge.py"),"run-job",job_id],cwd=bridge.ROOT,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=bridge.HIDDEN,close_fds=True)
        except Exception as exc:
            model.update(status="failed" if new else "ready",pending_job=None)
            bridge.write_json(path/"model.json",model)
            manifest.update(status="failed",message=str(exc),finished_at=bridge.now())
            bridge.write_json(directory/"job.json",manifest)
            raise
        return {**manifest,"model_name":model["model_name"],"revision":model["revision"]}

def run_generic_job(job_id: str, manifest: dict):
    directory=bridge.job_path(job_id)
    request=bridge.read_json(directory/"request.json")
    model=request["model"]
    path=model_path(model["model_id"])
    worker_started=False
    try:
        with bridge.toolkit_lock(wait_seconds=120):
            manifest.update(status="running",stage="building_worker",started_at=bridge.now())
            bridge.write_json(directory/"job.json",manifest)
            exe=bridge.build_native()
            manifest["stage"]="executing_feature_plan"
            bridge.write_json(directory/"job.json",manifest)
            with (directory/"worker.log").open("wb") as log:
                worker_started=True
                proc=subprocess.run([str(exe),"generic",str(directory)],cwd=directory,env=bridge.native_environment(),
                    stdout=log,stderr=subprocess.STDOUT,timeout=bridge.config().get("generic_timeout_seconds",600),creationflags=bridge.HIDDEN)
            result_file=directory/"native_result.json"
            if not result_file.exists():
                manifest.update(status="unknown_outcome",message=f"Native worker exited {proc.returncode} without a result; inspect Creo before retrying")
                model["status"]="unknown_outcome"
            else:
                result=bridge.read_json(result_file)
                manifest["result"]=result
                if proc.returncode==0 and result.get("success"):
                    if not request["readonly"] and not result.get("saved_file_reloaded_and_verified"): raise RuntimeError("Saved model was not verified")
                    part=Path(result["part_file"])
                    if part.parent.resolve()!=(path/"output").resolve() or not part.is_file(): raise RuntimeError("Unexpected native output file")
                    result["sha256"]=hashlib.sha256(part.read_bytes()).hexdigest()
                    if request["readonly"]:
                        model.update(status="ready",last_live_inspection=result["inspection"],last_query_at=bridge.now())
                    else:
                        model["revision"]+=1
                        model.update(status="ready",aliases=result["aliases"],inspection=result["inspection"],
                                     part_file=result["part_file"],updated_at=bridge.now(),last_job=job_id)
                    manifest.update(status="succeeded",stage="verified",message="General feature plan completed",revision=model["revision"])
                else:
                    model["status"]="ready" if (request["readonly"] or result.get("rollback_succeeded")) and model.get("part_file") else "failed"
                    manifest.update(status="failed",message=result.get("message",f"Toolkit code {result.get('toolkit_code')}"))
    except subprocess.TimeoutExpired:
        manifest.update(status="unknown_outcome",message="Native worker timed out; inspect Creo and the model before retrying")
        model["status"]="unknown_outcome"
    except Exception as exc:
        manifest.update(status="unknown_outcome" if worker_started else "failed",message=str(exc))
        model["status"]="unknown_outcome" if worker_started else ("ready" if model.get("part_file") else "failed")
    model["pending_job"]=None
    model["last_job"]=job_id
    bridge.write_json(path/"model.json",model)
    manifest["finished_at"]=bridge.now()
    bridge.write_json(directory/"job.json",manifest)
