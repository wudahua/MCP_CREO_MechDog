"""Release scope. Registered tools are not a claim that every Creo operation works."""

from __future__ import annotations

import math

from version import VERSION

REGISTERED_OPERATIONS = (
    "airfoil_sketch",
    "update_airfoil",
    "update_sketch_geometry",
    "feature_group",
    "reorder_features",
    "axis_pattern",
    "linear_pattern",
    "geometry_transform",
    "set_geometry_transform",
    "sketch",
    "extrude",
    "revolve",
    "hole",
    "round",
    "chamfer",
    "datum_plane",
    "datum_axis",
    "shell",
    "dimension_pattern",
    "mirror",
    "sweep",
    "loft",
    "draft",
    "sheetmetal_wall",
    "sheetmetal_planar_wall",
    "sheetmetal_base_flange",
    "resize_sheetmetal_planar_wall",
    "sheetmetal_flange",
    "sheetmetal_flange_profile",
    "sheetmetal_corner_relief",
    "sheetmetal_quilt_form",
    "sheetmetal_unbend",
    "sheetmetal_flat_pattern",
    "sheetmetal_bend_back",
    "assemble_component",
    "component_placement",
    "component_constraints",
    "remove_component",
    "recolor_assembly",
    "feature_state",
    "set_dimensions",
    "set_sketch_dimensions",
    "set_parameters",
    "set_relations",
    "feature_tree",
    "regenerate",
    "save",
    "export",
    "import_geometry",
    "dump_tree",
    "mass_properties",
    "udf_inspect",
    "udf_create",
    "datum_csys",
    "datum_points",
    "surface_fill",
    "thicken",
    "surface_offset",
    "solidify",
    "redefine_solidify_body",
    "surface_trim",
    "surface_loft",
    "surface_boundary_fill",
    "surface_round",
    "surface_group_measure",
    "surface_curvature",
    "quilt_merge",
    "project_curve",
    "boolean_bodies",
    "rib",
    "drawing_model",
    "drawing_sheet",
    "drawing_view",
    "drawing_projection",
    "drawing_view_update",
    "drawing_note",
    "drawing_note_update",
    "drawing_table",
    "drawing_table_cell",
    "drawing_dimension",
    "drawing_delete",
)

# FEAT-039: an operation whose native route is not proved on hardware stays out
# of the published surface chain. surface_trim left this table in 0.12.1 after
# its live retained-side evidence, and project_curve left it after the live
# swept-surface route produced measured projections (line and arc, saved and
# reloaded). The entries below are still waiting for a route that produces
# measurable geometry, so no client receives a success the release cannot back
# up.

# The single copy of the reason a thin offset trim is refused. References publish
# the same text so the contract and the admission gate cannot drift apart.
SURFACE_TRIM_OFFSET_LIMIT = (
    "surface_trim offset_mm is not published: the documented Thin tree "
    "(PRO_SURF_TRIM_THIN with PRO_E_THICKNESS/PRO_E_SRF_OFFS_METHOD) only "
    "removes a band of that thickness when the tool is a quilt, keeps both "
    "sides instead of the requested keep_side, and offset_side has no "
    "observable effect (2026-11-06 six direction variants all produced the "
    "same band; negative thickness fails regeneration)"
)

UNAVAILABLE_OPERATIONS: dict[str, str] = {
    "sheetmetal_flange_profile": (
        "DEV-078 multi-entity flange profiles are offline candidates only; "
        "hem/joggle geometry, sheetmetal identity, flat pattern and saved reload are not verified"
    ),
    "sheetmetal_corner_relief": (
        "DEV-078 independent three-surface corner relief is an offline candidate only; "
        "a real ripped edge and intersecting bends are prerequisites, not verified inputs"
    ),
    "sheetmetal_quilt_form": (
        "DEV-078 quilt form is an offline candidate only; native forming, gauge retention "
        "and flatten/unflatten behavior require hardware evidence"
    ),
    # quilt_merge is published again in 0.19.0 (FEAT-039/H03 resolved the joined
    # target quilt); the old global gate is deliberately not carried forward.
    # BUG-124/C1 left this table on 2026-11-13: STEP and IGES imports ran on Creo
    # 12.4.0.0 (create_code=0, one closed 440.0 mm2 quilt and six quilts at
    # 1540.0 mm2, both saved and reloaded), so the gate is gone. It goes back here
    # if a later release cannot repeat that; Creo 10 is still unverified.
    "surface_boundary_fill": (
        "DEV-078 four-boundary two-direction blend is offline only and not published; "
        "the previous single-direction candidate creates and extracts (ProFeatureWithoptionsCreate=0, "
        "ProFeatureElemtreeExtract=0) but regeneration fails with feature_status=6 "
        "and produces no quilt (quilt visit -4, quilt_count=0, empty "
        "element-error list); a planar 4-curve rectangle loop whose measured endpoint gap is "
        "1.9e-31 mm reproduces it twice and rolls back, so the closed single-direction chain "
        "does not yield a measurable filled surface; this evidence does not test the new route"
    ),
}

# FEAT-065/M4: optional fields of a published operation whose native route is
# not proved, keyed "<op>.<field>". A non-empty value is refused before a job
# exists, in the same words as UNAVAILABLE_OPERATIONS. Deleting an entry is the
# only switch. Empty since 2026-11-11: surface_loft.boundary_conditions left
# after FEAT-065 T2b measured 'tangent' on Creo 12.4.0.0; the conditions that
# were not proved (curvature, normal, any non-free guide boundary) are refused
# by the SurfaceLoftOp schema and again by native/surface_loft.cpp.
UNAVAILABLE_FIELDS: dict[str, str] = {}


def require_available(operations: list[dict]) -> None:
    unavailable = [op["op"] for op in operations if op["op"] in UNAVAILABLE_OPERATIONS]
    if unavailable:
        details = "; ".join(
            f"{name}: {UNAVAILABLE_OPERATIONS[name]}" for name in dict.fromkeys(unavailable)
        )
        raise ValueError(
            f"Not available in the {VERSION} release; no native job was queued. {details}"
        )
    for op in operations:
        for key, reason in UNAVAILABLE_FIELDS.items():
            name, field = key.split(".", 1)
            if op["op"] == name and op.get(field):
                raise ValueError(
                    f"Not available in the {VERSION} release; no native job was queued. "
                    f"{key}: {reason}"
                )
    for op in operations:
        if op["op"] == "loft" and (op.get("mode", "add") != "add" or op.get("new_body", False)):
            raise ValueError(
                "Direct Blend supports solid add into the default body only; cut, surface and new_body are not accepted - the 2026-11-05 measurement on the seed reference part shows the blend feature has no extractable element tree (ProFeatureElemtreeExtract returned -18), so the panel route is the only route for a blend"
            )
        if (
            op["op"] in ("sketch", "airfoil_sketch", "update_sketch_geometry")
            and op.get("endpoint_policy") == "weld"
        ):
            # FEAT-039/W01: the native side regularises the welded endpoints by
            # half the gap before it writes them, so the bound the caller gives
            # is what keeps the move controlled. Without a bound the request is
            # refused before a job exists.
            bound = op.get("max_endpoint_move_mm")
            if (
                not isinstance(bound, (int, float))
                or isinstance(bound, bool)
                or not math.isfinite(float(bound))
                or float(bound) <= 0.0
            ):
                raise ValueError(
                    "endpoint_policy weld needs max_endpoint_move_mm: the native side "
                    "moves each welded endpoint by half the gap, so the bound is what "
                    "keeps the move controlled"
                )
        if op["op"] == "surface_trim" and op.get("offset_mm") is not None:
            # FEAT-039/S07: a distance here is not the published "keep one side"
            # semantics. The documented Thin tree does honour PRO_E_THICKNESS on a
            # quilt tool (2026-11-06: 40x20 target -> 700 mm2 at 5 mm), but it
            # removes a band instead of moving the cut, the direction elements are
            # inert, and a datum-plane tool ignores the thickness.
            raise ValueError(SURFACE_TRIM_OFFSET_LIMIT)


# H13: operations whose native implementation is compiled only when the worker's
# Toolkit SDK carries a specific header. The running worker's own build-info is
# the only authority; Python must not inspect this machine's SDK or guess from
# release_numeric. BUG-120/D1: the entry covers the element_tree route only; the
# resident_panel route is a separate backend with its own worker declaration.
WORKER_CONDITIONAL_OPERATIONS = ("surface_loft",)

#: BUG-120/D1: the worker build-info key the resident panel backend declares. The
#: panel route reuses ``op="surface_loft"`` with ``creation_route="resident_panel"``
#: instead of adding a public tool, so its readiness is a separate fact.
PANEL_FEATURE = "surface_loft_panel"


def is_panel_route(op: dict) -> bool:
    """True when this operation asks for the resident panel creation route."""
    return op.get("op") == "surface_loft" and op.get("creation_route") == "resident_panel"


def _tree_route_operations(operations: list[dict]) -> list[dict]:
    return [
        op
        for op in operations
        if op.get("op") in WORKER_CONDITIONAL_OPERATIONS and not is_panel_route(op)
    ]


def _verified_worker_feature(identity: object, name: str) -> dict | None:
    if not isinstance(identity, dict) or identity.get("identity_status") != "verified":
        return None
    features = identity.get("features")
    feature = features.get(name) if isinstance(features, dict) else None
    if not isinstance(feature, dict) or not isinstance(feature.get("available"), bool):
        return None
    return feature


def _missing_requirements(feature: dict) -> list[str]:
    missing = feature.get("missing_sdk_requirements")
    if isinstance(missing, list) and missing:
        return [str(item) for item in missing]
    requirements = feature.get("sdk_requirements")
    if isinstance(requirements, list) and requirements:
        return [str(item) for item in requirements]
    return ["PRO_E_BNBLN_CURVES"]


def require_worker_availability(operations: list[dict], identity: object) -> None:
    """Reject a conditional operation before a job exists when the worker lacks it.

    Only a verified worker self-report can reject. A missing or invalid identity
    stays unknown: the runtime error remains the authority, and Python never
    substitutes its own SDK inspection for the loaded executor. BUG-120/D1: this
    gate is about the element_tree route only, so a resident_panel request never
    inherits a missing boundary-blend element id from it.
    """
    for op in _tree_route_operations(operations):
        name = op.get("op")
        feature = _verified_worker_feature(identity, name)
        if feature is None or feature["available"]:
            continue
        missing = ", ".join(_missing_requirements(feature))
        digest = identity.get("source_digest") if isinstance(identity, dict) else None
        raise ValueError(
            f"{name} is compiled out of the current worker: its Toolkit SDK is missing the "
            f"boundary-blend element ids {missing} (worker source_digest={digest}, "
            f"state={feature.get('state')}). No native job was queued. Rebuild the worker "
            "against an SDK whose ProElemId.h declares the boundary-blend tree or use a route "
            "that does not need it; availability is taken from the executor's own build "
            "identity, not from the Python environment's SDK headers or release_numeric."
        )


