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
