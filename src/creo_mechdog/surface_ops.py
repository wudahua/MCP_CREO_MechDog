"""Surface-chain operation schemas (FEAT-039 S02/S03/S04/S07).

The trim, merge and projection operators live here instead of inside the
general schema module, so the package owns the surface chain by name. The
shared primitives come from creo_mechdog.schema_base; the general module
re-exports these classes, so both import paths stay valid.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from creo_mechdog.schema_base import Label, Positive, StrictModel


def quilt_reference_problem(
    reference: Any, *, allow_datum_plane: bool, allow_curve: bool = False
) -> str | None:
    """FEAT-039/S02: describe why a surface_trim reference is unusable.

    Quilt references are always accepted; a datum plane and a curve are
    trimming tools only, so they are opt-in. A curve is passed as the geometry
    item (`{kind: curve, id: N}`) because that is what the use-curve tree
    consumes; a curve feature label would name the parent sketch instead.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind == "quilt":
        value = reference.get("id")
        if type(value) is not int or value < 0:
            return "quilt reference requires a nonnegative integer id"
        return None
    if kind == "quilt_feature":
        if not isinstance(reference.get("label"), str) or not reference["label"]:
            return "quilt_feature reference requires a label"
        return None
    if allow_datum_plane and kind == "datum_plane":
        if not isinstance(reference.get("label"), str) or not reference["label"]:
            return "datum_plane reference requires a label"
        return None
    if allow_curve and kind == "curve":
        value = reference.get("id")
        if type(value) is not int or value < 0:
            return "curve reference requires a nonnegative integer id"
        return None
    return f"unsupported kind '{kind}'"