def require_kernel_completion(operations: list[dict], identity: object) -> None:
    """BUG-122 / BUG-205: refuse element_tree surface_loft before a job when unsupported.

    On Creo 10 (release_numeric=42), ProFeatureElemtreeExtract (-18) and
    redefine regeneration leave the feature incomplete with zero geometry even
    when accept_unverified_completion=True, so element_tree is refused before
    a job whenever kernel_completion != "supported". On other releases, the
    worker-SHA-keyed extract refusal keeps accept_unverified_completion bypass.
    """
    if not _tree_route_operations(operations):
        return
    from creo_mechdog import panel_profiles

    feature = _verified_worker_feature(identity, "surface_loft")
    host_rel = panel_profiles.host_release(identity)
    if (
        host_rel == 42
        and isinstance(identity, dict)
        and identity.get("identity_status") == "verified"
        and (feature is None or feature.get("kernel_completion") != "supported")
    ):
        raise ValueError(
            "surface_loft creation_route='element_tree' is refused before a job on Creo 10 "
            "(release_numeric=42): this Creo release refuses ProFeatureElemtreeExtract (-18) "
            "and leaves the blend incomplete with zero geometry (SURFACE_LOFT_ACCEPT_INCOMPLETE) "
            "even with accept_unverified_completion=true. No native job was queued. Use "
            "creation_route='resident_panel' after confirming creo_callback_status readiness='ready'."
        )
    # BUG-135: on non-Creo-10 hosts, a request that explicitly accepts geometry-only
    # verification is not blocked by an earlier extract refusal; the receipt still
    # reports kernel_completion="unsupported" so the kept feature is never read as proven.
    if all(op.get("accept_unverified_completion") for op in _tree_route_operations(operations)):
        return
    if feature is None or feature.get("kernel_completion") != "unsupported":
        return
    evidence = feature.get("evidence")
    if not isinstance(evidence, dict):
        return
    if evidence.get("create_code") != 0 or evidence.get("extract_code") != -18:
        return
    raise ValueError(
        "surface_loft is refused before a job on this executor: the last run created the "
        "boundary blend (create_code=0) but the host kernel refused to hand back its element "
        f"tree (extract_code=-18, release_numeric={evidence.get('release_numeric')}, "
        f"worker_sha256={identity.get('worker_sha256')}, job_id={feature.get('job_id')}). "
        "No native job was queued and no feature would be created. This creation path still "
        "needs element-tree extraction when a template XML is supplied. Use a host that can "
        "complete that path, or a separately verified route that does not need extraction. "
        "The observation is keyed by worker SHA256: a new worker build invalidates the "
        "record, but does not prove that this host can complete the feature. Read "
        "creo_capabilities for the recorded evidence."
    )


def require_panel_route(identity: object, *, root=None, environ=None) -> dict:
    """BUG-120/D1: admit a resident_panel request, or refuse before a job exists.

    Three facts must hold, in this order: the loaded worker declares a panel
    backend, that backend is available, and an admitted UI profile exists for this
    request (certified for normal clients, ticket-bound for the development
    driver). A missing declaration is a refusal, never a reason to run the element
    tree instead; a compiled backend alone is not readiness either.

    Returns the admission record so the job can carry which profile and mode ran.
    """
    from creo_mechdog import panel_profiles

    feature = _verified_worker_feature(identity, PANEL_FEATURE)
    digest = identity.get("source_digest") if isinstance(identity, dict) else None
    if feature is None:
        raise ValueError(
            "creation_route='resident_panel' is not available on this executor: the current "
            "worker does not declare a surface_loft_panel backend (worker "
            f"source_digest={digest}). No native job was queued and the request is not retried "
            "on the element_tree route. Rebuild the worker with the panel backend, or ask for "
            "creation_route='element_tree' explicitly on a host that supports it."
        )
    if not feature["available"]:
        raise ValueError(
            "creation_route='resident_panel' is not available on this executor: the worker "
            f"declares surface_loft_panel state={feature.get('state')!r} (worker "
            f"source_digest={digest}). No native job was queued; compiled and runtime-ready are "
            "separate facts, so read creo_capabilities before retrying."
        )
    return panel_profiles.admit_for_request(identity, root=root, environ=environ)


def require_panel_directions(operations: list[dict], admission: dict) -> None:
    """Refuse a second-direction request the admitted profile cannot select.

    The native worker refuses the same request, but only after the job exists and
    the panel session guard is written. That projects an unknown_outcome onto a
    model for a request that was never executable. Admission is the last point that
    can still say "nothing was attempted" and keep that statement true.
    """
    needs_second = any(op.get("guides") for op in operations if is_panel_route(op))
    if not needs_second or str(admission.get("second_direction_macro") or ""):
        return
    raise ValueError(
        "the resident_panel request selects second-direction guides but the admitted profile "
        f"{admission.get('profile_id')!r} freezes no second_direction_macro; no job was created "
        "and the dialog was not opened. Use a certified profile that records the second "
        "direction, or send a first-direction-only request."
    )


def _kernel_observation(identity: object, runtime: object) -> dict:
    """The runtime observation that belongs to this exact worker, else unknown."""
    worker_sha = identity.get("worker_sha256") if isinstance(identity, dict) else None
    if (
        not isinstance(runtime, dict)
        or not worker_sha
        or runtime.get("worker_sha256") != worker_sha
        or runtime.get("kernel_completion") not in ("supported", "unsupported")
    ):
        return {"kernel_completion": "unknown"}
    return runtime


def _panel_route_document(identity: object, callback_runtime: object = None) -> dict:
    """BUG-120/D1 + BUG-193: what the resident_panel route needs, and what is missing.

    ``compiled`` describes the loaded worker; ``runtime_ready`` additionally needs a
    certified UI profile for this release and (when ``callback_runtime`` is supplied)
    a verified ready resident callback. Neither one promises geometry, and the
    fields are reported separately so a compiled backend never reads as usable.
    """
    from creo_mechdog import panel_profiles

    feature = _verified_worker_feature(identity, PANEL_FEATURE)
    document: dict = {
        "default": False,
        "request_field": {"creation_route": "resident_panel"},
        "limits": (
            "2-8 first-direction positions, each written as {label, open_confirmed:true} for "
            "one MCP-owned sketch with one open non-composite curve (a bare label is refused "
            "before a job exists because this build cannot read a standalone curve's openness), "
            "plus optionally one end position that is an MCP-owned datum point (first or last "
            "only, at most one per run); optional second direction of 2-8 guide curves in the "
            "same form; at most 11 positions per run (7 curves + 1 point + 3 guides is the "
            "accepted maximum); no boundary conditions or template. A single feature cannot hold "
            "both the end point and guides: Creo 10 rejects that combination at regeneration, so "
            "build the point-converged tip as a second loft that shares the last section. Two "
            "sections are ruled and three or more are one smooth blend. Before the dialog opens "
            "the worker reports a per-pair section/guide fit block (21 pairs for 7+3) and, after "
            "a successful saved/reloaded run, the created feature/quilt association with area, "
            "openness and boundary records; geometry_check.verified is true only when every one "
            "of those readings exists"
        ),
        "compiled": None,
        "state": None,
        "runtime_ready": False,
        "reason": None,
    }
    if feature is None:
        document["state"] = "not_declared"
        document["reason"] = "the loaded worker does not declare a surface_loft_panel backend"
    else:
        document["compiled"] = feature["available"]
        document["state"] = feature.get("state")
        if not feature["available"]:
            document["reason"] = "the panel backend is compiled out of this worker"
    try:
        profile = panel_profiles.certified_profile(
            release_numeric=panel_profiles.host_release(identity)
        )
    except (ValueError, OSError, TypeError, KeyError) as exc:
        # Disclosure fails closed: a manifest this release cannot read must not turn
        # creo_capabilities into an error while the route is closed anyway.
        profile = None
        document["profile"] = {"status": "uncertified", "reason": str(exc)}
    else:
        document["profile"] = {"status": "certified", **profile.document()}
    # A certified profile is bound to the release it was measured on. Until a
    # connected job on this worker recorded that release, admission cannot match
    # it either, so disclosure must not call the route ready.
    release = panel_profiles.host_release(identity)
    profile_ready = bool(profile is not None and release == profile.release_numeric)
    callback_ready = True
    if callback_runtime is not None:
        cb_readiness = (
            callback_runtime.get("readiness")
            if isinstance(callback_runtime, dict) and callback_runtime.get("readiness")
            else "unknown"
        )
        document["callback_readiness"] = cb_readiness
        callback_ready = cb_readiness == "ready"
    document["runtime_ready"] = bool(
        feature and feature["available"] and profile_ready and callback_ready
    )
    if not document["runtime_ready"] and document["reason"] is None:
        if profile is None:
            document["reason"] = "no certified panel UI profile for this release"
        elif release is None:
            document["reason"] = (
                "the host Creo release is not recorded yet: run one native job on this worker "
                "(a new part or a sketch) so the certified profile can be matched to it"
            )
        elif not profile_ready:
            document["reason"] = (
                f"the certified profile {profile.profile_id!r} was measured on "
                f"release_numeric={profile.release_numeric}, but this host reports {release}"
            )
        else:
            document["reason"] = (
                f"resident callback readiness is {document.get('callback_readiness', 'unknown')!r}; "
                "query creo_callback_status and start the registered auxiliary application in Creo "
                "before calling resident_panel"
            )
    return document


def project_worker_availability(
    families_doc: dict,
    identity: object,
    runtime: object = None,
    callback_runtime: object = None,
) -> dict:
    """Show the verified worker's compiled feature state in capability families.

    ``runtime`` is the last kernel-completion observation for this worker. It never
    changes ``available`` or ``enabled`` (those describe the build), is ignored when
    it came from another worker, and adds ``runtime_admission`` / ``runtime_ready``
    so callers distinguish compiled availability from live session readiness
    (BUG-122, BUG-193).
    """
    from creo_mechdog import panel_profiles

    cb_readiness = None
    if callback_runtime is not None:
        cb_readiness = (
            callback_runtime.get("readiness")
            if isinstance(callback_runtime, dict) and callback_runtime.get("readiness")
            else "unknown"
        )
        loft_entry = families_doc.get("loft")
        if isinstance(loft_entry, dict):
            loft_ready = cb_readiness == "ready"
            loft_entry["runtime_ready"] = loft_ready
            admission = dict(loft_entry.get("runtime_admission") or {})
            admission["status"] = "ready" if loft_ready else "requires_ready_callback"
            admission["callback_readiness"] = cb_readiness
            if isinstance(callback_runtime, dict) and callback_runtime.get("reason"):
                admission["reason"] = callback_runtime["reason"]
            loft_entry["runtime_admission"] = admission
    feature = _verified_worker_feature(identity, "surface_loft")
    entry = families_doc.get("surface_loft")
    if not isinstance(entry, dict):
        return families_doc
    panel_doc = _panel_route_document(identity, callback_runtime=callback_runtime)
    if feature is None:
        # No verified tree declaration: the top-level fields keep their published
        # meaning, and the routes block still reports both routes by name so a
        # missing tree feature cannot hide a declared panel backend.
        entry["routes"] = {
            "element_tree": {
                "default": True,
                "available": None,
                "state": "not_declared",
                "runtime_ready": False,
                "request_field": "creation_route omitted or 'element_tree'",
                "scope": "keeps 2-32 sections, guides, boundary conditions and template trees",
                "reason": "the loaded worker did not declare a verified surface_loft feature",
            },
            "resident_panel": panel_doc,
        }
        entry["runtime_ready"] = bool(panel_doc.get("runtime_ready"))
        return families_doc
    available = feature["available"]
    entry["available"] = available
    entry["availability"] = "available" if available else "unavailable"
    entry["worker_build_identity"] = {
        "identity_status": identity.get("identity_status"),
        "identity_source": identity.get("identity_source"),
        "source_digest": identity.get("source_digest"),
        "worker_sha256": identity.get("worker_sha256"),
        "feature_state": feature.get("state"),
        "probe": "creo_worker.exe build-info",
    }
    observation = _kernel_observation(identity, runtime)
    entry["worker_build_identity"]["kernel_completion"] = observation["kernel_completion"]
    for key in ("release_numeric", "observed_at", "job_id", "evidence"):
        if key in observation:
            entry["worker_build_identity"][key] = observation[key]
    host_rel = panel_profiles.host_release(identity)
    tree_admission: dict = {"status": "unknown"}
    tree_ready = bool(available)
    if available:
        entry["enabled_semantics"] = (
            "compiled into the current worker; a live run is still required for geometry, "
            "and compiled availability does not prove this host kernel can complete the "
            "feature tree extraction"
        )
        evidence = observation.get("evidence")
        if (
            observation["kernel_completion"] == "unsupported"
            and isinstance(evidence, dict)
            and evidence.get("create_code") == 0
            and evidence.get("extract_code") == -18
        ):
            # BUG-122: the same signature requires admission to refuse before a job,
            # so the projection must not read as "ready to call".
            tree_admission = {
                "status": "refused_before_job",
                "reason": "host_kernel_extract_unsupported",
                "create_code": evidence.get("create_code"),
                "extract_code": evidence.get("extract_code"),
                "release_numeric": evidence.get("release_numeric"),
                "job_id": observation.get("job_id"),
                "observed_at": observation.get("observed_at"),
                "effect": (
                    "creo_surface_loft is refused before a native job on this worker; no "
                    "incomplete feature is created; a new worker build clears the record"
                ),
            }
            entry["runtime_admission"] = tree_admission
            tree_ready = False
        elif host_rel == 42 and observation["kernel_completion"] != "supported":
            # BUG-193 / BUG-135: Creo 10 (release 42) refuses ProFeatureElemtreeExtract (-18)
            # and leaves element_tree blends incomplete even with accept_unverified_completion.
            tree_admission = {
                "status": "known_release_extract_unsupported",
                "reason": "creo10_element_tree_extract_unsupported",
                "release_numeric": 42,
                "effect": (
                    "Creo 10 (release 42) refuses element_tree extraction (-18); use "
                    "creation_route='resident_panel' after starting the resident callback"
                ),
            }
            tree_ready = False
    else:
        missing = ", ".join(_missing_requirements(feature))
        entry["enabled"] = False
        entry["unavailable_reason"] = f"bnbln_element_ids_missing: {missing}"
        entry["enabled_semantics"] = (
            "compiled out of the current worker; the SDK requirement is not satisfied"
        )
        tree_ready = False
    entry["routes"] = {
        "element_tree": {
            "default": True,
            "available": available,
            "state": feature.get("state"),
            "runtime_ready": tree_ready,
            "request_field": "creation_route omitted or 'element_tree'",
            "scope": "keeps 2-32 sections, guides, boundary conditions and template trees",
            "runtime_admission": tree_admission,
        },
        "resident_panel": panel_doc,
    }
    entry["runtime_ready"] = bool(tree_ready or panel_doc.get("runtime_ready"))
    if not entry["runtime_ready"] and "runtime_admission" not in entry:
        entry["runtime_admission"] = {
            "status": "not_ready",
            "element_tree_status": tree_admission.get("status"),
            "resident_panel_callback_readiness": panel_doc.get("callback_readiness", "unknown"),
            "check_tool": "creo_callback_status",
            "reason": panel_doc.get("reason") or tree_admission.get("reason"),
        }
    elif entry["runtime_ready"] and "runtime_admission" not in entry:
        entry["runtime_admission_note"] = (
            "runtime_admission is null or omitted when all runtime admission checks passed; "
            "query creo_callback_status to confirm readiness='ready' and reason='live_identity_verified'"
        )
    return families_doc


