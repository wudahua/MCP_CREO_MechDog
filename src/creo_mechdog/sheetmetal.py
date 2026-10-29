"""First-wall section contract shared by the standalone tool and execute_plan.

DEV-051 T03 / BUG-032. `creo_sheetmetal_wall` builds the first wall as a thin
extrusion of the sketch section and then converts that body into a native
sheetmetal wall. The conversion re-drives the body from one driving face, so
only one open straight line has a defined depth/thickness geometry:

    volume = line length x thickness x depth

Any other section (closed contour, arc, spline, multi-entity chain) would be
rebuilt from an arbitrary face: the reported closed rectangle kept the same
volume for depth 1 and depth 30, i.e. the depth was silently dropped. Admission
rejects those sections before the native modelling step, and the native
operation enforces the same rule for cross-job sketch references that Python
cannot inspect.
"""

from __future__ import annotations

from typing import Any

_UNSUPPORTED = (
    "closed contours, arcs, splines and multi-entity chains are not supported for the first wall"
)


def first_wall_section_problem(entities: list[dict[str, Any]]) -> str | None:
    """Return why a section cannot drive a first wall, or None when it can."""
    drawing = [
        entity
        for entity in entities
        if entity.get("type") != "centerline" and not entity.get("construction")
    ]
    if len(drawing) != 1:
        return (
            "sheetmetal_wall needs exactly one open straight line as the first wall section; "
            f"got {len(drawing)} drawing entities ({_UNSUPPORTED})"
        )
    kind = drawing[0].get("type")
    if kind != "line":
        return (
            "sheetmetal_wall needs exactly one open straight line as the first wall section; "
            f"got a {kind!r} entity ({_UNSUPPORTED})"
        )
    return None


# BUG-046 / DEV-051 T04: a solid protrusion that merges into an existing
# sheetmetal body is refused by Creo with a bare ProFeatureWithoptionsCreate -1.
# Live isolation on Creo 12.4.0.0 (2026-10-29) measured the three cases that fix
# the boundary: the same add over the sheet and far away from it both return -1
# with no element errors, the same rectangle as a cut removes 100 mm3, and the
# same add with new_body=true succeeds as a separate solid body (+500 mm3, no
# merge). Adding material to the sheet therefore has to go through the wall or
# flange operations; the solid protrusion path cannot feed the sheetmetal body.
SOLID_ADD_UNSUPPORTED = "SHEETMETAL_SOLID_ADD_UNSUPPORTED"


def solid_add_on_sheetmetal_problem(operations: list[dict[str, Any]]) -> str | None:
    """Return why a plan would add solid material into a sheetmetal body."""
    blocked = [
        operation.get("label")
        for operation in operations
        if operation.get("op") == "extrude"
        and operation.get("mode") == "add"
        and operation.get("thin") is None
        and not operation.get("new_body")
    ]
    if not blocked:
        return None
    labels = ", ".join(str(label) for label in blocked)
    return (
        f"{SOLID_ADD_UNSUPPORTED}: Creo rejects an extrude add that merges solid material "
        "into a sheetmetal body (ProFeatureWithoptionsCreate returns -1, measured on Creo "
        "12.4.0.0 with and without overlap). Add material with sheetmetal_wall or "
        "sheetmetal_flange, or request new_body=true to create a separate solid body; "
        f"cut, surface and thin extrudes are unaffected. Blocked operations: {labels}"
    )
