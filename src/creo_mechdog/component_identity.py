"""Component business-label identity projection (FEAT-023/008, T09A).

The native assembly inspection names every component by its physical copy
model name ("c_<token>_<n>"). That name is a uniqueness device of the
assemble_component copy step, not a business identity, and callers must not
have to guess it. This module projects the managed alias bindings onto the
component records at QUERY time so the business label and the
source_model_id/source_revision ride next to the record they describe.

Association key (fixed): the owning MODEL IDENTITY (the registry model_id of
the model whose inspection lists the component) plus the native component
feature_id. Labels are never identity: the same label can exist in different
models, and a removed-and-reinserted component keeps its label but gets a new
feature_id. Joins therefore happen strictly inside one model identity and
strictly by feature_id; a binding can never attach to a record of another
model or to a newer reinserted record.

Expression rules:

* exactly one component binding on a record -> label/source_model_id/
  source_revision mirror that binding and label_state is "single";
* several bindings on the same feature_id (multi-label) -> label and the
  singular source_* fields are null, label_state is "multi" and every binding
  stays visible in "bindings";
* no binding (older results, adopted assemblies) -> label_state is
  "unlabeled" and the derived fields stay null;
* a component binding whose feature_id is not among the current component
  records is a deleted identity: it is reported in "deleted_identities" and
  never merged onto a current record, so an old reference cannot mispoint at
  a newer component.

A binding is a real component binding when the alias entry records
op="assemble_component" (the native remember always stamps the op) or its
feature_id is one of the current component ids, the same rule
component_changes uses. Generic feature aliases (sketch, extrude, ...) are
never listed.

The projection never mutates the inspection or alias payloads and never
invents labels, ids or source values. Alias payloads resolve through
model_registry.aliases_of first, so controlled detail references (BUG-077)
work exactly like inline records and a tampered reference refuses instead of
silently losing labels.
"""

from __future__ import annotations

from typing import Any

COMPONENT_OP = "assemble_component"
IDENTITY_KEY = "model_identity+feature_id"


def _binding_feature_id(entry: Any) -> int | None:
    value = entry.get("feature_id") if isinstance(entry, dict) else None
    return value if type(value) is int else None


def _binding_source(entry: dict[str, Any]) -> tuple[Any, Any]:
    model_id = entry.get("source_model_id")
    revision = entry.get("source_revision")
    return (
        model_id if isinstance(model_id, str) else None,
        revision if type(revision) is int else None,
    )


def _binding_record(label: str, entry: dict[str, Any]) -> dict[str, Any]:
    source_model_id, source_revision = _binding_source(entry)
    return {
        "label": label,
        "source_model_id": source_model_id,
        "source_revision": source_revision,
    }


def _is_component_binding(entry: Any, component_ids: set[int]) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("op") == COMPONENT_OP:
        return True
    feature_id = _binding_feature_id(entry)
    return feature_id is not None and feature_id in component_ids


def project_component_identities(
    model: dict[str, Any], components: Any, aliases: Any = None
) -> dict[str, Any]:
    """Project alias bindings onto one model's component records.

    components is the native component record list of THIS model's inspection;
    aliases defaults to the model's resolved alias map. The return value is
    {"identity_key", "components", "deleted_identities"}.
    """
    model_id = model.get("model_id") if isinstance(model.get("model_id"), str) else None
    if aliases is None:
        from creo_mechdog.model_registry import aliases_of

        aliases = aliases_of(model)
    if not isinstance(aliases, dict):
        aliases = {}
    records = components if isinstance(components, list) else []
    component_ids = {
        feature_id
        for feature_id in (_binding_feature_id(record) for record in records)
        if feature_id is not None
    }
    bindings_by_id: dict[int, list[dict[str, Any]]] = {}
    for label, entry in aliases.items():
        if not isinstance(label, str) or not _is_component_binding(entry, component_ids):
            continue
        feature_id = _binding_feature_id(entry)
        if feature_id is None:
            continue
        bindings_by_id.setdefault(feature_id, []).append(_binding_record(label, entry))
    projected = []
    for record in records:
        item = dict(record) if isinstance(record, dict) else {}
        feature_id = _binding_feature_id(record)
        bindings = sorted(bindings_by_id.get(feature_id, []), key=lambda binding: binding["label"])
        if not bindings:
            label_state = "unlabeled"
        elif len(bindings) == 1:
            label_state = "single"
        else:
            label_state = "multi"
        single = bindings[0] if label_state == "single" else None
        item["identity"] = {"model_id": model_id, "feature_id": feature_id}
        item["labels"] = [binding["label"] for binding in bindings]
        item["label"] = single["label"] if single else None
        item["label_state"] = label_state
        item["source_model_id"] = single["source_model_id"] if single else None
        item["source_revision"] = single["source_revision"] if single else None
        item["bindings"] = bindings
        projected.append(item)
    deleted = []
    for feature_id in sorted(bindings_by_id):
        if feature_id in component_ids:
            continue
        bindings = sorted(bindings_by_id[feature_id], key=lambda binding: binding["label"])
        deleted.append(
            {
                "identity": {"model_id": model_id, "feature_id": feature_id},
                "labels": [binding["label"] for binding in bindings],
                "bindings": bindings,
                "reason": "feature_id_not_in_verified_components",
            }
        )
    return {
        "identity_key": {"model_id": model_id, "key": IDENTITY_KEY},
        "components": projected,
        "deleted_identities": deleted,
    }


def decorate_component_records(
    model: dict[str, Any], components: Any, aliases: Any = None
) -> list[dict[str, Any]]:
    """Decorated component records only (the query-section projection)."""
    return project_component_identities(model, components, aliases)["components"]