KNOWN_LIMITATIONS = (
    {
        "id": "add_volume_check",
        "condition": "solid add via extrude, revolve, sweep or loft",
        "release": "all Toolkit releases supported by this worker",
        "evidence": "BUG-191",
        "configurable": False,
        "effect": "The worker measures total solid volume before and after each add. A decrease above tolerance or an unverified measurement fails the job before save and invokes checkpoint rollback. The operation reports add_volume_check and the measured volumes in mm3.",
    },
    {
        "id": "cut_scope",
        "condition": "extrude cut scope requested for several bodies, a revolve cut, or with new_body",
        "release": "Creo 10/12.4 native body branch exposes one PRO_E_BODY_SELECT (blind and through_all cuts supported)",
        "evidence": "B4/F08 2026-11-10; BUG-150 2026-11-22; FEAT-075 through_all+scope 2026-11-23",
        "configurable": False,
        "effect": "shape limits are refused before the job (one target body per cut, split the rest into further cuts); cuts always apply at body granularity and cannot scope to a single merged feature without separating it via new_body=true first (then boolean_bodies union); a body id the part does not hold, or a created feature that does not carry the requested scope, fails the job with F08_SCOPE_RESOLVE_FAILED and rolls back; a non-target body that changed fails with F08_SCOPE_NON_TARGET_CHANGED",
    },
    {
        "id": "surface_loft_sdk_header",
        "condition": (
            "worker built against a Toolkit SDK whose ProElemId.h omits the boundary-blend "
            "element ids"
        ),
        "release": "external Creo 10 report; local Creo 12.4 declares every element id",
        "evidence": "DEV-076 H13 worker build-info; missing-element-id C++ fixture",
        "configurable": False,
        "effect": "creo_surface_loft is unavailable and refused before a job",
    },
    {
        "id": "surface_trim_open_tool",
        "condition": "the tool intersects the target as an open arc or does not partition a region",
        "release": "Creo 12.4 and external Creo 10 evidence",
        "evidence": "DEV-075 H14 / surface_trim_regeneration feature_status=6",
        "configurable": False,
        "effect": "trim fails and rolls back; intersection curves are not measured",
    },
    {
        "id": "surface_trim_offset_semantics",
        "condition": "surface_trim offset_mm/offset_side requested",
        "release": "Creo 12.4",
        "evidence": "FEAT-039 S07 / six direction variants",
        "configurable": False,
        "effect": "refused; the documented thin tree removes a band and ignores direction",
    },
    {
        "id": "surface_offset_result",
        "condition": "caller expects a standalone offset quilt",
        "release": "Creo 12.4",
        "evidence": "FEAT-039 H07",
        "configurable": False,
        "effect": "returns the offset wall; target_quilt_id names the source quilt",
    },
    {
        "id": "quilt_merge_scope",
        "condition": "INTERSECT, more than two quilts in one call, closed-shell merge or non-mm units",
        "release": "Creo 12.4",
        "evidence": "FEAT-039 H03 / 0.19.0 two-quilt JOIN",
        "configurable": False,
        "effect": "only two-quilt JOIN is published; other modes are unverified; the "
        "receipt names consumed_quilt_ids and merged_surface_ids, but inspect_model "
        "still enumerates any kernel residue of a consumed tool quilt",
    },
    {
        "id": "cut_profile_area_basis",
        "condition": "caller compares profile.material_area_mm2 with material_removed_mm3",
        "release": "Creo 12.4 and external Creo 10 evidence",
        "evidence": "2026-11-08 multi-contour arc cut feedback; profile.method=analytic-input",
        "configurable": False,
        "effect": "material_area_mm2 is the analytic input-sketch area, not a kernel section; "
        "partly circular multi-contour cuts can differ by about 2% from the removed volume",
    },
    {
        "id": "sketch_profile_partial_counts",
        "condition": "caller compares sketch profile counts with native_section on a b_spline/spline/ellipse profile",
        "release": "FEAT-066 b_spline, all releases with analytic profile diagnostics",
        "evidence": "DEV-098; profile_diagnostics._expand lists those types as unsupported",
        "configurable": False,
        "effect": "analysis='partial' makes profile entity/contour counts a lower bound (two closed "
        "b_splines can report 0 entities while native_section reports 2); closure and counts come "
        "from native_section or creo_measure_surface_group, and diagnostic_semantics returns "
        "consistent=null instead of true/false",
    },
    {
        "id": "quilt_closure_not_solidifiable",
        "condition": "caller uses the quilt closure block to predict topological closure or solidify",
        "release": "Creo 12.4 and external Creo 10 evidence",
        "evidence": "DEV-098 / 0.32.0 feedback; native/surface_measure.h quilt_closed_native",
        "configurable": False,
        "effect": "closure is only ProQuiltVolumeEval: available (a volume), quilt_is_open or "
        "quilt_volume_eval_failed. A failed query (-62 on a 3-face shell) does not prove an open "
        "boundary and did not stop a single-step solidify committing; a single fill face can report "
        "closed=true. Topology needs creo_measure_surface_group; solidifiability needs the solidify "
        "effect_status; unknown stays null",
    },
    {
        "id": "hidden_hung_window_scope",
        "condition": "creo_process_snapshot reports state hidden_only with hung_window_observed=true",
        "release": "all releases with window observations",
        "evidence": "DEV-098 / 0.32.0 feedback; window_observations.connection_guidance",
        "configurable": False,
        "effect": "only a hidden top-level window (for example a launcher) failed to respond; "
        "visible_hung_window_observed stays false, hung_implies_modal is always false, and the "
        "snapshot neither proves the Creo session is stuck nor authorizes ending a process or "
        "clearing protection",
    },
    {
        "id": "sketch_tangent_or_intersecting_contours",
        "condition": "a single sketch contains multi-boss loops that share an edge, touch at a point, cross, or branch (>2 curves at a vertex)",
        "release": "all Creo releases supported by this worker",
        "evidence": "BUG-209 / profile_diagnostics.validate_solid_profile",
        "configurable": False,
        "effect": "solid extrude/revolve rejects branched, self-intersecting, intersecting, and tangent contours before queuing a job and names the conflicting entity pair(s). Combine adjacent/tangent multi-boss regions into a single non-self-intersecting outer boundary, or split overlapping bosses into separate extrude operations that union onto the solid body; disjoint or nested closed loops remain supported in one sketch.",
    },
    {
        "id": "edge_selector_nearest_scope",
        "condition": "a geometry_selector edge reference matches zero or several edges",
        "release": "DEV-098 nearest list; FEAT-085 optional edge disambiguation",
        "evidence": "native/geometry_selectors.cpp measured edge candidates",
        "configurable": True,
        "effect": "zero matches refuse the job and may include up to five candidates in "
        "geometry_selector_diagnostic.nearest_edges. For model-space anchors, on_face can "
        "restrict the current surface and a "
        "point_mm-only anchor can opt into ambiguity:'nearest'. Only a unique minimum distance "
        "inside tolerance is selected. A tie within 1e-6 mm requires a face or a current edge ID.",
    },
    {
        "id": "surface_selector_nearest_scope",
        "condition": "a geometry_selector surface reference matches zero or several faces",
        "release": "DEV-098 nearest surface list",
        "evidence": "DEV-098 native/geometry_selectors.cpp zero-match diagnostic",
        "configurable": False,
        "effect": "a zero-match geometry_selector surface refuses the job but reports "
        "geometry_selector_diagnostic.nearest_surfaces (at most 5 planar/cylindrical faces, "
        "ordered by error then id, with type/origin_mm/normal-or-axis/error_mm and the applied "
        "axis/radius/center/points errors); wrong-type candidates stay in type_rejected_ids; "
        "several matches still report only candidate_count and matched_ids; a nearest face is "
        "never selected automatically, and callers must re-read creo_inspect_model surfaces or "
        "pass {kind:'surface',id:N}. An assembly-space selector additionally reports "
        "requested_coordinate_space='assembly' while its measurements stay in the component frame",
    },
    {
        "id": "surface_round_scope",
        "condition": "edge-chain, variable radius, full/transition or non-adjacent faces",
        "release": "Creo 12.4",
        "evidence": "FEAT-055 H08",
        "configurable": False,
        "effect": "constant radius on two adjacent faces only; no edge-chain input",
    },
    {
        "id": "sheetmetal_forming_unavailable",
        "condition": "corner relief beyond miter cuts, louver/form, hem/jog, grille cut, boss/hinge/ear",
        "release": "Creo 12.4 counter-evidence",
        "evidence": "FEAT-014 forming survey; 0.19.0 release notes",
        "configurable": False,
        "effect": "features are unavailable or unproven; gates remain",
    },
    {
        "id": "quilt_offset_unavailable",
        "condition": "standalone offset quilt",
        "release": "Creo 12.4 counter-evidence",
        "evidence": "FEAT-039 H07",
        "configurable": False,
        "effect": "no public quilt_offset tool; surface_offset produces a wall",
    },
    {
        "id": "surface_boundary_fill_unavailable",
        "condition": "non-planar closed boundary fill",
        "release": "Creo 12.4 counter-evidence",
        "evidence": "FEAT-039 H09 / surface_boundary_fill gate",
        "configurable": False,
        "effect": "the tool is gated; planar sketch fill is unchanged",
    },
    {
        "id": "creo9_10_unverified",
        "condition": "Creo 9 or Creo 10 runtime behavior",
        "release": "external reports only; local baseline is Creo 12.4",
        "evidence": "DEV-074/075/076 handoffs",
        "configurable": False,
        "effect": "do not infer Creo 9/10 support from Creo 12.4 results",
    },
    {
        "id": "long_poll_limit",
        "condition": "creo_get_job wait_seconds above the published maximum",
        "release": "0.19.1+ maximum 300 seconds",
        "evidence": "FEAT-007",
        "configurable": True,
        "effect": "values above 300 are rejected before reading the job",
    },
    {
        "id": "chamfer_d1_d2_direction",
        "condition": "chamfer_type='d1_d2' per-face leg direction",
        "release": "FEAT-071",
        "evidence": "ProChamfer.h PRO_CHM_D1_X_D2 = 603 requires LEG1/LEG2/REFERENCE_SURFACE; "
        "2026-11-21 Creo 10 block probe: D1 lands on the adjacent face not named by "
        "reference_surface and D2 on the reference face (2/5 and 5/2 swapped, both 250 mm3)",
        "configurable": False,
        "effect": "distance_1/distance_2 and reference_surface are explicit and no face direction "
        "is inferred from reference order; on the tested Creo 10 block D1 went to the non-reference "
        "adjacent face and D2 to reference_surface, but other reference combinations, curved edges "
        "and other Creo versions stay unverified",
    },
)


