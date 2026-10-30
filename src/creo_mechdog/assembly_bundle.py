"""Copy an owned assembly's verified native snapshots into one job artifact."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

MAX_FILES = 128
MAX_BYTES = 512 * 1024 * 1024
_NATIVE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,30}\.(?:asm|prt)$", re.I)
_IDENTITY_NAME = re.compile(r"[a-z][a-z0-9_]{0,30}")
_COMPONENT_OP = "assemble_component"


def _safe_directory(path: Path) -> Path:
    if path.is_symlink() or path.is_junction():
        raise ValueError("linked bundle/source directory is refused")
    return path.resolve(strict=True)


def _latest(source: Path, name: str) -> Path | None:
    versions: list[tuple[int, Path]] = []
    for candidate in source.glob(name + ".*"):
        # Windows glob matching is case-insensitive; the recorded identity names
        # the file exactly, so a differently cased file is a different file.
        if candidate.name[: len(name) + 1] != name + ".":
            continue
        if candidate.is_symlink() or candidate.is_junction() or not candidate.is_file():
            continue
        suffix = candidate.name[len(name) + 1 :]
        if suffix.isdigit():
            versions.append((int(suffix), candidate))
    return max(versions, default=(0, None))[1]


def _snapshot_identities(model: dict) -> dict[int, str]:
    """feature_id -> the copy name recorded when the component was assembled.

    ``assemble_component`` copies the source under one generated name
    (``c_<job16>_<n>``) and Creo writes that exact string as the snapshot's
    file stem. The alias record carries the string forward across jobs, so it
    is the only identity that provably names the owned file: nothing is derived
    by editing a name read back from the session (no prefix stripping, case
    folding or suffix rewriting).
    """
    from creo_mechdog.model_registry import aliases_of

    aliases = aliases_of(model) if isinstance(model, dict) else {}
    if not isinstance(aliases, dict):
        raise ValueError("component identity record is unavailable")
    identities: dict[int, str] = {}
    for entry in aliases.values():
        if not isinstance(entry, dict) or entry.get("op") != _COMPONENT_OP:
            continue
        feature_id = entry.get("feature_id")
        name = entry.get("snapshot_name")
        if type(feature_id) is not int or not isinstance(name, str):
            continue
        known = identities.get(feature_id)
        # Two different snapshot names for one occurrence cannot both name its
        # file; the association is ambiguous and must not be guessed.
        if known is not None and known != name:
            identities[feature_id] = ""
            continue
        identities[feature_id] = name
    return identities


def _references(inspection: dict, identities: dict[int, str]) -> tuple[list[dict], bool]:
    components = inspection.get("components")
    if not isinstance(components, list):
        raise ValueError("assembly inspection has no component list")
    references: list[dict] = []
    complete = True

    def walk(nodes: list, depth: int) -> None:
        nonlocal complete
        if depth > 32:
            raise ValueError("assembly reference depth exceeds 32")
        for node in nodes:
            if not isinstance(node, dict):
                raise ValueError("invalid assembly component record")
            feature_id = node.get("feature_id")
            name = identities.get(feature_id) if type(feature_id) is int else None
            kind = node.get("model_type", "part")
            if kind not in ("part", "sheetmetal", "assembly"):
                kind = "unknown"
            if not isinstance(name, str) or not _IDENTITY_NAME.fullmatch(name):
                references.append(
                    {"name": None, "status": "missing", "reason": "unresolved_identity"}
                )
                complete = False
                continue
            extension = "asm" if kind == "assembly" else "prt"
            references.append({"name": name + "." + extension, "status": "pending"})
            if kind == "assembly":
                children = node.get("components")
                if isinstance(children, list):
                    walk(children, depth + 1)
                else:
                    references.append(
                        {
                            "name": name + ".asm",
                            "status": "missing",
                            "reason": "nested_closure_unknown",
                        }
                    )
                    complete = False

    walk(components, 0)
    return references, complete


def create_bundle(model: dict, inspection: dict, output: Path, source_dir: Path) -> dict:
    """Create a partial manifest when references are missing; never copy external files."""
    if model.get("model_type") != "assembly":
        raise ValueError("native_bundle requires an assembly")
    owned = _safe_directory(source_dir)
    root = Path(model["part_file"])
    if root.is_symlink() or root.is_junction() or root.parent.resolve() != owned:
        raise ValueError("root snapshot must be in the owned model output directory")
    if not root.is_file() or not re.fullmatch(r"[a-z][a-z0-9_]{0,30}\.asm\.\d+", root.name, re.I):
        raise ValueError("verified root assembly snapshot is missing")
    root_name = root.name.rsplit(".", 1)[0]
    references, closure_known = _references(inspection, _snapshot_identities(model))
    names = [root_name, *(ref["name"] for ref in references if ref["name"])]
    names = list(dict.fromkeys(names))
    if len(names) > MAX_FILES:
        raise ValueError(f"bundle exceeds {MAX_FILES} native files")
    if any(not _NATIVE_NAME.fullmatch(name) for name in names):
        raise ValueError("unsafe native filename")
    bundle = output / "native_bundle"
    if bundle.exists():
        raise ValueError("native_bundle already exists for this job")
    output.mkdir(parents=True, exist_ok=True)
    bundle.mkdir()
    try:
        entries = []
        total = 0
        missing = {ref["name"] for ref in references if ref["status"] == "missing"}
        for name in names:
            source = root if name == root_name else _latest(owned, name)
            if source is None or not source.is_file() or name in missing:
                entries.append({"path": name, "status": "missing"})
                continue
            if source.parent.resolve() != owned:
                raise ValueError("source escaped owned model output directory")
            size = source.stat().st_size
            total += size
            if total > MAX_BYTES:
                raise ValueError(f"bundle exceeds {MAX_BYTES} bytes")
            destination = bundle / name
            shutil.copyfile(source, destination)
            with source.open("rb") as source_stream:
                source_hash = hashlib.file_digest(source_stream, "sha256").hexdigest()
            with destination.open("rb") as destination_stream:
                copied_hash = hashlib.file_digest(destination_stream, "sha256").hexdigest()
            if source_hash != copied_hash:
                raise ValueError(f"source changed while copying {name}")
            entries.append({"path": name, "status": "copied", "size": size, "sha256": copied_hash})
        unresolved = [ref for ref in references if ref["status"] == "missing"]
        manifest = {
            "schema": 1,
            "root": root_name,
            "complete": closure_known
            and not unresolved
            and all(e["status"] == "copied" for e in entries),
            "files": entries,
            "unresolved_references": unresolved,
            "total_bytes": total,
        }
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        if len(encoded) > 32768:
            raise ValueError("bundle manifest exceeds 32768 bytes")
        (bundle / "manifest.json").write_bytes(encoded)
        return {
            "directory": str(bundle),
            "manifest": str(bundle / "manifest.json"),
            "complete": manifest["complete"],
            "files": len(entries),
            "missing": sum(e["status"] == "missing" for e in entries) + len(unresolved),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    except Exception:
        shutil.rmtree(bundle)
        raise
