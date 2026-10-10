"""Check the environment produced by vcvars64 before invoking cl/link."""
import os
from pathlib import Path
import shutil


def compiler_environment_errors(env: dict[str, str]) -> list[str]:
    errors = []
    for program in ("cl.exe", "link.exe"):
        if not shutil.which(program, path=env.get("PATH", "")):
            errors.append(f"{program} is unavailable after vcvars64; install MSVC x64 tools")
    include = [Path(p.strip('"')) for p in env.get("INCLUDE", "").split(";") if p]
    libraries = [Path(p.strip('"')) for p in env.get("LIB", "").split(";") if p]
    for filename, label in (("stdio.h", "Windows SDK UCRT headers"), ("windows.h", "Windows SDK UM headers")):
        if not any((directory / filename).is_file() for directory in include):
            errors.append(f"Missing {filename} in INCLUDE: {label} were not configured")
    for filename in ("ucrt.lib", "kernel32.lib"):
        if not any((directory / filename).is_file() for directory in libraries):
            errors.append(f"Missing {filename} in LIB: Windows SDK x64 libraries were not configured")
    if errors:
        errors.append("Check Visual Studio C++/Windows SDK installation and vcvars64 SDK discovery; blocked reg.exe/registry access can cause this even when vcvars64 exits 0. Ask the environment administrator to allow SDK discovery, or pass a reviewed local compiler environment wrapper via -VcVars64. Global security policy is not changed by this installer.")
    return errors


if __name__ == "__main__":
    problems = compiler_environment_errors(dict(os.environ))
    for problem in problems:
        print("COMPILER_PREFLIGHT: " + problem)
    if not problems:
        print("COMPILER_PREFLIGHT: MSVC, UCRT and Windows SDK headers/libraries found")
    raise SystemExit(4 if problems else 0)