PLAN_EXAMPLES = (
    {
        "name": "rectangle_extrude",
        "goal": "new part: 40x20 sketch extruded 10 mm",
        "operations": [
            {
                "op": "sketch",
                "label": "profile",
                "entities": [
                    {
                        "type": "rectangle",
                        "name": "rect",
                        "min": [0, 0],
                        "max": [40, 20],
                    }
                ],
            },
            {"op": "extrude", "label": "body", "sketch": "profile", "depth": 10},
        ],
    },
    {
        "name": "surface_fill_and_trim",
        "goal": "planar 40x20 fill trimmed at x=5 by a datum plane",
        "operations": [
            {
                "op": "sketch",
                "label": "fill_profile",
                "entities": [
                    {
                        "type": "rectangle",
                        "name": "rect",
                        "min": [0, 0],
                        "max": [40, 20],
                    }
                ],
            },
            {"op": "surface_fill", "label": "patch", "sketch": "fill_profile"},
            {
                "op": "datum_plane",
                "label": "cut_plane",
                "reference": {"kind": "datum_plane", "axis": "x", "offset": 0},
                "offset": 5,
            },
            {
                "op": "surface_trim",
                "label": "trimmed",
                "target": {"kind": "quilt_feature", "label": "patch"},
                "tool": {"kind": "datum_plane", "label": "cut_plane"},
                "keep_side": "one",
            },
        ],
    },
    {
        "name": "thicken_existing_quilt",
        "goal": "thicken an existing quilt by 2 mm on an owned model",
        "operations": [
            {
                "op": "thicken",
                "label": "wall",
                "reference": {"kind": "quilt", "id": 12},
                "thickness": 2.0,
            }
        ],
    },
    {
        "name": "through_hole",
        "goal": "6 mm hole through an existing solid on two datum planes",
        "operations": [
            {
                "op": "hole",
                "label": "h6",
                "placement": {"type": "point", "x": 10, "y": 10, "z": 0},
                "reference1": {"type": "plane", "id": 3},
                "reference2": {"type": "plane", "id": 4},
                "diameter": 6.0,
                "depth": 20.0,
            }
        ],
    },
    {
        "name": "edit_dimension",
        "goal": "change one existing dimension and regenerate",
        "operations": [{"op": "set_dimensions", "values": [{"id": 12, "value": 30}]}],
    },
    {
        "name": "assemble_component",
        "goal": "place an existing managed part with a translation only",
        "operations": [
            {
                "op": "assemble_component",
                "label": "i001",
                "source_model_id": "00000000000000000000000000000000",
                "translation": [50, 0, 0],
            }
        ],
    },
)


