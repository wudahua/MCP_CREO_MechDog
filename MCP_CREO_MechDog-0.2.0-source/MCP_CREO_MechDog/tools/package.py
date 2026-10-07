"""Build the public MIT source release from an explicit allowlist."""
import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
NAME = "MCP_CREO_MechDog"


def source_files():
    names = ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "server.py", "bridge.py",
             "generic_bridge.py", "schema.py", "config.example.json", "client-config.example.json",
             "requirements.txt", "requirements.lock.txt", "setup.ps1", ".gitignore")
    files = [ROOT / name for name in names]
    for directory, extensions in {"native": {".cpp", ".hpp", ".h"}, "tools": {".py"},
                                  "tests": {".py"}, "examples": {".json"},
                                  "docs": {".md", ".json"}}.items():
        files.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in extensions and "__pycache__" not in p.parts)
    files.append(ROOT / "native/third_party/LICENSE.nlohmann-json")
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing source file or unexpected symlink: {path}")
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, help="Also copy public files into a new empty upload directory")
    args = parser.parse_args()
    files = source_files()
    if args.stage:
        stage = args.stage.resolve()
        if stage == ROOT or ROOT in stage.parents or stage in ROOT.parents:
            raise ValueError("Upload directory must be separate from the working project")
        if stage.exists() and (not stage.is_dir() or any(stage.iterdir())):
            raise ValueError("Upload directory must be new or empty; existing files are never deleted")
        stage.mkdir(parents=True, exist_ok=True)
        for source in files:
            destination = stage / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    archive = ROOT.parent / f"{NAME}-{VERSION}-source.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for source in files:
            output.write(source, f"{NAME}/" + source.relative_to(ROOT).as_posix())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print(f"Public source: {archive}; {len(files)} files; SHA256 {checksum}")
    if args.stage:
        print(f"GitHub upload directory: {args.stage.resolve()}")


if __name__ == "__main__":
    main()
