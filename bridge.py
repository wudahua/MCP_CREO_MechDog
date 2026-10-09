"""Local, file-backed job runner for the Creo Toolkit worker. Never logs licenses."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from capabilities import REGISTERED_OPERATIONS, UNAVAILABLE_OPERATIONS

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
MODEL_NAME = re.compile(r"[a-z][a-z0-9_]{0,30}\Z")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def config() -> dict:
    if not (ROOT / "config.json").is_file():
        raise ValueError("Missing config.json: run setup.ps1, or copy config.example.json and set your installation paths")
    value = read_json(ROOT / "config.json")
    for key in ("creo_root", "vcvars64"):
        if any(c in value[key] for c in '\r\n"%'):
            raise ValueError(f"Invalid local path: {key}")
    return value


def job_path(job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("job_id must be the 32 hexadecimal characters returned by an MCP modeling tool")
    path = JOBS / job_id
    if path.is_symlink() or path.is_junction():
        raise ValueError("Job directories cannot be links")
    return path


def validate_spec(length: float, width: float, thickness: float, radius: float,
                  holes: list[dict], model_name: str | None = None) -> dict:
    values = {"length": length, "width": width, "thickness": thickness, "radius": radius}
    for name, v in values.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError(f"{name} must be a finite number in mm")
    if not 1 <= length <= 1000 or not 1 <= width <= 1000 or not 0.1 <= thickness <= 1000:
        raise ValueError("Supported size: length/width 1–1000 mm, thickness 0.1–1000 mm")
    if radius < 0 or radius >= min(length, width) / 2:
        raise ValueError("corner_radius must be >= 0 and less than half the shorter side")
    if model_name is not None and not MODEL_NAME.fullmatch(model_name):
        raise ValueError("model_name: lowercase letter followed by lowercase letters, digits or _, max 31 characters")
    if len(holes) > 50:
        raise ValueError("At most 50 through holes are supported")
    checked: list[dict] = []
    for i, h in enumerate(holes):
        if set(h) != {"x", "y", "diameter"}:
            raise ValueError(f"Hole {i + 1} requires exactly x, y and diameter")
        for v in h.values():
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"Hole {i + 1} contains a non-finite number")
        if h["diameter"] <= 0:
            raise ValueError(f"Hole {i + 1}: diameter must be positive")
        qx = abs(h["x"]) - (length / 2 - radius)
        qy = abs(h["y"]) - (width / 2 - radius)
        signed_distance = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
        if signed_distance + h["diameter"] / 2 >= -1e-4:
            raise ValueError(f"Hole {i + 1} intersects or touches the outer boundary")
        for j, prior in enumerate(checked):
            if math.hypot(h["x"] - prior["x"], h["y"] - prior["y"]) <= (h["diameter"] + prior["diameter"]) / 2 + 1e-4:
                raise ValueError(f"Holes {j + 1} and {i + 1} overlap or touch")
        checked.append({k: float(v) for k, v in h.items()})
    return {**{k: float(v) for k, v in values.items()}, "holes": checked, "model_name": model_name}


@contextmanager
def toolkit_lock(wait_seconds: float = 0):
    """Serialize all native calls across MCP clients and detached jobs."""
    lock = ROOT / "toolkit.lock"
    with lock.open("a+b") as f:
        f.seek(0, 2)
        if f.tell() == 0:
            f.write(b"0")
            f.flush()
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Creo Toolkit is busy with another task; query its job and try later")
                time.sleep(0.25)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


def native_environment() -> dict[str, str]:
    common = Path(config()["creo_root"]) / "Common Files"
    env = os.environ.copy()
    selected = config().get("creo_session_id")
    if selected:
        env["MECHDOG_CREO_SESSION_ID"] = selected
    env["PRO_COMM_MSG_EXE"] = str(common / "x86e_win64/obj/pro_comm_msg.exe")
    env["PATH"] = os.pathsep.join(str(common / p) for p in ("x86e_win64/lib", "x86e_win64/obj", "libs/dfor/lib")) + os.pathsep + env.get("PATH", "")
    # Child-process environment only; do not return or log the license value.
    psf = Path(config()["creo_root"]) / "Parametric/bin/parametric.psf"
    if not env.get("PTC_D_LICENSE_FILE") and psf.exists():
        for line in psf.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.search(r"PTC_D_LICENSE_FILE[^=]*=(.+)$", line, re.I)
            if match:
                env["PTC_D_LICENSE_FILE"] = match[1].strip()
                break
    return env


def check_environment() -> dict:
    c = config()
    root = Path(c["creo_root"])
    common = root / "Common Files"
    sdk = common / "protoolkit"
    files = {
        "creo_executable": root / "Parametric/bin/parametric.exe",
        "toolkit_headers": sdk / "includes/ProToolkit.h",
        "async_library": sdk / "x86e_win64/obj/ptasyncmd.lib",
        "toolkit_library": sdk / "x86e_win64/obj/protkmd_NU.lib",
        "communication_executable": common / "x86e_win64/obj/pro_comm_msg.exe",
        "metric_template": common / "templates/mmns_part_solid_abs.prt",
        "metric_assembly_template": common / "templates/mmns_asm_design_abs.asm",
        "compiler_setup": Path(c["vcvars64"]),
    }
    checks = {key: {"exists": p.is_file(), "path": str(p)} for key, p in files.items()}
    return {"platform": sys.platform, "creo_root": str(root), "checks": checks,
            "ready_to_build": all(p.is_file() for p in files.values()),
            "license_setting_present": bool(native_environment().get("PTC_D_LICENSE_FILE")),
            "license_usable": "unverified_here; only successful native feature creation proves it",
            "transport": "stdio", "supported_features": [op for op in REGISTERED_OPERATIONS if op not in UNAVAILABLE_OPERATIONS],
            "complete_creo_coverage": False}


def build_native() -> Path:
    """Caller holds toolkit_lock. Source hash invalidates the local build."""
    c = config()
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    exe = build / "creo_worker.exe"
    if not (ROOT / "native/constants.inc").is_file():
        if not check_environment()["ready_to_build"]:
            raise RuntimeError("Creo SDK, template or MSVC is missing; call creo_check_environment")
        with (build / "generate_constants.log").open("wb") as log:
            generated = subprocess.run([sys.executable, str(ROOT / "tools/generate_constants.py")],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=30, creationflags=HIDDEN)
        if generated.returncode:
            raise RuntimeError(f"SDK constant generation failed; see {build / 'generate_constants.log'}")
    digest = hashlib.sha256()
    for p in sorted(p for p in (ROOT / "native").rglob("*") if p.suffix in (".cpp", ".h", ".hpp", ".inc")):
        digest.update(p.read_bytes())
    digest.update(json.dumps(c, sort_keys=True).encode())
    fingerprint = digest.hexdigest()
    stamp = build / "source.sha256"
    if exe.exists() and stamp.exists() and stamp.read_text() == fingerprint:
        return exe
    if not check_environment()["ready_to_build"]:
        raise RuntimeError("Creo SDK, template or MSVC is missing; call creo_check_environment")
    sdk = Path(c["creo_root"]) / "Common Files/protoolkit"
    libs = " ".join(f'"{sdk / "x86e_win64/obj" / name}"' for name in ("protkmd_NU.lib", "ptasyncmd.lib", "ucore.lib", "udata.lib"))
    script = build / "build.cmd"
    script.write_text(f'''@echo off
setlocal
call "{c['vcvars64']}"
if errorlevel 1 exit /b 1
cl /nologo /MD /EHsc /std:c++17 /bigobj /W3 /DPRO_MACHINE=36 /DPRO_OS=4 /DPRO_USE_VAR_ARGS /I"{sdk / 'includes'}" /c "{ROOT / 'native/worker.cpp'}" /Fo"{build / 'worker.obj'}"
if errorlevel 1 exit /b 2
link /nologo /MACHINE:X64 /SUBSYSTEM:CONSOLE /OUT:"{exe}" "{build / 'worker.obj'}" {libs} kernel32.lib user32.lib wsock32.lib advapi32.lib mpr.lib winspool.lib netapi32.lib psapi.lib gdi32.lib shell32.lib comdlg32.lib ole32.lib ws2_32.lib
if errorlevel 1 exit /b 3
exit /b 0
''', encoding="utf-8")
    with (build / "build.log").open("wb") as log:
        result = subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=build, stdout=log, stderr=subprocess.STDOUT, timeout=120, creationflags=HIDDEN)
    if result.returncode:
        raise RuntimeError(f"Native build failed ({result.returncode}); see {build / 'build.log'}")
    stamp.write_text(fingerprint)
    constants = subprocess.run([str(exe), "constants"], env=native_environment(), capture_output=True, timeout=20, creationflags=HIDDEN)
    if constants.returncode == 0:
        (build / "constants.json").write_bytes(constants.stdout)
    return exe


def session_status() -> dict:
    with toolkit_lock():
        exe = build_native()
        result = subprocess.run([str(exe), "status"], cwd=ROOT / "build", env=native_environment(), capture_output=True, timeout=50, creationflags=HIDDEN)
    try:
        value = json.loads(result.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError(f"Toolkit worker failed without a result (exit {result.returncode}); check the Creo session and runtime libraries") from None
    value["worker_exit_code"] = result.returncode
    return value


def create_job(spec: dict) -> dict:
    JOBS.mkdir(exist_ok=True)
    job_id = uuid.uuid4().hex
    directory = job_path(job_id)
    directory.mkdir()
    output = directory / "output"
    output.mkdir()
    if len(str(output)) >= 230:
        raise ValueError("Project path is too long for this Creo Toolkit build")
    spec = dict(spec)
    spec["model_name"] = spec["model_name"] or f"ai_plate_{job_id[:12]}"
    manifest = {"job_id": job_id, "status": "queued", "created_at": now(), "spec": spec,
                "job_directory": str(directory), "output_directory": str(output),
                "message": "Call creo_get_job until succeeded, failed or unknown_outcome. Do not repeat create_plate to poll."}
    write_json(directory / "job.json", manifest)
    try:
        with (directory / "runner.log").open("ab") as log:
            subprocess.Popen([sys.executable, str(ROOT / "bridge.py"), "run-job", job_id], cwd=ROOT,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=HIDDEN, close_fds=True)
    except Exception as exc:
        manifest.update(status="failed", message=str(exc), finished_at=now())
        write_json(directory / "job.json", manifest)
        raise
    return manifest


def run_job(job_id: str) -> None:
    directory = job_path(job_id)
    manifest = read_json(directory / "job.json")
    if manifest.get("kind") == "generic":
        from generic_bridge import run_generic_job
        run_generic_job(job_id, manifest)
        return
    try:
        with toolkit_lock(wait_seconds=120):
            manifest.update(status="running", stage="building_worker", started_at=now(), runner_pid=os.getpid())
            write_json(directory / "job.json", manifest)
            exe = build_native()
            spec = validate_spec(**{k: manifest["spec"][k] for k in ("length", "width", "thickness", "radius", "holes", "model_name")})
            common = Path(config()["creo_root"]) / "Common Files"
            lines = [spec["model_name"], manifest["output_directory"], str(common / "templates/mmns_part_solid_abs.prt"),
                     " ".join(format(spec[k], ".17g") for k in ("length", "width", "thickness", "radius")), str(len(spec["holes"]))]
            lines.extend(" ".join(format(h[k], ".17g") for k in ("x", "y", "diameter")) for h in spec["holes"])
            (directory / "native_spec.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest.update(stage="creating_native_features")
            write_json(directory / "job.json", manifest)
            with (directory / "worker.log").open("wb") as log:
                proc = subprocess.run([str(exe), "create", str(directory)], cwd=directory, env=native_environment(),
                                      stdout=log, stderr=subprocess.STDOUT, timeout=config()["native_timeout_seconds"], creationflags=HIDDEN)
            result_path = directory / "native_result.json"
            if not result_path.exists():
                manifest.update(status="unknown_outcome", message=f"Worker exited {proc.returncode} without a result; inspect Creo and native.log before retrying")
            else:
                result = read_json(result_path)
                manifest["result"] = result
                if proc.returncode == 0 and result.get("success") and result.get("saved_file_reloaded_and_verified"):
                    part = Path(result["part_file"])
                    if part.parent.resolve() != (directory / "output").resolve() or not part.is_file():
                        raise RuntimeError("Native result references a missing or unexpected part file")
                    result["sha256"] = hashlib.sha256(part.read_bytes()).hexdigest()
                    result["preview_file"] = str(directory / "output/preview.jpg") if result["preview_code"] == 0 else None
                    manifest.update(status="succeeded", stage="verified", message="Native PRT saved, reloaded and verified; sketch/extrude/round/hole features are editable")
                else:
                    manifest.update(status="failed", message=f"Toolkit code {result['toolkit_code']}; inspect native.log. Partial new model may remain in Creo. Do not blindly retry.")
    except subprocess.TimeoutExpired:
        manifest.update(status="unknown_outcome", message="Native helper timed out and was stopped; Creo may contain a partial/new model. Inspect Creo before retrying.")
    except Exception as exc:
        manifest.update(status="failed", message=str(exc))
    manifest["finished_at"] = now()
    write_json(directory / "job.json", manifest)


def get_job(job_id: str) -> dict:
    directory = job_path(job_id)
    if not (directory / "job.json").exists():
        raise ValueError("Unknown job_id")
    manifest = read_json(directory / "job.json")
    native_log = directory / "native.log"
    if native_log.exists():
        tail = native_log.read_bytes()[-8000:].decode("utf-8", errors="replace")
        stages = re.findall(r"PHASE=([^\r\n]+)", tail)
        if stages and manifest["status"] == "running":
            manifest["stage"] = stages[-1]
        if manifest["status"] in ("failed", "unknown_outcome"):
            manifest["native_log_tail"] = tail[-4000:]
    if manifest["status"] in ("queued", "running"):
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(manifest["created_at"])).total_seconds()
        timeout = config().get("generic_timeout_seconds",600) if manifest.get("kind") == "generic" else config()["native_timeout_seconds"]
        if age > 120 + 120 + timeout + 30:
            manifest.update(status="unknown_outcome", message="Job exceeded its expected lifetime; inspect runner.log and Creo before retrying")
    return manifest


def list_jobs(limit: int = 10) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1–50")
    paths = sorted(JOBS.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [get_job(p.parent.name) for p in paths[:limit]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "status", "environment", "run-job"])
    parser.add_argument("job_id", nargs="?")
    args = parser.parse_args()
    if args.action == "run-job":
        run_job(args.job_id)
    elif args.action == "build":
        with toolkit_lock():
            print(build_native())
    else:
        print(json.dumps(session_status() if args.action == "status" else check_environment(), ensure_ascii=False, indent=2))