def families() -> dict:
    return {
        "product_rules": {
            "enabled": True,
            "tool": "creo_plan_product_variant",
            "read_only": True,
            "templates": ["box_frame"],
            "units": {"length": "mm", "angle": "deg"},
            "parameters": ["length_mm", "width_mm", "height_mm", "wall_mm"],
            "scope": "Offline fixed-template planning; no connection or job submission. executable means enabled static operations and schema admission only; expected_geometry contains analytic expectations, not native measurements.",
            "native": "not_run",
            "saved_reload": "not_run",
        },
        "mass_properties": {
            "enabled": True,
            "tool": "creo_get_mass_properties",
            "scope": "Read-only volume, surface area, mass, density and centres of a part, "
            "sheetmetal part or assembly",
            "density": "Model material density first; density_g_cm3 is an explicit what-if "
            "fallback; neither means null mass",
            "parts_only": False,
            "assembly": {
                "mass": "Creo's own assembly query, reported only when the read-only occurrence "
                "scan proves every active component has a material and resolved",
                "density": "total mass over total volume with "
                "density_is_effective_average=true; not a component material density",
                "suppressed_components": "skipped as Creo skips them",
                "unproven_tree": [
                    "component_material_missing",
                    "component_unavailable",
                    "component_scan_incomplete",
                    "no_components",
                ],
            },
            "mass_value_unit": "g",
            "native_mass_unit": "Model unit; also retained in the compatibility mass_unit field",
            "mass_source": ["native", "computed_from_density", "none"],
            "job_id": "Finished execution record; the synchronous query needs no polling",
            "batch": {
                "tool": "creo_get_mass_properties_batch",
                "scope": "Same reading per model, at most 16 models per call, read serially",
                "item": "Each item is succeeded with the single-model receipt fields, or failed "
                "with error_kind invalid_request/query_failed/toolkit_busy/timeout, or skipped "
                "with reason toolkit_busy/timeout/time_budget_exhausted",
                "limits": {
                    "model_ids": 16,
                    "time_budget_seconds": {"default": 180, "min": 10, "max": 600},
                },
                "partial": "A failed item never erases the readings already taken; all_succeeded "
                "is false while any item failed or was skipped",
                "concurrency": "No added concurrency: independent requests still get the declared "
                "busy error (BUG-009)",
            },
        },
        "job_reporting": {
            "failed_stage": "Terminal failed jobs prefer the native failed_stage when reported; otherwise retain the last known stage",
            "busy": "Busy requests are rejected without a job; blocking owner fields are preserved",
            "retry_after_seconds": 5,
            "retry_interval": "Suggested interval only, not a completion estimate; inspect the owner and poll accepted jobs",
        },
        "callback_lifecycle": {
            "enabled": True,
            "tool": "creo_callback_status",
            "scope": "Stable resident Blend registration, deployment identity and bounded live readiness",
            "automatic_loading": False,
            "automatic_creo_restart": False,
        },
        "model_reconciliation": {
            "enabled": True,
            "tool": "creo_reconcile_model",
            "actions": [
                "restore_baseline",
                "accept_saved",
                "accept_live",
                "abandon_new",
                "ack_no_mutation",
                "ack_failure",
            ],
            "scope": (
                "Owned part/sheetmetal/assembly models for native recovery; drawings rejected "
                "there. Assembly restore_baseline requires a verified baseline whose recorded "
                "part_file still matches and verifies by identity (name/type/units/feature "
                "count/volume), while accept_live requires every dependency under the model "
                "output directory or the managed models root. ack_no_mutation "
                "(confirm_zero_mutation=true) is a registry-only "
                "transition from failed to ready when the failed job provably changed nothing "
                "(verified checkpoint, nothing pending, no failed rollback); ack_failure "
                "(confirm_failure_ack=true) is the metadata-only exit for a terminal "
                "failed/unknown_outcome job whose disk or component state cannot be proven, "
                "returning the model to ready without touching revision, model files or "
                "component bindings; both apply to assemblies and drawings too because they "
                "never touch component ownership"
            ),
            "original_plan_replay": False,
            "inspect_requires_creo": False,
        },
        "model_adoption": {
            "enabled": True,
            "tool": "creo_adopt_current_model",
            "actions": ["inspect", "prepare", "apply"],
            "never_saved_models": "Explicit prepare freezes a verified snapshot; apply confirms it. Later source edits are excluded.",
            "snapshot_evidence_renewal": "inspect(model_id=...) without copying; 600-second tokens",
            "scope": (
                "Explicit managed-copy adoption of the user's current window model; the source "
                "model and its file are never modified; identity from origin path, file sha256 "
                "and live inspection, never display names"
            ),
            "supported": "independent part/sheetmetal, millimeter units, no external dependencies, healthy features",
            "limits": (
                "assembly/drawing, non-millimeter units, dependent or unhealthy models are "
                "refused; each source file adopts at most once; failed adoption resolves via "
                "creo_reconcile_model abandon_new"
            ),
        },
        "file_adoption": {
            "enabled": True,
            "tool": "creo_adopt_file",
            "actions": ["inspect", "apply"],
            "maximum_paths": 20,
            "scope": "Healthy independent millimeter parts/sheetmetal; ordered independent commits; no display/window switching",
            "limits": "Duplicate origins refused; modified/ambiguous residents refused; existing_resident disk/content equality before inspection unknown; unknown stops remainder and preserves protection",
            "evidence_seconds": 600,
            "native_acceptance": "Creo 12.4 developer validation in 0.6.0; WorkBuddy was canceled and was not run",
        },
        "session_models": {
            "enabled": True,
            "tool": "creo_list_session_models",
            "scope": "Read-only session inventory, frozen pagination, unknown fields are null",
            "limit": {"default": 20, "maximum": 50, "page_bytes": 32768},
            "automatic_activation": False,
            "automatic_adoption": False,
        },
        "session_assembly": {
            "enabled": True,
            "tool": "creo_inspect_session_assembly",
            "scope": (
                "Read-only inspection of a resident session assembly by name: "
                "tree-order components with occurrence paths, normalized "
                "millimeter coordinate transforms (row-vector 4x4, translation "
                "last row) with raw matrices and real per-node unit info "
                "(null when unknown), and constraint snapshots; frozen pagination"
            ),
            "limit": {"default": 20, "maximum": 50, "page_bytes": 32768},
            "supported": "resident assemblies selected by name; nested assemblies, repeated instances, suppressed and unresolved components",
            "limits": (
                "no writes: no loading, activation, regeneration, save, adoption "
                "or managed revision; assembly editing/adoption not included"
            ),
        },
        "assembly_replay": {
            "enabled": True,
            "tool": "creo_plan_assembly_rebuild",
            "snapshot_schema_version": 3,
            "supported_constraints": [
                "mate",
                "align",
                "mate_offset",
                "align_offset",
                "insert",
                "csys",
            ],
            "scope": (
                "Read-only planning of a single-level assembly rebuild from a frozen "
                "creo_inspect_session_assembly snapshot: explicit occurrence and "
                "source-reference mappings produce ordered assemble_component then "
                "component_constraints operations for creo_execute_plan"
            ),
            "placement_semantics": (
                "fixed and default placements are replayed as their real placement "
                "operations; a constrained component is inserted fixed and then its "
                "constraints are set; a component without recorded constraints is "
                "frozen at its observed pose and labelled packaged/unconstrained"
            ),
            "binding": (
                "each assemble_component carries the source model, revision and file "
                "sha256; creo_execute_plan and the native executor re-check the binding "
                "before the source is used. The 600-second snapshot window is planning "
                "evidence, not a long-lived write authorization"
            ),
            "limits": (
                "snapshot schema 3, complete single-level assemblies and managed "
                "part/sheetmetal sources only; unknown constraint types, missing, "
                "ambiguous or nested references, older/expired snapshots, changed "
                "sources and plans over the 200-operation limit are refused; no split "
                "transactions, no FEAT-050 comparison, no new constraint types"
            ),
        },
        "planar_constraint_verification": {
            "operations": ["assemble_component", "component_constraints"],
            "types": ["mate", "align", "mate_offset", "align_offset"],
            "scope": (
                "Resolved planar references are checked in the owning assembly frame "
                "after write, regeneration, and save/reload"
            ),
            "distance_tolerance_mm": 0.001,
            "angle_tolerance_deg": 0.01,
            "failure_effect": "Fails the job and uses managed checkpoint recovery",
        },
        "disk_open": {
            "enabled": True,
            "tool": "creo_open_file",
            "scope": (
                "Read-only retrieval and display of existing on-disk .prt/.asm models "
                "(explicit or highest numeric version); never saves, erases, renames "
                "or adopts; creates no managed model"
            ),
            "supported": (
                "part, sheetmetal and complete assemblies; retrieval requires no "
                "same-name/same-type session model; assemblies additionally require a "
                "session without parts/assemblies"
            ),
            "limits": (
                "no managed revision and no adoption (use creo_adopt_current_model "
                "afterwards); incomplete assemblies fail with residues reported and "
                "missing components marked unknown; display failures are reported "
                "separately from retrieval"
            ),
        },
        "session_erase": {
            "enabled": True,
            "tool": "creo_erase_session_models",
            "actions": ["inspect", "apply"],
            "scope": (
                "Explicit, evidence-bound erasure of selected session models; the "
                "manifest erases assembly-before-components; nothing is saved and no "
                "disk file is deleted; apply holds one channel lock per job"
            ),
            "supported": (
                "saved (has origin), unmodified, non-managed part/sheetmetal/assembly "
                "session models; targets not referenced outside the manifest and free "
                "of manifest dependency cycles; the current window model may qualify"
            ),
            "limits": (
                "incomplete session enumeration refuses; managed models stay with "
                "creo_reconcile_model; no global/recursive erase, no manifest "
                "widening, mid-manifest failures stop and report without resubmitting"
            ),
        },
        "generation_reclaim": {
            "enabled": True,
            "tool": "creo_reclaim_generations",
            "actions": ["inspect", "apply"],
            "evidence_seconds": 600,
            "scope": (
                "Explicit, evidence-bound reclamation of this project's own loader "
                "and payload generation directories; no Toolkit connection, no DLL "
                "load and no automatic cleanup on startup, upgrade or status queries"
            ),
            "supported": (
                "generation directories explicitly listed by "
                "creo_callback_status.generation_inventory that are provably "
                "unreferenced in every dimension: no current/registered/runtime "
                "reference, definitive local records, consistent deployment record "
                "and flat project-owned content"
            ),
            "limits": (
                "current, registered, runtime-referenced, rollback-retained and "
                "unprovable (missing/corrupt/conflicting records) generations are "
                "kept; paths outside build/blend_loader and build/blend_callback, "
                "links/reparse points, expired evidence, changed content or "
                "references, and occupied files are refused; apply uses the shared "
                "channel lock, is idempotent per key and reports per-item "
                "reclaimed/kept/failed/unknown because deletion is not rolled back"
            ),
        },
        "registry_maintenance": {
            "enabled": True,
            "tools": ["creo_registry_health", "creo_migrate_registry"],
            "scope": (
                "Read-only registry health report (entry sizes, budget usage, "
                "corruption and migration state; 80% warning threshold) plus the "
                "explicit migration that splits legacy inline registry records and "
                "job-evidence manifests into content-addressed detail sidecars"
            ),
            "guarantees": (
                "original bytes are backed up before any rewrite; details persist "
                "before the control record publishes atomically; reruns are "
                "idempotent and interrupted migrations resume; model identity, "
                "revision and history conclusions never change; apply holds the "
                "common nonblocking channel lock and refuses active or unproven owners; "
                "targets are validated owned model_ids, never arbitrary paths"
            ),
            "limits": (
                "the unified 16 MiB read budget is never raised; neither tool "
                "connects Toolkit; migration never deletes files and leaves "
                "oversized raw native results untouched on disk; health, migration "
                "inspect and apply/replay responses use limit/cursor under a whole-response "
                "32 KiB budget, with complete counts and bounded previews"
            ),
        },
        "seed_library": {
            "enabled": True,
            "scope": "MIT native seeds bundled with source; SHA256 validation, local registration and automatic count/mode selection",
            "automatic_pairs": [
                "2/straight",
                "2/smooth",
                "3/straight",
                "3/smooth",
                "4/straight",
                "4/smooth",
                "5/smooth",
                "6/straight",
                "6/smooth",
            ],
            "available_scope": (
                "available means the seed file bytes match the published SHA256; it does not mean "
                "the current Creo session can load this seed"
            ),
            "native_load_probe": (
                "not_performed; listing and validation never connect to Creo and never trial-load "
                "a seed"
            ),
            "compatibility_evidence": (
                "external Creo 9 reported the tested seeds failing with -16; a Creo 10 "
                "three-section success is on record; the current session and the other seeds "
                "are unverified"
            ),
            "production_version": (
                "seed_build_version stays null until a traceable generation record or reliable "
                "native evidence names it for the exact seed SHA256; the UGC header token is "
                "kept as an unverified clue only"
            ),
            "limits": "no automatic download, arbitrary seed generation or mode/count conversion",
        },
        "airfoil": {
            "enabled": True,
            "scope": "symmetric NACA 00xx native sketch splines; chord/thickness/twist/origin/pivot edits preserve sketch and Blend IDs",
            "native_test": "five smooth stations, two sequential middle-section edits and edit after a native group axis pattern; STL section comparison",
            "limits": "no camber; metadata driven MCP edits, not Creo relation-driven airfoil dimensions; creation-time sample count is fixed",
        },
        "sketch_dimensioning": {
            "enabled": True,
            "modes": ["auto", "autodim", "coordinates"],
            "scope": "auto selects native coordinate dimensions on any valid sketch plane for supported undimensioned profiles with at least 10 expanded entities or coordinate/radius magnitude above 1000 mm; coordinates can be requested explicitly",
            "native_test": "19-line large-coordinate profile, R40000 12-gon, large capsule on XY and rotated/translated XZ, large YZ circle and explicit-coordinate rectangle; native sketch/solid IDs, named dimension edits, STL boundaries and save/erase/reload verified",
            "limits": "auto selects coordinates for supported unconstrained profiles of any size (line/centerline/rectangle/polyline/circle) and rejects absolute deviation (including translation) above 1e-5 mm or geometry_tolerance_mm, and rejects incomplete measurement; spline uses autodim, while b_spline/arc/ellipse try autodim first in auto mode and fall back to coordinates if autodim fails on an unconstrained coordinate-supported profile; explicit dimensioning='coordinates' supports line/centerline/rectangle/polyline/circle/arc/ellipse and exact b_spline (control points, degree, optional knots; approximation_segments is not required there) on any valid sketch plane (principal string or dictionary plane), without user dimensions/constraints; input u/v components are named after their dominant native section axis; actual geometry checked to 1e-5 mm when creating/replacing; centerlines are verified as infinite lines (direction and offset) and skewed centerlines carry no endpoint dimensions; no normalization or rigid solving; solid extrude/revolve admission checks multi-loop input for open, branched, self-intersecting, intersecting, tangent, zero-area and near-tolerance contours and rejects only confirmed cases; sketch results report analytic contour/entity counts plus the solved native section counts (any b_spline/spline/ellipse entity sets profile analysis='partial', so those counts are a lower bound: compare with native_section, never read the partial profile as a missing contour); geometry_deviation reports post-solve fidelity at SectionRegenerate and CompleteFeature with bounded samples (unavailable measurements stay null with a reason, never zero); coordinates rejects shape changes above 1e-5 mm and autodim warns above 1e-3 mm unless geometry_tolerance_mm forces a stricter or looser cap (finite positive number; bool/NaN/Inf/zero/negative rejected; an explicit cap also rejects unmeasurable geometry); in explicit coordinates a measured rigid-body translation (every named point moved by the same vector, shape residual <= 1e-9 mm) is a solver artefact rather than a shape change, so it is accepted up to 1e-2 mm and reported with accepted_rigid=true, beyond which it is rejected with the measured translation and the limit; deformed profiles are still rejected at the shape gate; sketch_shifted publishes the post-solve movement at the top level (detected, rigid, translation_mm, residual_mm, shape_deviation_mm, accepted_rigid, max_point_mm, bounded sample) and accepted_by_request marks a moved sketch that only an explicit tolerance let through; geometry_tolerance_mm is an acceptance threshold, not a solve precision; no coordinates_lenient mode; the native solver remains authoritative; not proof of every constraint or extreme shape",
        },
        "sketch_geometry_edit": {
            "enabled": True,
            "scope": "in-place geometry replacement; entity names/types/counts and sketch feature ID retained; dimensions rebuilt using auto/autodim/coordinates",
            "native_test": "large 19-line and capsule replacements preserve downstream extrusion IDs, geometry, saved reload; failed dimension assertions roll back and live refresh confirms restoration",
            "limits": "replaces prior dimensions/constraints and clears airfoil metadata; query new named dimension IDs after replacement; spline/ellipse retain the original autodim path; coordinate mode cannot be mixed with user constraints; auto on eligible replacements enforces absolute deviation including translation; geometry_deviation reports post-solve fidelity for edited sketches at SectionRegenerate and CompleteFeature under the same geometry_tolerance_mm contract as creation (an independently verified identical payload skips the re-solve and reports the deviation as explicitly unavailable); sketch_shifted reports the same rigid-translation verdict as creation, accepted_rigid marks a measured rigid move inside the 1e-2 mm limit, and accepted_by_request marks an explicit tolerance that let a moved edit through",
        },
        "feature_lifecycle": {
            "enabled": True,
            "tool": "creo_execute_plan",
            "op": "feature_state",
            "actions": ["delete", "suppress", "resume"],
            "scope": (
                "managed part/sheetmetal ordinary sketches, datums, protrusion/revolve and "
                "their cuts, group and pattern headers; explicit label/ID targets with real "
                "before/after status per target"
            ),
            "dependency_rule": (
                "every affected descendant must be listed explicitly; a missing dependency "
                "returns the dependency list and refuses the plan (native re-checks before "
                "executing; no automatic cascade)"
            ),
            "identity": (
                "deleted labels become tombstones and are never rebound; suppression keeps "
                "the feature identity; resume applies only to suppressed targets"
            ),
            "suppression_registry": (
                "intentional suppression is recorded per model/job and participates in health, "
                "saved-reload and rollback comparison; unrecorded suppression stays unhealthy"
            ),
            "limits": (
                "assembly components use remove_component; system-required objects (default "
                "coordinate system and template datums) and individually targeted group/pattern "
                "members are refused; unrecorded or inconsistent suppression is refused; "
                "native acceptance pending"
            ),
        },
        "placement": {
            "enabled": True,
            "scope": "native body FlexMove or quilt/geometry Move, in-place translation/rotation edits, local feature groups, reorder and axis patterns",
            "native_test": "body rotate/translate/edit with true solid bounding boxes; quilt rotate/translate/thicken/edit; five-section blade group pattern and later airfoil edit; save/erase/reload",
            "limits": (
                "rotation components are limited to -180..180 degrees and an out-of-range "
                "request is refused before submission with its equivalent angle (225 -> -135); "
                "both backends normalize into that same interval, so -135 and 225 address the "
                "same rotation; a failed transform reports failed_transform with backend, "
                "requested and normalized angles, translation, keep_original, reference "
                "count and a bounded selection block (requested body ids, selected surface "
                "count, model counts at op start), and the plan rolls back; a keep_original "
                "copy takes the whole current body and accumulates inside it, so an appended "
                "copy can fail when it overlaps the copies already there (reproduced on Creo "
                "12.4 in four independent models at operation index 4 with the same angle "
                "set, also reported on Creo 10; root cause identified as the copy selection "
                "semantics plus overlap/regeneration, no behavior fix shipped); the failure "
                "follows the model state and the angle rather than the copy count (the same "
                "five copies succeed when the first angle differs) and splitting the copies "
                "into smaller batches does not avoid it, so the former 'at most four copies "
                "per batch and re-reference the current body ID in the next batch' advice is "
                "withdrawn; keep one copy set in one plan and use a separate model when a "
                "fixed-original copy is needed; body branch can require Flexible Modeling "
                "license; copy-original, multiple bodies, custom csys, complex quilts and "
                "datum/curve combinations require local validation"
            ),
        },
        "drawing": {
            "enabled": True,
            "scope": "native DRW sheets, general/projected views, driving dimensions, notes, tables, edits, deletion and PDF",
            "limits": "owned part/sheetmetal snapshots; no live source update, assembly drawings, sections, detail views, GD&T or automatic BOM",
        },
        "datums": {
            "enabled": True,
            "scope": (
                "coordinate systems and dimensioned point arrays in addition to planes "
                "and axes; datum_plane also accepts the three-point form "
                "{kind:'through_points',points:[label_a,label_b,label_c]} with three "
                "distinct single-point datum_points labels created earlier in the same "
                "plan (mutually exclusive with angle/axis/nonzero offset; external "
                "{thru_points:[...]} spellings must be converted first)"
            ),
            "native_test": "XYZ offsets 10/20/30, Z rotation 45 degrees, native origin check and offset dimension edit",
            "limits": (
                "three-point planes: offline contract and native judgment implemented "
                "(FEAT-053); Creo 12.4 live acceptance pending; no four-point fitting "
                "and no guessing a point out of a multi-point feature"
            ),
        },
        "surface_solid": {
            "enabled": True,
            "scope": (
                "surface-mode extrude and revolve (including partial angles), planar fill, "
                "thicken and solidify; surface sweep and axis pattern on surface features "
                "are available within their existing operation contracts"
            ),
            "native_test": "20 x 10 fill, symmetric thickness 2 to 3; plane cut of a cube",
            "limits": (
                "closed-quilt solidification is published (measured volume plus rollback "
                "on an open quilt); thin offset on a trimmed quilt stays gated because "
                "surface_trim offset_mm removes a band instead of moving the cut; "
                "curved-quilt thicken side options beyond the published symmetric case "
                "need further native validation"
            ),
        },
        "geometry_import": {
            "enabled": True,
            "tools": ["creo_execute_plan"],
            "scope": (
                "import one STEP or IGES file into its own new part: the plan holds exactly "
                "the import_geometry operation and no model_id, and the native route calls "
                "ProIntfimportModelWithOptionsMdlnameCreate with PRO_IMPORTREP_MASTER instead "
                "of copying the part template; the imported part is what a later "
                "assemble_component places (Creo 12.4.0.0 live-verified 2026-11-13)"
            ),
            "native_test": (
                "2026-11-13 live on Creo 12.4.0.0: STEP import create_code=0, one closed "
                "quilt 440.0 mm2, feature_count=2, saved and reloaded; IGES import "
                "create_code=0, six quilts 1540.0 mm2, saved and reloaded; both in mm with "
                "profile_source=creo_default"
            ),
            "limits": (
                "one import per plan and never into an existing model, because the documented "
                "call creates the model itself and returns it as the job's model; profile is "
                "optional and defaults to Creo's own import settings (a passed profile stays "
                "valid for the whole session, so the receipt reports profile_source); the "
                "imported model must be millimetres or the existing unit gate refuses it after "
                "the import; a licence refusal keeps its own code (PRO_TK_NO_LICENSE); quilt "
                "closure is only reported when exactly one quilt exists; Creo 10 and "
                "pure-surface (non-solid) imports are not live-verified, and the operation "
                "cannot continue in the same plan with other features"
            ),
        },
        "surface_chain": {
            "enabled": True,
            "tools": [
                "creo_surface_loft",
                "creo_surface_trim",
                "creo_project_curve",
                "creo_surface_offset",
                "creo_quilt_merge",
                "creo_measure_surface_group",
                "creo_surface_round",
                "creo_measure_surface_curvature",
            ],
            "scope": (
                "boundary-blend a quilt from 2-32 sketch sections (two ruled, three or more "
                "one smooth blend) with optional guides, plus curve/edge ids and one "
                "convergence point as FEAT-065 M3 inputs (Creo 12.4.0.0 live-verified) and "
                "tangency to the face next to an edge first/last section (FEAT-065 M4) "
                "(measured area and closure); trim one quilt "
                "with another quilt, a datum-plane label or a curve geometry id; "
                "project one curve geometry id onto one quilt along an explicit "
                "direction reference; offset one quilt along its surface normal; "
                "join two touching or intersecting quilts into the target quilt with a "
                "measured result area and closure; "
                "measure a group of quilts read-only (open boundary edges, seam gap "
                "against a tolerance, overlapping face area); round the edge shared by "
                "two member faces of one quilt with a constant radius; analyse the "
                "principal curvature of member faces and the normal angle across a "
                "shared edge numerically. There is no zebra-stripe or curvature-comb "
                "visualization API; the numeric analysis is the equivalent deliverable"
            ),
            "native_test": (
                "surface_trim: 800 mm2 fill cut to 600 mm2 with a measured retained side; "
                "quilt_merge: 2026-11-08 live 2x400 mm2 adjacent fills joined into the "
                "target quilt at 800.0 mm2, open, saved and reloaded, then thickened 2 mm; "
                "project_curve: 40.000 mm and 25.133 mm measured projections, saved and "
                "reloaded; surface_offset: 40x20 fill offset 5 mm on both sides, "
                "3999.9999999999995 mm3 and 4.999999999999999 mm measured distance; "
                "surface_round: 2026-11-08 live quilt 1200 mm2 R3 on adjacent faces "
                "-> 5 faces / 1187.1238898038469 mm2, open, no solid, saved and reloaded, "
                "with a non-adjacent pair failing regeneration and rolling back; "
                "surface_curvature: 2026-11-08 live planar 0.0 1/mm, R8 sphere "
                "0.125 1/mm / 8.0 mm, 90-degree G1 between adjacent planar walls, "
                "revision unchanged"
            ),
            "limits": (
                "quilt merge joins exactly two touching or intersecting quilts and reports "
                "the target quilt it grew in place (result_quilt_source="
                "retrimmed_target_quilt); consumed_quilt_ids names the inputs the JOIN "
                "consumed and merged_surface_ids lists the feature's own surfaces, but "
                "inspect_model still enumerates kernel residue of a consumed quilt rather "
                "than filtering it; the consumed tool quilt is no longer measurable, "
                "intersect, three or more participants, chained merges and closed shells are "
                "not published; a merge, mirror or trim result label resolves to the quilt the native operation measured and the receipt publishes its quilt_id; when no unique result quilt can be identified the reference is refused with candidate guidance instead of guessing (older builds failed resolving the merge feature label with ProFeatureGeomitemVisit -4, 2026-11-10 Creo 10 report); in-plan reuse is live-verified on Creo 10.0.0.0 (a merge result consumed by solidify at the expected volume), while a later job has no in-memory alias and must use the published quilt_id or keep referencing the original target quilt label; "
                "the closed non-planar boundary fill stays gated "
                "(UNAVAILABLE_OPERATIONS; the former single-direction candidate "
                "regenerated to no quilt; DEV-078's four-boundary two-direction route "
                "is offline only and rejects unsupported parameter reversals); surface_loft is "
                "2-32 single-curve sections (two = ruled straight, three or more = one smooth "
                "blend through every section) with an optional second direction of 2-8 guide "
                "sketches that bend the surface; one guide alone does not regenerate; curve/"
                "edge id inputs and a first/last convergence point (FEAT-065 M3) are "
                "live-verified on Creo 12.4.0.0; boundary continuity is 'tangent' only, at a "
                "first/last edge section with one adjacent face (FEAT-065 M4; curvature, "
                "normal and guide boundaries are refused before a job); no "
                "closed or solid output; conditional on the PRO_E_BNBLN_* element ids in the "
                "worker build SDK; intersection with a trim tool does not by itself prove "
                "that it partitions a removable region (a closed loop or connections to "
                "target boundaries may be needed); intersection curves are not measured; "
                "surface_trim offset_mm stays "
                "refused; surface_offset returns the offset wall, not a standalone offset "
                "quilt; it can add solid volume, and target_quilt_id names the source quilt; "
                "surface_trim publishes result_quilt_id only after ProQuiltInit accepts the "
                "retained quilt, and result_quilt_handle separates that handle from the "
                "measurement status; consecutive trim/save-reload reuse of that handle still "
                "needs live evidence; "
                "trimmed quilt feature-label reuse and curved-quilt offset measurement "
                "have no published geometric guarantee; "
                "the closure block is the raw ProQuiltVolumeEval receipt (available / "
                "quilt_is_open / quilt_volume_eval_failed) and proves neither edge-paired "
                "topology nor solidifiability - a failed volume query did not stop a "
                "single-step solidify committing, and a single fill face can report "
                "closed=true; use creo_measure_surface_group for topology; when "
                "surface_boundary_fill is unavailable, seal an open shell with a closed "
                "double-b_spline sketch + surface_fill + quilt_merge in separate jobs "
                "(documented route, external Creo 10 evidence only); "
                "creo_measure_surface_group reports member seams (state closed/open/"
                "micro_gap/overlap) while boundary_closed tells whether the whole group "
                "boundary is a shell; its overlap area is a tessellation estimate, gaps "
                "wider than gap_search_mm are not quantified, and the join judgement is "
                "sampled boundary geometry rather than a kernel boolean; overlap sampling "
                "is bounded and can be unavailable for larger or finely tessellated groups - "
                "the status then keeps overlap_area_mm2 null while reporting the sample "
                "budget, tests required/attempted, coverage and observed containment errors; "
                "its open_edge_records (edge_id, surface_id, quilt_id, length_mm, "
                "endpoints_mm; at most 32, with open_edge_records_total and "
                "open_edge_records_truncated) are the quilt edge id channel for "
                "surface_loft {kind:'edge',id:N} (FEAT-065 T1b, live-verified on Creo "
                "12.4.0.0: the 8 open edges of two strips listed and two top edges picked by "
                "endpoint); "
                "an unknown unit scale keeps their mm values null; "
                "surface_round is one constant radius on two member faces of one quilt "
                "(no variable radius, edge chain, transitions or solid target) and the "
                "kernel decides whether the two faces share an edge; "
                "creo_measure_surface_curvature is numeric only (principal curvature, "
                "radius and direction per UV sample, plus the normal angle across a "
                "shared edge); Creo Toolkit has no zebra-stripe or curvature-comb "
                "visualization API, so no image is produced and samples outside the trimmed "
                "face are counted rather than measured; the per-sample rows are omitted from the "
                "default tool response to stay within the MCP result budget (include_samples=true "
                "returns every point, and the job record always keeps them)"
            ),
        },
        "boolean_bodies": {
            "enabled": True,
            "native_test": "overlapping cubes: union 1500, difference 500 and intersection 500 mm3",
            "limits": "multi-target/tool lists and keep_tools require further native validation; Creo initial body ID -5778 is supported when active (other negative IDs and empty/inactive bodies are refused); sheetmetal-to-solid fusion is unverified even with positive IDs",
        },
        "rib": {
            "enabled": True,
            "scope": "native profile rib driven by an open sketch",
            "limits": "sketch must intersect the solid; material side depends on sketch direction; trajectory ribs are not wrapped",
        },
        "udf": {
            "enabled": True,
            "scope": "local UDF metadata and independent native feature-group placement with reference/variable-dimension mapping",
            "limits": "part/sheetmetal only; exact reference prompts required; assembly UDFs, quadrants, variable parameters and manufacturing UDFs are not wrapped; libraries supplied by user",
        },
        "mirror": {
            "enabled": True,
            "native_test": "whole solid about a principal datum plane",
            "scope": "whole-part, geometry or datum references; the receipt names the native "
            "implementation path and the reference kinds",
            "limits": "PRO_E_MIRROR_REF_ITEMS (ProMirror.h) takes curves, axes, quilts, datum "
            "planes, coordinate systems, points or the whole part, so a feature reference is "
            "refused by the contract and again natively before creation: a feature item hung "
            "Creo's main thread twice on 2026-11-21 (10.0.0.0). Mirror the part with "
            "kind=part, or a surface feature's quilt with kind=quilt; feature subtrees are not "
            "expanded by Python and no geometry is synthesised",
        },
        "surface_offset": {
            "enabled": True,
            "tool": "creo_surface_offset",
            "scope": "offset one quilt along its surface normal by a measured distance and direction",
            "native_test": "40x20 fill offset 5 mm on both sides (2026-11-05 live): the "
            "offset wall measures 3999.9999999999995 mm3 on the positive and on the negative "
            "side (area times distance, oracle 800 x 5), the measured distance volume over area "
            "is 4.999999999999999 mm against the requested 5 mm, and both jobs report "
            "saved_file_reloaded_and_verified=true",
            "limits": "one quilt, one explicit side - the receipt direction is the requested "
            "side and the z sign is not read back from the geometry; the documented "
            "normal-to-surface offset method; the result is the offset wall, not a standalone "
            "offset quilt; it can add solid volume, and target_quilt_id names the source "
            "quilt, not a new downstream quilt; a closed quilt is not required. Measured "
            "distance is available only under offset_distance_status's planar/empty-model gate",
        },
        "surface_loft": {
            "enabled": True,
            "availability": "sdk_conditional",
            "sdk_requirements": [
                "PRO_E_BNBLN_CURVES",
                "PRO_E_BNBLN_1DIR",
                "PRO_E_BNBLN_2DIR",
                "PRO_E_BNBLN_DIR_CURVES",
                "PRO_E_BNBLN_TAN_COND",
            ],
            "enabled_semantics": "registered implementation; not verification of the loaded worker SDK",
            "tool": "creo_surface_loft",
            "sdk_requirement": (
                "PRO_E_BNBLN_* boundary-blend element ids in ProElemId.h; an SDK without them "
                "returns SURFACE_LOFT_SDK_UNAVAILABLE"
            ),
            "scope": (
                "one boundary-blend quilt from 2-32 MCP-owned section sketches, in the "
                "submitted order, optionally guided by a second direction of 2-8 guide "
                "sketches: exactly two sections are ruled (interpolation=straight), three or "
                "more are one smooth blend through every section (interpolation=smooth), and "
                "guides bend the surface through their curves. FEAT-065 M3 (Creo 12.4.0.0 "
                "live-verified 2026-11-11): sections and guides may also name an existing "
                "curve or edge id, and the first or last section may be one convergence point. "
                "FEAT-065 M4: an edge section at the first or last position may be made "
                "tangent to the face next to it (boundary_conditions)"
            ),
            "limits": (
                "2-32 sections and, optionally, 2-8 guides (PRO_E_BNBLN_2DIR); straight is "
                "exact only with two sections and is refused above two (the kernel fits one "
                "smooth blend through 3+ sections: 40/60/40 mm measured 2101.25 mm2, not the "
                "2000.00 a piecewise ruled surface would give); each sketch section and each "
                "sketch guide must own exactly one non-composite curve (two curves are accepted "
                "for a closed section profile only), no sketch may be repeated across sections "
                "and guides, and one guide alone never regenerates (2DIR needs two curves; "
                "measured 2026-11-11); whether a guide crosses every section is the kernel's "
                "decision and a non-crossing guide fails regeneration instead of being "
                "silently dropped; no closed surface, control points or solid output, and "
                "continuity is 'tangent' only (below); section order is the loft direction; "
                "closure comes from "
                "ProQuiltVolumeEval, so an open quilt is reported open instead of assumed. "
                "FEAT-065 M3 input forms, live-verified on Creo 12.4.0.0 on 2026-11-11 (40 live "
                "checks): {kind:'curve',id:N} and {kind:'edge',id:N} as one-item sections or "
                "guides (one geometry item per holder, no multi-edge chain per slot) - two "
                "strip top edges plus two sketch guides bridged at 800 mm2 with a 0 mm seam "
                "gap, a projected-curve "
                "section ruled at 1131.37 mm2, three YZ ellipse sections along X at "
                "2075.38 mm2 - and one convergence point {kind:'point',id:N} / "
                "{kind:'datum_point_feature',label} at the first or last section only (never a "
                "guide, never two points); the point is placed with "
                "PRO_CURVCOLL_ADD_POINT_INSTR, which Probbl.h does not document for a chain "
                "holder, and the same ellipses closed at x = 60 mm measured 2415.05 mm2; each "
                "source record carries live_verified=true and unverified_input_forms stays in "
                "the receipt for compatibility, always empty; a bad id fails with "
                "SURFACE_LOFT_INPUT_REJECTED and failed_loft_input; creo_inspect_model "
                "enumerates solid edges only, so read a quilt edge id from "
                "creo_measure_surface_group group.open_edge_records (FEAT-065 T1b, "
                "live-verified in the same run). FEAT-065 M4 boundary_conditions "
                "([{boundary: first_section|last_section|first_guide|last_guide, condition: "
                "free|tangent|curvature|normal}], at most 4, each boundary once): 'tangent' is "
                "published at first_section/last_section only, where that section is an edge "
                "{kind:'edge',id:N} with a single adjacent face (a quilt boundary edge); the "
                "direction is fixed - the surface leaves the boundary continuing the "
                "neighbouring face, with no flip or weight (PRO_E_BNBLN_TAN_COND_TYPE 2 and "
                "PRO_E_BNBLN_STRETCH -1 at the first / +1 at the last section, kernel-default "
                "connect chain); measured on Creo 12.4.0.0: two vertical 40x10 mm strips 20 mm "
                "apart bridged by their top edges became an arch of 982.5888 mm2 (bounding box "
                "z up to 15.12 mm) with G1 0.0 deg at both seams, where the free bridge is the "
                "800 mm2 plane at 90 deg, and reversing one strip's sketch gave the same "
                "result; 'free' is accepted on any boundary and writes nothing; 'curvature' is "
                "refused because the candidate value 3 kept a 90 deg seam (915.99 mm2), "
                "'normal' because value 4 built the same plane as free, and a non-free guide "
                "boundary because guide boundaries were not measured; these are refused before "
                "a job, and the native executor repeats the refusal "
                "(SURFACE_LOFT_BOUNDARY_CONDITION_REJECTED, reason not_available) before any "
                "feature exists"
            ),
            "unavailable_fields": {
                key.split(".", 1)[1]: reason
                for key, reason in UNAVAILABLE_FIELDS.items()
                if key.startswith("surface_loft.")
            },
        },
        "surface_round": {
            "enabled": True,
            "tool": "creo_surface_round",
            "scope": (
                "one constant round on the edge shared by two member faces of one quilt "
                "(PRO_FEAT_ROUND with PRO_ROUND_REF_SURF_SURF); the result stays on the "
                "same quilt and reports its measured face count, area and closure"
            ),
            "native_test": (
                "2026-11-08 Creo 12.4.0.0 probe through the generic round tree: a 4-face "
                "open quilt of 1200 mm2, R3 on adjacent face pairs (68,66) and (66,64), "
                "became 5 faces / 1187.1238898038469 mm2 (analytic 1200-60+pi/2*3*10) with "
                "saved_file_reloaded_and_verified=true; a non-adjacent pair failed "
                "regeneration and rolled back to 4 faces / 1200 mm2"
            ),
            "limits": (
                "exactly two member faces of one quilt with one shared edge, one constant "
                "radius, one reference set; the kernel decides adjacency (H08 measured the "
                "non-adjacent pair failing regeneration and rolling back); no variable "
                "radius, full/chordal/through-curve radius, edge chain, transitions, "
                "multi-set or solid target; edge-chain input is not accepted: the route takes "
                "face pairs only (quilt edge ids are now listed by creo_measure_surface_group "
                "open_edge_records, but no edge-chain round route is proved); "
                "the quilt result is open by nature, so no solid volume is expected"
            ),
        },
        "surface_curvature": {
            "enabled": True,
            "tool": "creo_measure_surface_curvature",
            "scope": (
                "read-only numerical curvature analysis of one or two member faces of one "
                "quilt: principal curvatures (1/mm), curvature radii (mm), principal "
                "directions, the aggregate max absolute curvature and min curvature radius, "
                "and, for two faces sharing an edge, the normal angle across that edge"
            ),
            "native_test": (
                "2026-11-08 Creo 12.4.0.0 live: a planar 40x20 surface_loft quilt measures "
                "0.0 1/mm max absolute curvature with 144/144 samples inside the face and "
                "min_curvature_radius_mm=null (reason zero_curvature); an R8 revolve sphere "
                "measures 0.12500000000000003 1/mm and 7.999999999999998 mm; two adjacent "
                "planar walls report g1_max_angle_deg=90.0 over 1 shared edge and 17 samples "
                "with within_g1=false; revision stays unchanged (read-only)"
            ),
            "limits": (
                "no zebra-stripe or curvature-comb image: Toolkit has no such API, and the "
                "numeric analysis is the declared equivalent; every sample is a UV cell "
                "centre checked with ProSurfaceUvpntVerify, so a trimmed face reports only "
                "samples inside its contour (outside samples are counted, not measured); a "
                "failed curvature query is a count plus a reason, never zero curvature; an "
                "unknown unit scale keeps 1/mm and mm values null; the G1 angle is the angle "
                "between the two kernel normals as returned (an opposite-wound neighbour "
                "would read near 180 degrees and must be confirmed live); the 0.5 degree "
                "threshold only sets within_g1 and never replaces the measured angle; only "
                "the dedicated read-only tool keeps the revision unchanged - the generic "
                "execute_plan entry is a write job and saves the model"
            ),
        },
        "sweep": {
            "enabled": True,
            "native_test": "straight and quarter-circle trajectories; solid add, straight cut, open surface followed by thicken, symmetric thin; named section edits, native ID preservation, analytic volume checks, save/erase/reload and failed-assertion rollback on 2026-10-11; the surface mode was measured on 2026-11-05 with a 40x20 profile swept 20 mm: open 2400.000 mm2 (2*(40+20)*20), capped 4000.000 mm2 (walls plus two 40x20 caps) and the capped quilt solidifies to 15999.999999999998 mm3 (40*20*20)",
            "limits": "constant section (ProSweep.h documents no variable or multi-section sweep), so a boundary blend through several sections is not reachable through this route; compound trajectories, all frame options and intersections still require local validation; thin is total symmetric wall thickness",
        },
        "draft": {
            "enabled": True,
            "native_test": "constant unsplit planar-wall draft and Creo 10 cylindrical boss with solid-face, datum-plane and datum-axis neutral/pull references, signed angles, both flip orientations and save/reload",
            "direction": (
                "flip=false writes PRO_DIRECTION_FLIP_ALONG (direction_flip_code=1, effective_flip=false) "
                "and flip=true writes PRO_DIRECTION_FLIP_AGAINST (direction_flip_code=-1, effective_flip=true); "
                "on a +Z boss with positive angle, solid bottom surface flip=false removes material while XY datum_plane flip=false adds material on Creo 10; "
                "check material_effect ('added'/'removed'/'unchanged'/null) and material_delta_mm3"
            ),
            "limits": "variable, split and rib draft are not high-level tools",
        },
        "loft": {
            "enabled": True,
            "tool": "creo_loft",
            "scope": "direct native solid Blend from independent MCP-owned XY sketches ordered by increasing Z; create in a feature plan or append to an owned part",
            "interpolation": ["straight", "smooth"],
            "section_count_input_range": [2, 20],
            "runtime_admission": {
                "status": "requires_ready_callback",
                "check_tool": "creo_callback_status",
                "callback_free_tool": "creo_new_loft_part",
            },
            "native_test": "3/4/6 straight and smooth factory cases; append 3/smooth to an existing saved base, preserve native IDs, edit dimensions, verify all-section STL, save/erase/reload and failed-append rollback with a live refresh",
            "limits": "solid add into the default body only; no cut/surface/new_body, nonparallel sections or endpoint tangency/curvature controls; surface output belongs to creo_surface_loft (2-32 sections plus optional guides), and mode='surface' is refused before a job; native reports support Chinese/English Creo; requires explicit resident callback initialization before modeling under every loader policy, otherwise rejects before DLL load; modeling never loads DLLs or changes security policy",
            "callback_setup": "creo_capabilities.direct_blend_callback lists the generated registry_file; load/start it via Creo Auxiliary Applications and review the DLL prompt before modeling",
        },
        "loft_seed": {
            "enabled": True,
            "tool": "creo_new_loft_part",
            "target_scope": "new_part_only",
            "scope": "new native part ONLY (new_part_only; cannot append to an existing model) by rebinding an automatically selected bundled seed or explicit compatible seed to new XY sketch/airfoil sections",
            "section_count_input_range": [2, 20],
            "seed_section_count_must_match": True,
            "callback_required": False,
            "geometry_verification": "Confirms requested sketch dependencies, positive solid volume and end-plane coverage before saving and after reload. Use assertions.volume_mm3 and assertions.bbox_mm for independent numeric targets.",
            "interpolation": ["straight", "smooth"],
            "tested_section_count_mode_pairs": [
                {"section_count": 2, "interpolation": "straight"},
                {"section_count": 2, "interpolation": "smooth"},
                {"section_count": 3, "interpolation": "straight"},
                {"section_count": 3, "interpolation": "smooth"},
                {"section_count": 4, "interpolation": "straight"},
                {"section_count": 4, "interpolation": "smooth"},
                {"section_count": 5, "interpolation": "smooth"},
                {"section_count": 6, "interpolation": "straight"},
                {"section_count": 6, "interpolation": "smooth"},
            ],
            "missing_bundled_combinations": [{"section_count": 5, "interpolation": "straight"}],
            "mode_verification": "requested interpolation must match the saved seed; native PRO_FEAT_INFO checked before save, after parameter edits and after reload",
            "compatibility_evidence": (
                "external Creo 9 reported the tested seeds failing with -16; a Creo 10 "
                "three-section success is on record; the current session and the other seeds "
                "are unverified"
            ),
            "load_failure_diagnosis": (
                "a failed native load keeps the original API, error code and stage plus the seed "
                "identity, SHA256 and the session release; the error alone never names the cause"
            ),
            "native_test": "five-section smooth rectangles and NACA 0012 spline airfoils; middle sketch/plane edits; saved reload, all-section STL checks and failed-assertion rollback; two-section rectangle/circle/triangle regression",
            "limits": "new_part_only (no existing-target insertion); bundled seeds cover 2/3/4/6 straight and 2/3/4/5/6 smooth ONLY (5/straight is not bundled; 7-20 sections require an explicit compatible seed_file and seed_feature_id), Chinese/English Creo; XY sketches with strictly increasing Z offsets; no seed section insertion/removal, mode conversion, cut/surface or tangency controls; use direct creo_loft for existing-target insertion; seed endpoint settings and datums are inherited; input range is not proof that every count/profile is tested; free endpoints may produce identical geometry with two sections",
        },
        "sheetmetal": {
            "enabled": True,
            "scope": (
                "first flat wall (thin extrusion + native conversion), native rectangular "
                "unattached planar wall with in-place resize, attached flange, unbend, "
                "bend-back and flat pattern"
            ),
            "native_test": "40 x 30 x 1 wall, 90 degree flange with R2/R3 bend, followed by unfolding and refolding; 100 x 60 x 1 native planar wall resized to 120 x 80 (live 2026-11-04, 6000 -> 9600 mm3, same feature id, saved reload verified)",
            "limits": (
                "sheetmetal modeling starts from creo_new_sheetmetal; wait for its terminal "
                "state before wall/flange operations, because execute_plan without model_id "
                "creates a plain part by default and never converts an existing solid part into "
                "sheetmetal implicitly; creo_sheetmetal_wall keeps the thin-extrusion + "
                "conversion first wall; creo_sheetmetal_planar_wall is the native unattached "
                "planar wall (Fill tree with the sheetmetal branch) and therefore needs "
                "creo_new_sheetmetal(template='native_planar'), an empty model and a closed "
                "rectangle - this direct first-wall route needs the sheetmetal subtype, so a "
                "solid-template part refuses it natively; it also creates the feature "
                "<label>_sk, so both names are protected against duplicates, tombstones and "
                "same-plan collisions; direction=positive grows toward the reported sketch "
                "normal (verified on XY/XZ/YZ and negative), the gauge is read back from the "
                "wall body and re-read from the saved file before a resize, and the signed "
                "envelope plus volume must match the request; its resize drives the driving "
                "sketch's coordinate dimensions, so it keeps the feature id and gauge but "
                "refuses unknown labels, walls from other operations and walls with downstream "
                "dependencies (a flange on the wall counts); a flange attaches to a native "
                "first wall (live 2026-11-04) but non-rectangular sections remain unverified; "
                "creo_sheetmetal_flange relief is bend-end relief only (PRO_E_SMT_BEND_RELIEF per "
                "bend end, 'none' or 'rectangular' with explicit width/depth), not corner relief "
                "or a miter, and it is not proven to resolve corner overlap; a flange whose "
                "attach-edge ends abut existing bends fails to regenerate (live verified "
                "2026-10-30: a free full edge attaches, an edge shortened at even one end by a "
                "previous bend fails and rolls back), so it is refused before create by the "
                "adjacent_bend_ends guard, which is a pre-create refusal rule and not a geometry "
                "or miter proof and still applies when relief is supplied; passing miter_cuts "
                "{width, offset} is the only release - it adds the flange's native "
                "PRO_E_SMT_MTR_CUTS section (literal BLIND width/offset in model units) so "
                "Creo cuts the end overlap; the four-wall box route is live verified "
                "2026-11-06 (four walls built, saved and reloaded), while the cut amount "
                "produced by a given width/offset is not yet quantified; forms, hems and "
                "jogs are not high-level tools; attaching solid material (bosses, louvers, "
                "grilles, hinges, door ears) to an existing sheetmetal body is unsupported: "
                "on Creo 12.4.0.0 (2026-11-07) an extrude add and a boolean union with the "
                "sheetmetal body as target both return ProFeatureWithoptionsCreate=-1, and "
                "the reverse union builds but consumes the sheetmetal body (all wall contours "
                "answer ProSmtedgeContourGet=-8 and unbend fails), so new_body=true stays a "
                "separate solid body instead of a one-piece sheetmetal result; Creo 10 has "
                "never been tried"
            ),
        },
        "assembly": {
            "enabled": True,
            "orientation_input": (
                "XYZ Euler degrees (X then Y then Z), or exclusive nested 3x3 rotation_matrix; "
                "row vectors local to parent, translation separately in mm; finite real numbers, "
                "orthogonality and determinant +1 within rotation_tolerance (default 1e-7), "
                "without repair or transpose. rotation_convention='column' declares "
                "p_parent(column) = R * p_local(column) + T and is transposed exactly once by the "
                "native entry; the gate always measures the canonical row form, and both the "
                "request matrix and its convention are echoed unchanged"
            ),
            "rotation_tolerance": (
                "optional positive linear tolerance on rotation_matrix orthogonality and "
                "determinant, at most 1e-7 (the measured Creo 10 boundary); a tighter value is "
                "honoured and the input is never repaired or orthonormalized. Python and the "
                "native helper apply the same effective value; a larger tolerance would admit a "
                "pose the kernel rejects with code -2 and is refused"
            ),
            "matrix_validation": "offline production helper and MCP/schema regression; live placement/save-reload unverified",
            "native_test": "part snapshots, rigid placement, removal, 3 datum-plane align constraints and 20 mm offset",
            "component_changes": (
                "jobs with component operations report a bounded manifest component_changes "
                "summary (also present in detail=compact): committed (real native feature "
                "identities; moved carries queried from/to transforms), rolled_back ONLY "
                "with native rollback_succeeded evidence (requested intents only, never "
                "reported as effective), no_effect (busy rejection/worker not started or "
                "native model_unchanged; nothing attempted or mutated) or unknown_outcome "
                "(empty; failed-after-execution without confirmed rollback, or unconfirmed "
                "outcome; protection retained)"
            ),
            "constraint_names": (
                "list_components constraints keep the numeric SDK type code and add type_name "
                "from the same mapping as inspect_session_assembly; unknown codes stay numeric "
                "with type_name unknown"
            ),
            "pipeline": "single execute_plan job inserts multiple components (distinct labels per occurrence); official rebuild pipeline: docs/ASSEMBLY_REBUILD.md with examples/assembly_rebuild_pipeline.json",
            "limits": "MCP-owned part/sheetmetal/assembly sources (drawings refused); a nested assembly is copied like a part, so its own file and components are never moved; source edits do not update snapshots (regenerate via remove + re-assemble or rebuild); mate/insert/csys/default placement need further validation",
        },
        "assembly_appearance": {
            "enabled": True,
            "tool": "creo_recolor_assembly",
            "op": "recolor_assembly",
            "modes": ["automatic", "explicit"],
            "scope": (
                "Paint managed single-level assembly components by part family at the "
                "component level (source part bytes unchanged): automatic grouping by the "
                "component binding's unique source_model_id (palette keys may be those ids or "
                "a unique component label), an explicit family table of component "
                "labels/feature IDs, or random=true for deterministic per-family colors; RGB "
                "colors are finite 0..1 triples, booleans refused; dry_run previews grouping, "
                "family counts, unmatched entries and the resolved palette from persisted "
                "registry data in 32 KiB pages without Toolkit, jobs or revision changes"
            ),
            "guarantees": (
                "one validation path for the tool and the execute_plan recolor_assembly "
                "operation; family tables refuse duplicated or omitted components and "
                "plan-created component references; writes require a complete palette and "
                "always save once with the revision advancing exactly one; job results "
                "report painted/unmatched/family counts, both per-component readbacks "
                "(write and save/erase/reload), the component appearance baseline and its "
                "source (checkpoint or adopted_live); explicit refresh_baseline adopts the "
                "live pre-job appearance as the rollback baseline for checkpoints saved "
                "before the appearance field existed, and dry_run returns next_action with "
                "that call"
            ),
            "limits": (
                "managed single-level assemblies with a verified checkpoint of at least one "
                "component only; non-assembly models, assemblies without components, stale "
                "expected_revision and ambiguous labels are refused; old checkpoints without "
                "a component appearance baseline are refused unless refresh_baseline=true is "
                "passed explicitly (that flag relaxes only the missing appearance field, "
                "never component identity); automatic grouping refuses missing or conflicting "
                "sources and demands an explicit family table; entries matching no component "
                "stay unmatched instead of being guessed; face-level painting, standalone "
                "parts, nested/external assemblies, non-RGB appearance properties and "
                "queueing/scheduling beyond the single busy-rejecting Toolkit channel are out "
                "of scope; component readback values and on-screen display are verified "
                "separately; live Creo acceptance has NOT been performed for refresh_baseline "
                "yet"
            ),
        },
    }
