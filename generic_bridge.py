"""Persistent owned models and composable general feature jobs."""
from __future__ import annotations
import hashlib
import json
import re
import shutil
from pathlib import Path
import subprocess
import sys
import uuid
import bridge
from schema import validate_operations,Assertions
from capabilities import require_available

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

def component_graph(source: dict, target_id: str, seen: set[str] | None=None) -> dict[str,dict]:
    """Check all assembly descendants before a native job is queued."""
    seen=set() if seen is None else seen
    sid=source['model_id']
    if sid==target_id: raise ValueError("Assembly containment cycle is not allowed")
    if sid in seen: return {}
    seen.add(sid)
    if source['status']!='ready' or source.get('pending_job'):
        raise ValueError("Every component source must be ready with no pending mutation")
    if not source.get('part_file') or not Path(source['part_file']).is_file():
        raise ValueError("Every component source needs a verified saved native file")
    result={sid:source}
    for alias in source.get('aliases',{}).values():
        child=alias.get('source_model_id')
        if child: result.update(component_graph(model_info(child),target_id,seen))
    return result

def submit(operations: list[dict], model_id: str | None=None, model_name: str | None=None,
           expected_revision: int | None=None, assertions: dict | None=None, readonly: bool=False,
           model_type: str="part") -> dict:
    operations=validate_operations(operations)
    require_available(operations)
    assertions=Assertions.model_validate(assertions or {}).model_dump(exclude_none=True)
    if readonly and any(op["op"] not in ("dump_tree","export","udf_inspect") for op in operations): raise ValueError("Read-only requests may only inspect/export")
    with bridge.toolkit_lock():
        new=model_id is None
        if new:
            if model_type not in ("part","sheetmetal","assembly","drawing"): raise ValueError("Unsupported model_type")
            if model_name is not None and not bridge.MODEL_NAME.fullmatch(model_name): raise ValueError("Invalid model_name")
            model_id=uuid.uuid4().hex
            path=model_path(model_id)
            model={"model_id":model_id,"model_name":model_name or f"ai_part_{model_id[:12]}",
                   "revision":0,"created_at":bridge.now(),"status":"new","aliases":{},"model_type":model_type,
                   "output_directory":str(path/"output"),"part_file":None}
            if len(model["output_directory"])>220: raise ValueError("Project path is too long for Creo Toolkit")
        else:
            path=model_path(model_id)
            model=model_info(model_id)
            if model.get("pending_job"): raise ValueError(f"Model has pending job {model['pending_job']}; poll it first")
            if model["status"]!="ready": raise ValueError("Model is not ready; inspect its last job before recovery")
            if expected_revision is None and not readonly: raise ValueError("Provide expected_revision from creo_inspect_model to prevent stale edits")
            if expected_revision is not None and expected_revision!=model["revision"]: raise ValueError(f"Stale revision: current model revision is {model['revision']}")
        actual_type=model.get("model_type","part")
        assembly_ops={"assemble_component","component_placement","component_constraints","remove_component"}
        for op in operations:
            if op['op'].startswith('drawing_') and actual_type!='drawing': raise ValueError("Drawing operations require an MCP drawing")
            if actual_type=='drawing' and not (op['op'].startswith('drawing_') or op['op'] in {'regenerate','save','export'}): raise ValueError("This operation requires a solid model")
            if op['op']=='export':
                if actual_type=='drawing' and op['format'] not in {'pdf','jpeg'}: raise ValueError("Drawing export supports PDF and JPEG")
                if actual_type!='drawing' and op['format']=='pdf': raise ValueError("PDF export requires a drawing")
            if op['op'] in assembly_ops and actual_type!="assembly": raise ValueError("Assembly operations require an MCP assembly model")
            if op['op'].startswith('sheetmetal_') and actual_type!="sheetmetal": raise ValueError("Sheetmetal operations require an MCP sheetmetal model")
            if actual_type=="assembly" and op['op'] not in assembly_ops|{"datum_plane","datum_axis","datum_csys","datum_points","set_parameters","set_relations","set_dimensions","regenerate","save","export","dump_tree","feature_tree"}: raise ValueError("This operation requires a part model")
        components={}
        for op in operations:
            if op['op'] in ("assemble_component","drawing_model"):
                source=model_info(op['source_model_id'])
                components.update(component_graph(source,model_id))
                if source.get('model_type') in ('assembly','drawing'):
                    raise ValueError("Nested assembly copying is not yet supported; insert owned part/sheetmetal models")
        duplicate=set(model["aliases"]).intersection(op["label"] for op in operations if "label" in op)
        if duplicate: raise ValueError(f"Feature labels already exist: {sorted(duplicate)}")
        # Initialize from a solid template. Native first-wall conversion creates
        # the sheetmetal body; the stock empty SMT body breaks attached walls.
        templates={"part":"mmns_part_solid_abs.prt","sheetmetal":"mmns_part_solid_abs.prt","assembly":"mmns_asm_design_abs.asm","drawing":"a4_drawing.drw"}
        template=Path(bridge.config()["creo_root"])/"Common Files/templates"/templates[actual_type]
        if not template.is_file(): raise ValueError(f"Missing local model template: {templates[actual_type]}")
        udf_files={}
        for index,op in enumerate(operations):
            if op['op'] in ('udf_inspect','udf_create'):
                source=Path(op['file_path']).expanduser()
                if not source.is_absolute() or not source.is_file() or not re.search(r'\.gph(?:\.\d+)?$',source.name,re.I):
                    raise ValueError('UDF file_path must be an absolute path to an existing .gph or .gph.N file')
                udf_files[index]=source.resolve()
        if new: (path/'output').mkdir(parents=True)
        job_id=uuid.uuid4().hex
        directory=bridge.job_path(job_id)
        directory.mkdir(parents=True)
        (directory/"output").mkdir()
        for index,source in udf_files.items():
            inputs=directory/'input'/str(index)
            inputs.mkdir(parents=True)
            snapshot=inputs/'library.gph'
            shutil.copyfile(source,snapshot)
            operations[index]['file_path']=str(snapshot)
        model["pending_job"]=job_id
        bridge.write_json(path/"model.json",model)
        request={"new":new,"model":model,"operations":operations,"readonly":readonly,"components":components,
                 "template_file":str(template),
                 "assertions":assertions or {}}
        manifest={"job_id":job_id,"kind":"generic","model_id":model_id,"status":"queued","readonly":readonly,
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