class SurfaceTrimOp(StrictModel):
    """High-level surface trim (FEAT-039/S02).

    The target is one quilt; the tool is one quilt, one datum plane or one
    curve. Bodies and multiple tools are refused before a job is queued. For a
    curve tool ProTrim.h defines the two sides along the curve direction, which
    the 2026-11-04 probe measured: reversing the curve swaps the retained
    region, so ``kept_side_basis`` reports ``side_reference=curve_direction``.
    ``keep_side``
    is ``one``/``two`` only — its physical direction is read back through
    ``kept_side_basis`` instead of being named after a GUI view.
    """

    op: Literal["surface_trim"]
    label: Label
    target: dict[str, Any]
    tool: dict[str, Any]
    keep_side: Literal["one", "two"]
    # FEAT-039/S07: the documented thin-trim route offsets the trimming
    # surface by a distance before it cuts (ProTrim.h §4.1). The distance and
    # its direction are given explicitly, never derived from a GUI view.
    offset_mm: Positive | None = None
    offset_side: Literal["one", "two"] | None = None

    @model_validator(mode="after")
    def valid_references(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_trim target {problem}")
        problem = quilt_reference_problem(self.tool, allow_datum_plane=True, allow_curve=True)
        if problem:
            raise ValueError(f"surface_trim tool {problem}")
        # The same reference object cannot be both sides of the trim. Two
        # different spellings of one quilt are caught at run time by the native
        # resolver, which already refuses ambiguous quilt references.
        if self.target == self.tool:
            raise ValueError(
                "surface_trim target and tool must be distinct quilts; one quilt cannot trim itself"
            )
        if (self.offset_mm is None) != (self.offset_side is None):
            raise ValueError("surface_trim offset_mm and offset_side must be given together")
        if self.offset_mm is not None and self.tool.get("kind") == "curve":
            raise ValueError(
                "surface_trim offset applies to the use-quilt trimming variant; a curve "
                "tool has no surface to offset"
            )
        return self


def _normalize_feature_refs(values: Any, what: str) -> Any:
    """FEAT-009/H02: accepted section/guide references, normalized once.

    Same public-client tolerance as LoftOp: digit-only strings are integer
    feature IDs, because a label must start with a letter. Booleans and
    out-of-range integers are refused instead of being coerced. FEAT-065/M3
    reference objects pass through unchanged; their shape is checked by
    ``loft_input_problem``.
    """
    if isinstance(values, list):
        values = [
            int(value) if isinstance(value, str) and re.fullmatch(r"[0-9]+", value) else value
            for value in values
        ]
        if any(type(value) is int and not 0 <= value <= 2147483647 for value in values):
            raise ValueError(f"Surface loft {what} IDs must be nonnegative 32-bit integers")
        if any(isinstance(value, bool) for value in values):
            raise ValueError(f"Surface loft {what} IDs cannot be booleans")
    return values


#: FEAT-065/M3: reference objects a loft section or guide accepts beside a
#: sketch label or feature id. A chain kind names one existing geometry item
#: that becomes one chain holder; a point kind is a convergence end and is
#: accepted only as the first or last section. The native executor proves each
#: id exists and has that type. All four forms were live-verified on Creo
#: 12.4.0.0 on 2026-11-11 (FEAT-065 T3), so the receipt's
#: ``unverified_input_forms`` stays for compatibility and is always empty.
LOFT_CHAIN_KINDS = ("curve", "edge")
LOFT_POINT_KINDS = ("point", "datum_point_feature")
LOFT_INPUT_LIVE_STATUS = "Creo 12.4.0.0 live-verified on 2026-11-11 (FEAT-065 M3/T3)"

LOFT_INPUT_FORMS = (
    "a sketch label or integer feature id, {kind:'curve',id:N} (a PRO_CURVE geometry id, "
    "e.g. a project_curve curve_id) or {kind:'edge',id:N} (an edge geometry id from "
    "creo_inspect_model)"
)
LOFT_POINT_FORMS = "{kind:'point',id:N} or {kind:'datum_point_feature',label:'...'}"
_LOFT_POINT_RULE_SECTION = (
    "a point is only accepted as the first or last section (a convergence end); "
    "move it to sections[0] or the last section"
)
_LOFT_POINT_RULE_GUIDE = (
    "a guide is a curve that crosses every section and cannot be a point; use " + LOFT_INPUT_FORMS
)


def loft_input_problem(
    value: Any, where: str, *, point_allowed: bool, point_rule: str
) -> str | None:
    """FEAT-065/M3: describe why one section/guide entry is unusable.

    Strings and integers are sketch references (already normalized by
    ``_normalize_feature_refs``) and are left to the native sketch resolver.
    A reference object must be one of the documented forms, carry only its own
    keys and, for a point, sit where a convergence end is allowed.
    """
    if not isinstance(value, dict):
        return None
    kind = value.get("kind")
    if not isinstance(kind, str) or not kind:
        return f"{where} must carry a string kind; use {LOFT_INPUT_FORMS}"
    if kind in LOFT_CHAIN_KINDS or kind == "point":
        if "label" in value:
            alternative = (
                "name a sketch by its label directly"
                if kind == "curve"
                else "use {kind:'datum_point_feature',label:...} for a datum point feature"
                if kind == "point"
                else "read the edge id from creo_inspect_model"
            )
            return (
                f"{where} {{kind:'{kind}'}} is a geometry kind and takes an id, not a label; "
                + alternative
            )
        if set(value) != {"kind", "id"}:
            return f"{where} {{kind:'{kind}',id:N}} accepts only kind and id"
        identifier = value.get("id")
        if type(identifier) is not int or not 0 <= identifier <= 2147483647:
            return f"{where}.id must be a nonnegative 32-bit integer geometry id"
    elif kind == "datum_point_feature":
        if set(value) != {"kind", "label"}:
            return f"{where} {{kind:'datum_point_feature',label:...}} accepts only kind and label"
        label = value.get("label")
        if not isinstance(label, str) or not label:
            return (
                f"{where}.label must be the non-empty label of a single-point datum_points feature"
            )
    else:
        hint = (
            "; a quilt or face is not a chain - pass one of its edges as {kind:'edge',id:N}"
            if kind in ("quilt", "quilt_feature", "surface", "plane", "datum_plane")
            else ""
        )
        return f"{where} kind '{kind}' is not a loft input{hint}; use {LOFT_INPUT_FORMS}" + (
            f", or at a convergence end {LOFT_POINT_FORMS}" if point_allowed else ""
        )
    if kind in LOFT_POINT_KINDS and not point_allowed:
        return f"{where} is a point: {point_rule}"
    return None


def loft_input_key(value: Any) -> tuple[str, Any]:
    """Identity of one section/guide entry for the distinctness checks."""
    if isinstance(value, dict):
        kind = value.get("kind")
        return (str(kind), value.get("label") if kind == "datum_point_feature" else value.get("id"))
    return ("sketch", value)


def _loft_input_text(value: Any) -> str:
    if isinstance(value, dict):
        key = loft_input_key(value)
        field = "label" if key[0] == "datum_point_feature" else "id"
        return f"{{kind:'{key[0]}',{field}:{key[1]!r}}}"
    return repr(value)


def _first_repeat(values: list[Any]) -> tuple[int, int] | None:
    seen: dict[tuple[str, Any], int] = {}
    for index, value in enumerate(values):
        key = loft_input_key(value)
        if key in seen:
            return seen[key], index
        seen[key] = index
    return None


# Public JSON element of sections/guides: a sketch reference or one of the
# FEAT-065/M3 reference objects. Shape is enforced by the model validators.
LoftInput = str | int | dict[str, Any]

#: FEAT-065/M4: the four loft boundaries a continuity condition can name, and
#: the slot that supplies each one. A guide boundary needs guides.
LOFT_BOUNDARY_SLOTS = {
    "first_section": ("sections", 0),
    "last_section": ("sections", -1),
    "first_guide": ("guides", 0),
    "last_guide": ("guides", -1),
}

#: FEAT-065/M4 (T2b, 2026-11-11, Creo 12.4.0.0): the boundaries where a
#: non-free condition was measured. Two vertical 40 x 10 mm strips 20 mm apart
#: bridged by their top edges became an arch (982.5888 mm2) meeting both strips
#: at G1 0.0 deg with ``tangent`` at both sections; the free bridge is the
#: 800 mm2 plane at 90 deg. Guide boundaries were not measured.
LOFT_TANGENT_BOUNDARIES = ("first_section", "last_section")

#: FEAT-065/M4: why a condition the field can spell is still refused. Probbl.h
#: documents only TAN_COND_FREE, so each reason is the measured result of the
#: one candidate value tried for it on the same two-strip bridge.
LOFT_CONDITION_REFUSALS = {
    "curvature": (
        "the candidate PRO_E_BNBLN_TAN_COND_TYPE value 3 changed the bridge (915.99 mm2) but "
        "kept a 90 deg seam on Creo 12.4.0.0, so it is not curvature continuity"
    ),
    "normal": (
        "the candidate value 4 built the same 800 mm2 plane as 'free' on Creo 12.4.0.0, so "
        "normal cannot be told apart from free"
    ),
}


class LoftBoundaryCondition(StrictModel):
    """FEAT-065/M4: continuity between one loft boundary and its neighbour face.

    ``free`` keeps the kernel's own default and is accepted on any boundary.
    ``tangent`` is the only published non-free condition: it needs a
    ``first_section``/``last_section`` boundary whose source is an edge
    ``{kind:'edge',id:N}``, and the neighbour is that edge's single adjacent
    face, resolved natively. The surface leaves the boundary continuing that
    face; the direction is fixed (measured, not a parameter). ``curvature`` and
    ``normal`` stay spellable so the refusal can name the measured reason
    (``LOFT_CONDITION_REFUSALS``); guide boundaries take ``free`` only.
    """

    boundary: Literal["first_section", "last_section", "first_guide", "last_guide"]
    condition: Literal["free", "tangent", "curvature", "normal"]


class LoftTemplate(StrictModel):
    """BUG-123: build the blend from an element tree dumped by another release.

    ``file`` is the XML ``creo_dump_feature_tree`` wrote for a real boundary
    blend; the native side replaces only its curve collections and keeps every
    other default, so the holder counts must match the request exactly (checked
    natively, where the tree is parsed). The digest is optional but recommended:
    a template that changes under the model would otherwise be applied silently.
    """

    file: str
    sha256: str | None = None

    @field_validator("file")
    @classmethod
    def _existing_xml(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("template.file must be a non-empty path")
        candidate = Path(value).expanduser()
        if candidate.suffix.lower() != ".xml":
            raise ValueError("template.file must be the XML written by creo_dump_feature_tree")
        resolved = (candidate if candidate.is_absolute() else Path.cwd() / candidate).resolve()
        if not resolved.is_file():
            raise ValueError(f"template.file does not exist: {resolved}")
        return str(resolved)

    @field_validator("sha256")
    @classmethod
    def _digest_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", text):
            raise ValueError("template.sha256 must be a 64-character hex digest")
        return text

    @model_validator(mode="after")
    def _digest_matches_the_file(self):
        if self.sha256 is not None:
            actual = hashlib.sha256(Path(self.file).read_bytes()).hexdigest()
            if actual != self.sha256:
                raise ValueError(
                    "template.sha256 does not match the file on disk (" + actual + "); "
                    "re-export or update the digest instead of loading a changed tree"
                )
        return self


class SurfaceLoftOp(StrictModel):
    """Boundary blend with one or two directions (FEAT-009/H02, FEAT-065 M1/M2/M3).

    Two to 32 sections. Each section is an MCP-owned sketch that owns one
    non-composite curve (two for one closed profile), or - FEAT-065/M3, Creo
    12.4.0.0 live-verified on 2026-11-11 - one existing curve
    ``{kind:'curve',id:N}`` or edge ``{kind:'edge',id:N}``; the first or the
    last section may instead be one convergence point ``{kind:'point',id:N}`` /
    ``{kind:'datum_point_feature',label:...}``. The sections feed the same
    PRO_E_BNBLN_1DIR tree the two-section release used, so a third (or more)
    section is one more chain holder rather than a new feature family.

    Interpolation follows what the kernel actually builds, measured on
    2026-11-11 (Creo 12.4.0.0): exactly two sections are ruled, so
    ``interpolation="straight"`` is exact there; three or more sections are
    fitted as one blend through every section instead of piecewise ruled
    patches (40/60/40 mm measured 2101.25 mm2 where piecewise linear would be
    2000.00), so ``"smooth"`` is required and ``"straight"`` is refused.

    ``guides`` is the optional second direction (``PRO_E_BNBLN_2DIR``): two to
    eight sketches, each holding one curve, or (M3) curve/edge references, that
    the surface is built through as well. A guide is never a point. Whether a
    guide actually crosses every section is left to the kernel; the measured
    shape follows the guides (2026-11-11: semicircular guides widened the quilt
    to x = 44.24 mm on a 40 mm section). Closed surfaces and solid output are
    still refused before a job exists, and the operator never falls back to a
    solid Blend. ``boundary_conditions`` (FEAT-065/M4) publishes ``tangent``
    at an edge first/last section only; curvature, normal and any non-free
    guide boundary are refused here with the measured reason.
    """

    op: Literal["surface_loft"]
    label: Label
    # 32 keeps one element tree and one receipt bounded; the kernel publishes no
    # maximum of its own (native/surface_loft.cpp enforces the same number).
    sections: Annotated[list[LoftInput], Field(min_length=2, max_length=32)]
    interpolation: Literal["straight", "smooth"] = "straight"
    # FEAT-065/M2: guides are the second direction (PRO_E_BNBLN_2DIR). Each one
    # is an MCP-owned sketch holding one curve, or (M3) one curve/edge id; every
    # guide must cross every section, and that crossing is the kernel's call.
    guides: Annotated[list[LoftInput], Field(max_length=8)] = []
    # FEAT-065/M4: None keeps the dumped plan of every earlier request unchanged.
    boundary_conditions: Annotated[list[LoftBoundaryCondition], Field(max_length=4)] | None = None
    # BUG-123/B2: read the tree from a dumped template instead of building it.
    # The receipt then reports tree_source="template_xml" and the parsed counts.
    template: LoftTemplate | None = None

    @model_validator(mode="after")
    def template_route_limits(self):
        if self.template is not None and self.boundary_conditions:
            raise ValueError(
                "template trees keep the exporting run's TAN_COND subtree, so "
                "boundary_conditions cannot be applied on the template route; remove the "
                "template to use tangent boundaries"
            )
        return self

    @field_validator("sections", mode="before")
    @classmethod
    def normalize_section_ids(cls, values: Any) -> Any:
        return _normalize_feature_refs(values, "section")

    @field_validator("guides", mode="before")
    @classmethod
    def normalize_guide_ids(cls, values: Any) -> Any:
        return _normalize_feature_refs(values, "guide")

    @model_validator(mode="after")
    def distinct_sections(self):
        last = len(self.sections) - 1
        for index, value in enumerate(self.sections):
            problem = loft_input_problem(
                value,
                f"sections[{index}]",
                point_allowed=index in (0, last),
                point_rule=_LOFT_POINT_RULE_SECTION,
            )
            if problem:
                raise ValueError(f"surface_loft {problem}")
        points = [
            index
            for index, value in enumerate(self.sections)
            if isinstance(value, dict) and value.get("kind") in LOFT_POINT_KINDS
        ]
        if len(points) > 1:
            raise ValueError(
                f"surface_loft accepts one convergence point: sections[{points[0]}] and "
                f"sections[{points[-1]}] are both points; keep the point at one end and give "
                "the other end a curve, edge or sketch section"
            )
        repeat = _first_repeat(self.sections)
        if repeat:
            first, second = repeat
            raise ValueError(
                "Surface loft sections must be distinct sketches or references: "
                f"sections[{second}] repeats sections[{first}] "
                f"({_loft_input_text(self.sections[second])})"
            )
        return self

    @model_validator(mode="after")
    def guides_form_a_second_direction(self):
        # Measured 2026-11-11 on Creo 12.4.0.0: a PRO_E_BNBLN_2DIR list with a
        # single holder is created but never regenerates (feature stays
        # PRO_FEAT_UNREGENERATED with no quilt); two holders build the surface
        # and its geometry follows them. Probbl.h states the same minimum, so a
        # one-guide request is refused here instead of failing after a job.
        if not self.guides:
            return self
        for index, value in enumerate(self.guides):
            problem = loft_input_problem(
                value, f"guides[{index}]", point_allowed=False, point_rule=_LOFT_POINT_RULE_GUIDE
            )
            if problem:
                raise ValueError(f"surface_loft {problem}")
        if len(self.guides) < 2:
            raise ValueError(
                "surface_loft guides are a second direction: give at least two guide "
                "sketches. A single guide is created but does not regenerate (2DIR needs "
                "two curves), and one guide cannot define a direction"
            )
        repeat = _first_repeat(self.guides)
        if repeat:
            first, second = repeat
            raise ValueError(
                "Surface loft guides must be distinct sketches or references: "
                f"guides[{second}] repeats guides[{first}] "
                f"({_loft_input_text(self.guides[second])})"
            )
        section_keys = {loft_input_key(value) for value in self.sections}
        shared = [
            _loft_input_text(value)
            for value in self.guides
            if loft_input_key(value) in section_keys
        ]
        if shared:
            raise ValueError(
                "surface_loft guides must not repeat a section sketch or reference; one sketch "
                "or geometry item cannot be both a section and a guide: " + ", ".join(shared)
            )
        return self

    @model_validator(mode="after")
    def section_count_matches_interpolation(self):
        # Measured 2026-11-11 on Creo 12.4.0.0: with three or more sections the
        # kernel fits one blend through all of them, so calling that "straight"
        # would promise a piecewise ruled surface the operator never builds.
        if len(self.sections) > 2 and self.interpolation != "smooth":
            raise ValueError(
                "surface_loft with "
                f"{len(self.sections)} sections is a smooth blend through every section, not "
                'piecewise ruled patches; pass interpolation="smooth" (straight is exact only '
                "with exactly two sections)"
            )
        return self

    @model_validator(mode="after")
    def boundary_conditions_name_edge_boundaries(self):
        # FEAT-065/M4: one entry per boundary; only the measured conditions
        # pass (free anywhere, tangent at an edge first/last section); a guide
        # boundary needs guides; tangent needs an edge there, because the
        # neighbour face is the edge's own adjacent face and a sketch or curve
        # has none. native/surface_loft.cpp repeats these refusals before any
        # feature exists, for a hand-written plan that skips this model.
        seen: dict[str, int] = {}
        for index, item in enumerate(self.boundary_conditions or []):
            where = f"surface_loft boundary_conditions[{index}]"
            if item.boundary in seen:
                raise ValueError(
                    f"{where} repeats boundary '{item.boundary}' from "
                    f"boundary_conditions[{seen[item.boundary]}]; give each boundary once"
                )
            seen[item.boundary] = index
            refusal = LOFT_CONDITION_REFUSALS.get(item.condition)
            if refusal:
                raise ValueError(
                    f"{where} condition '{item.condition}' is not available: {refusal}; use "
                    "'tangent' at an edge first_section/last_section, or 'free'"
                )
            if item.condition != "free" and item.boundary not in LOFT_TANGENT_BOUNDARIES:
                raise ValueError(
                    f"{where} '{item.condition}' on '{item.boundary}' is not available: guide "
                    "boundaries were not measured on Creo 12.4.0.0 (FEAT-065 T2b), so they "
                    "accept 'free' only; tangent applies to first_section/last_section"
                )
            field, position = LOFT_BOUNDARY_SLOTS[item.boundary]
            slots = self.sections if field == "sections" else self.guides
            if not slots:
                raise ValueError(
                    f"{where} names '{item.boundary}' but the loft has no guides; add 2-8 "
                    "guides or use first_section/last_section"
                )
            if item.condition == "free":
                continue
            slot = position if position >= 0 else len(slots) - 1
            value = slots[slot]
            if not isinstance(value, dict) or value.get("kind") != "edge":
                raise ValueError(
                    f"{where} '{item.condition}' needs {field}[{slot}] to be an edge "
                    f"{{kind:'edge',id:N}}, not {_loft_input_text(value)}; the neighbour face "
                    "is that edge's adjacent face"
                )
        return self


class QuiltMergeOp(StrictModel):
    """Surface merge of two quilts (FEAT-039/S03).

    The first release is the documented ProMerge.h join of exactly two quilts.
    No tolerance and no intersect variant are accepted: an unproved tolerance
    would just be ignored by the SDK tree, and intersect is not this op's
    semantics.
    """

    op: Literal["quilt_merge"]
    label: Label
    target: dict[str, Any]
    tool: dict[str, Any]

    @model_validator(mode="after")
    def two_distinct_quilts(self):
        for field, reference in (("target", self.target), ("tool", self.tool)):
            problem = quilt_reference_problem(reference, allow_datum_plane=False)
            if problem:
                raise ValueError(f"quilt_merge {field} {problem}")
        if self.target == self.tool:
            raise ValueError(
                "quilt_merge target and tool must be distinct quilts; a quilt cannot be "
                "merged with itself"
            )
        return self


def _curve_reference_problem(reference: Any) -> str | None:
    """FEAT-039/S04: describe why a projection source is unusable.

    The source is one ``PRO_CURVE`` geometry id from
    ``creo_inspect_model``; a feature label is not accepted because a sketch
    feature may own several curves and the projection would have to pick one.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind != "curve":
        return f"must be {{kind:'curve',id:<int>}}, not kind '{kind}'"
    value = reference.get("id")
    if type(value) is not int or not 0 <= value <= 2147483647:
        return "curve reference requires a nonnegative 32-bit integer id"
    return None


def _direction_reference_problem(reference: Any) -> str | None:
    """FEAT-039/S04: describe why a projection direction is unusable.

    Only references that yield a real vector are accepted: a datum plane or
    datum axis feature label, or a straight curve id. ``datum_plane`` labels are
    refused because the resolver drops the label and falls back to the default
    axis filter (live 2026-11-04, S02); a raw vector is refused because the
    reported side would then have no measurable basis.
    """
    if not isinstance(reference, dict):
        return "must be a single {kind:...} reference object"
    kind = reference.get("kind")
    if kind is None:
        return "must carry a kind"
    if kind in ("datum_feature", "datum_axis_feature"):
        label = reference.get("label")
        if not isinstance(label, str) or not label:
            return f"{kind} reference requires a label"
        return None
    if kind == "curve":
        value = reference.get("id")
        if type(value) is not int or not 0 <= value <= 2147483647:
            return "curve direction reference requires a nonnegative 32-bit integer id"
        return None
    if kind == "datum_plane":
        return (
            "must not be {kind:'datum_plane',label:...}: that resolver drops the label and "
            "picks the default plane; use {kind:'datum_feature',label:...} for a plane feature"
        )
    return f"unsupported kind '{kind}': use datum_feature, datum_axis_feature or a curve id"


class SurfaceGroupMeasureOp(StrictModel):
    """Read-only group-level boundary measurement (FEAT-039/H04).

    The group is one or more quilts; every member face is part of it. Per-quilt
    ``closed`` (ProQuiltVolumeEval) cannot say whether two members are joined,
    slightly apart or overlapping, so the native side measures boundary edges,
    seam gaps and overlapping face area separately. ``tolerance_mm`` is the
    join/flush tolerance (0.01 mm by default); ``gap_search_mm`` is the widest
    boundary-to-boundary distance still reported as a seam gap (1 mm by
    default). Gaps wider than that are exposed boundary, not a measured gap.
    """

    op: Literal["surface_group_measure"]
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=8)]
    tolerance_mm: Positive = 0.01
    gap_search_mm: Positive = 1.0

    @model_validator(mode="after")
    def valid_references(self):
        for index, reference in enumerate(self.references):
            problem = quilt_reference_problem(reference, allow_datum_plane=False)
            if problem:
                raise ValueError(f"surface_group_measure references[{index}] {problem}")
        if len({repr(sorted(reference.items())) for reference in self.references}) != len(
            self.references
        ):
            raise ValueError("surface_group_measure references must be distinct quilts")
        if self.gap_search_mm < self.tolerance_mm:
            raise ValueError(
                "surface_group_measure gap_search_mm must be at least tolerance_mm; a gap "
                "search narrower than the join tolerance could never report a gap"
            )
        return self


class ProjectCurveOp(StrictModel):
    """Project one curve onto one quilt along an explicit direction (FEAT-039/S04).

    Exactly one quilt target, exactly one curve source and one direction
    reference. ``side`` only flips the direction read from ``direction_ref``;
    which side is "positive" is measured on hardware, never named after a GUI
    view. A multi-branch projection is refused at run time by the native side
    instead of being reported as one curve.
    """

    op: Literal["project_curve"]
    label: Label
    target: dict[str, Any]
    source: dict[str, Any]
    direction_ref: dict[str, Any]
    side: Literal["positive", "negative"] = "positive"

    @model_validator(mode="after")
    def valid_references(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"project_curve target {problem}")
        problem = _curve_reference_problem(self.source)
        if problem:
            raise ValueError(f"project_curve source {problem}")
        problem = _direction_reference_problem(self.direction_ref)
        if problem:
            raise ValueError(f"project_curve direction_ref {problem}")
        return self


BOUNDARY_FILL_MIN_CURVES = 4
BOUNDARY_FILL_MAX_CURVES = 4


def _boundary_fill_curve_problem(reference: Any, index: int) -> str | None:
    """DEV-074/H09: describe why one boundary-fill curve reference is unusable.

    A boundary curve is one ``PRO_CURVE`` geometry id (a sketch curve, a
    projected curve or a composite curve). Quilts, faces, edges, bodies and
    feature labels are refused: the native route walks curve endpoints, and a
    label would name a whole sketch rather than one edge of the loop.
    """
    if not isinstance(reference, dict):
        return (
            f"boundary[{index}] must be a single {{kind:'curve',id:N}} object in chain order; "
            "nested loops, holes and multi-loop lists are not supported"
        )
    kind = reference.get("kind")
    if kind != "curve":
        return (
            f"boundary[{index}] must be {{kind:'curve',id:N}}; a quilt, face, edge, body or "
            "feature label is not a boundary curve"
        )
    if set(reference) != {"kind", "id"}:
        return (
            f"boundary[{index}] accepts only kind and id; a curve id is the geometry id from "
            "creo_inspect_model, not a feature label or a loop marker"
        )
    value = reference.get("id")
    if type(value) is not int or not 0 <= value <= 2147483647:
        return f"boundary[{index}].id must be a nonnegative 32-bit integer"
    return None


class SurfaceBoundaryFillOp(StrictModel):
    """Unavailable offline four-sided patch candidate.

    Four ordered perimeter curves form one closed loop. Opposite sides feed
    two Boundary Blend directions, each with ADD_CLOSED=false. The closed
    flag describes the perimeter, never cyclic blending of sections. Native
    endpoint checks enforce closure and compatible parameter direction.
    Arbitrary N-sided patches, holes and G1 constraints are unsupported.
    """

    op: Literal["surface_boundary_fill"]
    label: Label
    boundary: Annotated[list[dict[str, Any]], Field()]
    closed: bool = True

    @model_validator(mode="after")
    def one_ordered_closed_curve_chain(self):
        if not self.closed:
            raise ValueError(
                "surface_boundary_fill only builds a closed boundary; an open chain cannot be "
                "filled - use surface_loft for a surface through two or more sections"
            )
        if len(self.boundary) != BOUNDARY_FILL_MIN_CURVES:
            raise ValueError(
                "surface_boundary_fill needs exactly 4 ordered perimeter curves; "
                "use surface_loft for two or more sections"
            )
        ids: list[int] = []
        for index, reference in enumerate(self.boundary):
            problem = _boundary_fill_curve_problem(reference, index)
            if problem:
                raise ValueError(f"surface_boundary_fill {problem}")
            ids.append(reference["id"])
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        if duplicates:
            raise ValueError(
                "surface_boundary_fill boundary curves must be distinct; repeated curve id(s): "
                + ", ".join(str(value) for value in duplicates)
                + ". Remove the duplicate edges from the chain"
            )
        return self


class SurfaceRoundOp(StrictModel):
    """Constant round on the edge shared by two member faces of one quilt.

    DEV-074/H08 measured this route on hardware: ``PRO_FEAT_ROUND`` with
    ``PRO_ROUND_REF_SURF_SURF`` keeps the result on the same quilt. The
    reference set uses the same shape the generic round already takes
    (``[{"surfaces": [{kind:"surface",id:N}, {kind:"surface",id:M}]}]``), so
    one operation has exactly one set and exactly two faces. An edge chain, a
    second set, variable radii, full/chordal/through-curve radii and custom
    transitions have no field here and are refused before a job exists.

    The pair must be two distinct member faces of the target quilt. Face
    membership is checked natively against the quilt's own face visit, which
    also refuses a solid face or another quilt's face. Adjacency (sharing one
    edge) is deliberately left to the kernel: the 2026-11-08 hardware probe
    showed a non-adjacent pair failing regeneration with a full rollback, so a
    guessed topology test here would only second-guess the kernel.
    """

    op: Literal["surface_round"]
    label: Label
    target: dict[str, Any]
    references: Annotated[list[dict[str, Any]], Field(min_length=1, max_length=1)]
    radius: Positive

    @field_validator("radius", mode="before")
    @classmethod
    def radius_is_a_number(cls, value: Any) -> Any:
        # Pydantic would accept True as 1.0 and "3" as 3.0; a radius is a real
        # number, not a boolean or a string.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("surface_round radius must be a finite value greater than zero")
        return value

    @model_validator(mode="after")
    def one_constant_surface_pair(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_round target {problem}")
        if len(self.references) != 1:
            raise ValueError(
                "surface_round accepts exactly one {'surfaces':[...]} reference set; "
                "multiple sets are not supported"
            )
        reference = self.references[0]
        if not isinstance(reference, dict):
            raise ValueError("surface_round references[0] must be a {'surfaces':[...]} object")
        if set(reference) != {"surfaces"}:
            raise ValueError(
                "surface_round references[0] accepts only the 'surfaces' key; edge chains, "
                "variable radii and transitions are not supported"
            )
        faces = reference.get("surfaces")
        if not isinstance(faces, list) or len(faces) != 2:
            raise ValueError(
                "surface_round requires exactly two member faces as "
                "{'surfaces':[{kind:'surface',id:N}, {kind:'surface',id:M}]}"
            )
        ids = set()
        for index, face in enumerate(faces):
            if not isinstance(face, dict) or face.get("kind") != "surface":
                raise ValueError(
                    f"surface_round faces[{index}] must be {{kind:'surface',id:N}}; an edge, "
                    "a plane or a body is not a member face"
                )
            if set(face) != {"kind", "id"}:
                raise ValueError(
                    f"surface_round faces[{index}] accepts only kind and id; a face id is "
                    "the geometry id from creo_inspect_model, not a feature label"
                )
            value = face.get("id")
            if type(value) is not int or not 0 <= value <= 2147483647:
                raise ValueError(
                    f"surface_round faces[{index}].id must be a nonnegative 32-bit integer"
                )
            ids.add(value)
        if len(ids) != 2:
            raise ValueError("surface_round faces must be two distinct surfaces")
        return self


CURVATURE_MIN_SAMPLES = 5
CURVATURE_MAX_SAMPLES = 50


def _curvature_face_problem(reference: Any, index: int) -> str | None:
    """DEV-074/H08: describe why one curvature member face is unusable.

    A member is named either by its geometry id (``{kind:"surface",id:N}``, the
    id ``creo_inspect_model`` reports) or by its zero-based position in the
    quilt's own member-face order. A feature label, an edge or a body is not a
    face.
    """
    if type(reference) is int and not isinstance(reference, bool):
        if reference < 0:
            return f"faces[{index}] member index must be nonnegative"
        return None
    if not isinstance(reference, dict):
        return f"faces[{index}] must be {{kind:'surface',id:N}} or a zero-based member index"
    if reference.get("kind") != "surface":
        return (
            f"faces[{index}] must be {{kind:'surface',id:N}}; an edge, plane or body is not a face"
        )
    if set(reference) != {"kind", "id"}:
        return f"faces[{index}] accepts only kind and id"
    value = reference.get("id")
    if type(value) is not int or not 0 <= value <= 2147483647:
        return f"faces[{index}].id must be a nonnegative 32-bit integer"
    return None


class SurfaceCurvatureOp(StrictModel):
    """Read-only principal-curvature and G1 analysis of quilt member faces.

    DEV-074/H08: the SDK has no zebra-stripe or curvature-comb API, so the
    equivalent deliverable is numeric. Each requested face is sampled on a
    bounded UV raster (``samples_per_direction`` 5..50, default 12) and the
    native side returns the principal curvatures, radii and directions of every
    sample that lies inside the trimmed face. When two shared-edge member faces
    are given, the normals are sampled along the shared edge and the angle is
    reported; the 0.5 degree threshold is only a ``within_g1`` marker, not a
    substitute for the measured angle.

    The analysis is read-only: it creates no feature and does not advance the
    revision. One or two faces are accepted; more than two has no field here.
    """

    op: Literal["surface_curvature"]
    target: dict[str, Any]
    faces: Annotated[list[Any], Field(min_length=1, max_length=2)]
    samples_per_direction: int = 12

    @field_validator("samples_per_direction", mode="before")
    @classmethod
    def density_is_a_bounded_integer(cls, value: Any) -> Any:
        # A density is a real integer; booleans, strings, floats and NaN are
        # refused before a job exists. The range keeps a raster bounded.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                "surface_curvature samples_per_direction must be an integer between "
                f"{CURVATURE_MIN_SAMPLES} and {CURVATURE_MAX_SAMPLES}"
            )
        if not CURVATURE_MIN_SAMPLES <= value <= CURVATURE_MAX_SAMPLES:
            raise ValueError(
                "surface_curvature samples_per_direction must be between "
                f"{CURVATURE_MIN_SAMPLES} and {CURVATURE_MAX_SAMPLES}"
            )
        return value

    @model_validator(mode="after")
    def one_or_two_distinct_member_faces(self):
        problem = quilt_reference_problem(self.target, allow_datum_plane=False)
        if problem:
            raise ValueError(f"surface_curvature target {problem}")
        for index, reference in enumerate(self.faces):
            problem = _curvature_face_problem(reference, index)
            if problem:
                raise ValueError(f"surface_curvature {problem}")
        if len(self.faces) == 2 and self.faces[0] == self.faces[1]:
            raise ValueError("surface_curvature faces must be two different member faces")
        return self
