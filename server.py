"""MCP_CREO_MechDog: Creo 10 native-feature server. stdout is reserved for MCP messages."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

import bridge
import generic_bridge as general
from schema import Entity, SketchDimension, SketchConstraint, Operation
from typing import Literal
from version import VERSION
from capabilities import families,UNAVAILABLE_OPERATIONS,REGISTERED_OPERATIONS

logging.basicConfig(level=logging.WARNING)
mcp = MCPServer(
    "MCP_CREO_MechDog", version=VERSION,
    instructions="General native parametric modeling in Creo 10. Use mm and degrees. Create parts with creo_new_part "
                 "or a complete creo_execute_plan, create independent sketches, then reference them by feature label "
                 "for extrude/revolve/add/cut, and append subsequent native features. "
                 "Mutation tools return a job_id: poll creo_get_job, then use its model_id and latest revision. "
                 "Inspect surfaces/edges/dimensions before choosing raw references. Always provide expected_revision "
                 "when modifying an existing MCP model. Models and native files persist across clients. "
                 "Success requires status=succeeded and saved_file_reloaded_and_verified=true for mutations. "
                 "Create sheetmetal/assembly models with the corresponding new-model tools or model_type in execute_plan. "
                 "Use creo_capabilities for enabled and tested operations; reserved unavailable tools reject before native mutation. "
                 "Do not retry unknown_outcome without inspection.",
)
READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
CREATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    x: float = Field(description="Hole center X in mm, relative to plate center")
    y: float = Field(description="Hole center Y in mm, relative to plate center")
    diameter: float = Field(gt=0, description="Through-hole diameter in mm")


async def invoke(fn, *args, **kwargs):
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except (ValueError, RuntimeError, OSError) as exc:
        raise ToolError(str(exc)) from None


@mcp.tool(annotations=READ)
async def creo_check_environment() -> dict[str, Any]:
    """Check Creo executable, Toolkit SDK, metric template and compiler. License presence does not prove usability."""
    return await invoke(bridge.check_environment)


@mcp.tool(annotations=READ)
async def creo_session_status() -> dict[str, Any]:
    """Connect through Toolkit to the single open Creo session; return current model and native connection code."""
    return await invoke(bridge.session_status)


@mcp.tool(annotations=CREATE)
async def creo_create_plate(length: float, width: float, thickness: float,
                            corner_radius: float = 0, holes: list[Hole] | None = None,
                            model_name: str | None = None) -> dict[str, Any]:
    """Create a NEW native Creo part in mm. Origin is plate XY center at bottom Z=0.

    A dimensioned rectangular sketch drives extrusion to thickness. corner_radius rounds
    the four vertical corners. holes specifies independent native through-hole features.
    Return a job_id immediately; poll creo_get_job for the saved PRT and verification.
    Does not overwrite existing parts. Omit model_name to generate a unique name.
    Example: 80x60x20, R5; holes (±30,±20) diameter 8 and (0,0) diameter 10.
    """
    spec = await invoke(bridge.validate_spec, length, width, thickness, corner_radius,
                        [h.model_dump() for h in holes or []], model_name)
    return await invoke(bridge.create_job, spec)


@mcp.tool(annotations=READ)
async def creo_get_job(job_id: str) -> dict[str, Any]:
    """Read modeling progress/result. succeeded includes native PRT/ASM path, hash, counts, volume and saved-file verification."""
    return await invoke(bridge.get_job, job_id)


@mcp.tool(annotations=READ)
async def creo_list_jobs(limit: int = 10) -> dict[str, Any]:
    """List recent jobs, including jobs that continue after their MCP client disconnects."""
    return {"jobs": await invoke(bridge.list_jobs, limit)}


@mcp.tool(annotations=READ)
async def creo_capabilities() -> dict[str, Any]:
    """Describe general modeling tools, coordinate frames, reference syntax and test evidence."""
    local_evidence = bridge.ROOT / "build/capability_evidence.json"
    evidence = local_evidence if local_evidence.is_file() else bridge.ROOT / "docs/validation.json"
    verified = bridge.read_json(evidence) if evidence.is_file() else {}
    if verified.get('version') != VERSION:
        verified = {"version":VERSION,"status":"No validation summary for this version yet; inspect integration reports"}
    return {
        "name":"MCP_CREO_MechDog", "version":VERSION, "unit":"mm", "angle_unit":"degrees",
        "tool_count":len(await mcp.list_tools()),
        "enabled_tool_count":len(await mcp.list_tools())-len(UNAVAILABLE_OPERATIONS),
        "unavailable_tools":["creo_"+name for name in UNAVAILABLE_OPERATIONS],
        "modeling":"Composable native Creo features; geometry is not restricted to a plate recipe",
        "entities":["line","centerline","circle","arc","polyline","rectangle","spline","ellipse"],
        "operations":[op for op in REGISTERED_OPERATIONS if op not in UNAVAILABLE_OPERATIONS],
        "registered_operations":list(REGISTERED_OPERATIONS),
        "extrude_modes":["add","cut","surface"],"extrude_depths":["blind","through_all_cut","symmetric"],
        "revolve_modes":["add","cut","surface"],"thin_features":True,
        "frames":{"XY":"u=+X,v=+Y,normal=+Z","XZ":"u=+X,v=+Z,normal=-Y","YZ":"u=+Y,v=+Z,normal=+X"},
        "references":{"datum_plane":{"kind":"datum_plane","axis":"z","offset":0},
                      "planar_solid_face":{"kind":"plane","normal":[0,0,1],"offset":10},
                      "raw_face":{"kind":"surface","id":"from inspection"},
                      "raw_edge":{"kind":"edge","id":"from inspection"},
                      "datum_label":{"kind":"datum_feature","label":"plane_label"}},
        "arbitrary_planar_support":"plane={reference:{kind:surface,id:...},origin:[x,y,z],u_axis:[x,y,z]}",
        "workflow":"submit once -> poll get_job -> inspect model -> choose references -> append using expected_revision",
        "scope":"MCP-owned native part, sheetmetal and assembly models. Tool availability does not prove every option or Creo operation is supported; consult validation evidence and coverage documentation.",
        "complete_creo_coverage":False,
        "release_status":"pre-release candidate; requested complete coverage has not been achieved",
        "families":families(),
        "unavailable_operations":UNAVAILABLE_OPERATIONS,
        "evidence_directory":str(bridge.ROOT/"build"),
        "verified_evidence":verified,
    }


@mcp.tool(annotations=CREATE)
async def creo_new_part(model_name: str | None = None) -> dict[str, Any]:
    """Create a new metric native part with datum planes and coordinate system. Returns model_id and job_id."""
    return await invoke(general.submit,[],None,model_name)


@mcp.tool(annotations=CREATE)
async def creo_execute_plan(operations: list[Operation], model_id: str | None = None,
                            model_name: str | None = None, expected_revision: int | None = None,
                            assertions: dict[str,Any] | None = None,
                            model_type: Literal["part","sheetmetal","assembly"] = "part") -> dict[str, Any]:
    """Execute an ordered general feature plan. Omit model_id to create a new part.

    Sketch/extrude/revolve and later features reference earlier feature labels.
    Existing models require expected_revision. Stops at first error; existing models
    roll back to their saved checkpoint. assertions supports require_solid and volume_mm3.
    """
    return await invoke(general.submit,[op.model_dump(exclude_none=True) for op in operations],model_id,model_name,expected_revision,assertions,model_type=model_type)


@mcp.tool(annotations=CREATE)
async def creo_create_sketch(model_id: str, expected_revision: int, label: str,
                              entities: list[Entity], plane: Literal["XY","XZ","YZ"] | dict[str,Any] = "XY",
                              offset: float = 0, dimensions: list[SketchDimension] | None = None,
                              constraints: list[SketchConstraint] | None = None) -> dict[str, Any]:
    """Create an independent native dimensioned sketch of arbitrary supported entities.

    Coordinates are in the chosen plane's (u,v) frame. Arc angles are degrees CCW.
    Rectangle/polyline expand to named lines e.g. box_0, box_1. Explicit dimensions
    have names and entity references; automatic dimensioning fills remaining freedoms.
    For revolve include one centerline, or supply an external axis to creo_revolve.
    """
    op={"op":"sketch","label":label,"plane":plane,"offset":offset,"entities":[e.model_dump() for e in entities],
        "dimensions":[d.model_dump() for d in dimensions or []],"constraints":[c.model_dump() for c in constraints or []]}
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_extrude(model_id: str, expected_revision: int, label: str, sketch: str | int,
                       depth: float=1, mode: Literal["add","cut","surface"]="add",
                       direction: Literal["positive","negative","symmetric"]="positive",
                       depth_type: Literal["blind","through_all"]="blind", new_body: bool=False,
                       thin: float | None=None) -> dict[str,Any]:
    """Create native extrusion from a sketch label/ID. Supports protrusion, pocket, through cut, symmetric, surface and thin modes."""
    op={"op":"extrude","label":label,"sketch":sketch,"depth":depth,"mode":mode,"direction":direction,"depth_type":depth_type,"new_body":new_body}
    if thin is not None: op["thin"]=thin
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_revolve(model_id: str, expected_revision: int, label: str, sketch: str | int,
                       angle: float=360, mode: Literal["add","cut","surface"]="add",
                       direction: Literal["positive","negative","symmetric"]="positive",
                       axis: dict[str,Any] | None=None, new_body: bool=False, thin: float | None=None) -> dict[str,Any]:
    """Create native revolve/revolved cut from an arbitrary sketch, about its centerline or an external axis."""
    op={"op":"revolve","label":label,"sketch":sketch,"angle":angle,"mode":mode,"direction":direction,"new_body":new_body}
    if axis is not None: op["axis"]=axis
    if thin is not None: op["thin"]=thin
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_hole(model_id: str, expected_revision: int, label: str, diameter: float,
                    placement: dict[str,Any], reference1: dict[str,Any], reference2: dict[str,Any],
                    offset1: float=0, offset2: float=0, depth: float | None=None, flip: bool=False) -> dict[str,Any]:
    """Create native straight hole on a planar face. Two reference planes and signed offsets locate it. Omit depth for through-all; depth makes a blind hole."""
    op={"op":"hole","label":label,"diameter":diameter,"placement":placement,"reference1":reference1,"reference2":reference2,"offset1":offset1,"offset2":offset2,"flip":flip}
    if depth is not None: op["depth"]=depth
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_round(model_id: str, expected_revision: int, label: str, radius: float,
                     references: list[dict[str,Any]]) -> dict[str,Any]:
    """Create a native constant-radius fillet on edges or face pairs. Each set is {edge:reference} or {surfaces:[reference,reference]}."""
    return await invoke(general.submit,[{"op":"round","label":label,"size":radius,"references":references}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_chamfer(model_id: str, expected_revision: int, label: str, distance: float,
                       references: list[dict[str,Any]]) -> dict[str,Any]:
    """Create equal-distance native chamfer sets on explicit edges or face pairs."""
    return await invoke(general.submit,[{"op":"chamfer","label":label,"size":distance,"references":references}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_datum_plane(model_id: str, expected_revision: int, label: str, reference: dict[str,Any],
                           offset: float=0, angle: float | None=None, axis: dict[str,Any] | None=None) -> dict[str,Any]:
    """Create parametric offset datum plane, or angled plane through an axis."""
    op={"op":"datum_plane","label":label,"reference":reference,"offset":offset}
    if angle is not None: op["angle"]=angle
    if axis is not None: op["axis"]=axis
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_datum_axis(model_id: str, expected_revision: int, label: str,
                          references: list[dict[str,Any]]) -> dict[str,Any]:
    """Create a native datum axis through two planes, a cylindrical face, a straight edge or existing axis."""
    return await invoke(general.submit,[{"op":"datum_axis","label":label,"references":references}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_dimension_pattern(model_id: str, expected_revision: int, label: str,
                                  feature: str | int, dimension_id: int, count: int,
                                  increment: float) -> dict[str,Any]:
    """Create a native dimension pattern of a feature. Select a leader dimension ID from inspection, total count and per-member increment."""
    return await invoke(general.submit,[{"op":"dimension_pattern","label":label,"feature":feature,"dimension_id":dimension_id,"count":count,"increment":increment}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_shell(model_id: str, expected_revision: int, label: str, thickness: float,
                     remove_surfaces: list[dict[str,Any]] | None=None, outward: bool=False) -> dict[str,Any]:
    """Create native constant-thickness shell, optionally removing selected faces."""
    return await invoke(general.submit,[{"op":"shell","label":label,"thickness":thickness,"remove_surfaces":remove_surfaces or [],"outward":outward}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_set_dimensions(model_id: str, expected_revision: int, values: list[dict[str,Any]]) -> dict[str,Any]:
    """Modify native model dimensions by IDs returned in inspection. values=[{id:int,value:float}]. Regenerate, save and verify."""
    return await invoke(general.submit,[{"op":"set_dimensions","values":values}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_mirror(model_id: str, expected_revision: int, label: str, plane: dict[str,Any],
                      references: list[dict[str,Any]] | None=None, keep_original: bool=True) -> dict[str,Any]:
    """Create native geometry/whole-part mirror about a planar reference. Omit references for whole part.

    Toolkit geometry references are curves, axes, quilts, points, csys or a part.
    Feature-subtree mirroring is not supported by this API; do not supply feature selections.
    """
    return await invoke(general.submit,[{"op":"mirror","label":label,"plane":plane,"references":references or [],"keep_original":keep_original}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_sweep(model_id: str, expected_revision: int, label: str,
                     trajectory: str | int | list[dict[str,Any]], profile: list[Entity],
                     dimensions: list[SketchDimension] | None=None, constraints: list[SketchConstraint] | None=None,
                     mode: Literal["add","cut","surface"]="add", thin: float | None=None,
                     new_body: bool=False, capped: bool=False) -> dict[str,Any]:
    """Create a native constant-section sweep along sketch curves or selected curve/edge references.

    Profile coordinates are local (u,v) in Creo's generated section frame at the path start.
    Named profile dimensions can be edited using creo_set_sketch_dimensions with this label.
    """
    op={"op":"sweep","label":label,"trajectory":trajectory,"profile":[e.model_dump() for e in profile],"dimensions":[d.model_dump() for d in dimensions or []],"constraints":[c.model_dump() for c in constraints or []],"mode":mode,"new_body":new_body,"capped":capped}
    if thin is not None: op["thin"]=thin
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_loft(model_id: str, expected_revision: int, label: str, sections: list[str | int],
                    mode: Literal["add","cut","surface"]="add",
                    interpolation: Literal["straight","smooth"]="straight", new_body: bool=False) -> dict[str,Any]:
    """Unavailable in 0.21: native blend/loft has not passed Creo 10 verification.

    This reserved interface returns an explicit error before queuing or mutating a model.
    """
    return await invoke(general.submit,[{"op":"loft","label":label,"sections":sections,"mode":mode,"interpolation":interpolation,"new_body":new_body}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_draft(model_id: str, expected_revision: int, label: str, surfaces: list[dict[str,Any]],
                     neutral_plane: dict[str,Any], angle: float, pull_direction: dict[str,Any] | None=None,
                     flip: bool=False, include_tangent: bool=False) -> dict[str,Any]:
    """Create a native constant-angle, unsplit draft using selected surfaces and a neutral plane.

    Pull direction defaults to the neutral plane normal; can use a datum plane or axis reference.
    """
    op={"op":"draft","label":label,"surfaces":surfaces,"neutral_plane":neutral_plane,"angle":angle,"flip":flip,"include_tangent":include_tangent}
    if pull_direction is not None: op["pull_direction"]=pull_direction
    return await invoke(general.submit,[op],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_new_sheetmetal(model_name: str | None=None) -> dict[str,Any]:
    """Prepare a metric part for sheetmetal. The first wall creates its native sheetmetal body by conversion."""
    return await invoke(general.submit,[],None,model_name,model_type="sheetmetal")


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_wall(model_id: str, expected_revision: int, label: str, sketch: str | int,
                              depth: float, thickness: float,
                              direction: Literal["positive","negative"]="positive") -> dict[str,Any]:
    """Create the first flat sheetmetal wall from an open straight-line sketch, depth and thickness.

    The native tree contains the driving sketch, thin extrusion and sheetmetal conversion.
    Use flange tools for subsequent bent walls. Curved or closed first-wall sketches are not validated.
    """
    return await invoke(general.submit,[{"op":"sheetmetal_wall","label":label,"sketch":sketch,"depth":depth,"thickness":thickness,"direction":direction}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_flange(model_id: str, expected_revision: int, label: str, edge: dict[str,Any],
                                height: float, angle: float=90, radius: float=1, flip: bool=False, y_factor: float=0.5) -> dict[str,Any]:
    """Attach a native bent flange to a sheetmetal edge. The section exposes named height for dimension edits."""
    return await invoke(general.submit,[{"op":"sheetmetal_flange","label":label,"edge":edge,"height":height,"angle":angle,"radius":radius,"flip":flip,"y_factor":y_factor}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_unbend(model_id: str, expected_revision: int, label: str, fixed_surface: dict[str,Any],
                                references: list[dict[str,Any]] | None=None) -> dict[str,Any]:
    """Unbend a native sheetmetal part about a fixed surface. Omit references to unbend all bends."""
    return await invoke(general.submit,[{"op":"sheetmetal_unbend","label":label,"fixed_surface":fixed_surface,"references":references or []}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_flat_pattern(model_id: str, expected_revision: int, label: str, fixed_surface: dict[str,Any]) -> dict[str,Any]:
    """Create a native flat-pattern feature about a fixed sheetmetal surface."""
    return await invoke(general.submit,[{"op":"sheetmetal_flat_pattern","label":label,"fixed_surface":fixed_surface,"references":[]}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_sheetmetal_bend_back(model_id: str, expected_revision: int, label: str, fixed_surface: dict[str,Any],
                                   references: list[dict[str,Any]] | None=None) -> dict[str,Any]:
    """Refold previously unbent sheetmetal about a fixed surface. Omit references to bend back all bends."""
    return await invoke(general.submit,[{"op":"sheetmetal_bend_back","label":label,"fixed_surface":fixed_surface,"references":references or []}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_new_assembly(model_name: str | None=None) -> dict[str,Any]:
    """Create a native metric assembly with default datum planes from the locally installed template."""
    return await invoke(general.submit,[],None,model_name,model_type="assembly")


@mcp.tool(annotations=CREATE)
async def creo_assemble_component(model_id: str, expected_revision: int, label: str, source_model_id: str,
                                  translation: list[float] | None=None, rotation: list[float] | None=None,
                                  placement: Literal["fixed","default","constraints"]="fixed",
                                  constraints: list[dict[str,Any]] | None=None) -> dict[str,Any]:
    """Insert a revision snapshot of a verified MCP part/sheetmetal model as a native assembly component.

    Translation is XYZ mm; rotation is XYZ Euler degrees, applied X then Y then Z.
    Sources must be ready and saved; later source edits do not update the component snapshot.
    Native placement can be fixed, default or mate/align/insert/csys constraints. Nested subassemblies are not supported yet.
    """
    return await invoke(general.submit,[{"op":"assemble_component","label":label,"source_model_id":source_model_id,"translation":translation or [0,0,0],"rotation":rotation or [0,0,0],"placement":placement,"constraints":constraints or []}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_component_placement(model_id: str, expected_revision: int, component: str | int,
                                   translation: list[float], rotation: list[float] | None=None) -> dict[str,Any]:
    """Replace a component's existing placement constraints with fixed placement at the specified rigid transform."""
    return await invoke(general.submit,[{"op":"component_placement","component":component,"translation":translation,"rotation":rotation or [0,0,0]}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_component_constraints(model_id: str, expected_revision: int, component: str | int,
                                     constraints: list[dict[str,Any]]) -> dict[str,Any]:
    """Replace native component placement with mate/align/offset/insert/csys constraints to assembly references."""
    return await invoke(general.submit,[{"op":"component_constraints","component":component,"constraints":constraints}],model_id,None,expected_revision)


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False,destructive_hint=True,idempotent_hint=False,open_world_hint=False))
async def creo_remove_component(model_id: str, expected_revision: int, component: str | int) -> dict[str,Any]:
    """Remove a component feature from this MCP assembly, preserving its source model and native file."""
    return await invoke(general.submit,[{"op":"remove_component","component":component}],model_id,None,expected_revision)


@mcp.tool(annotations=READ)
async def creo_list_components(model_id: str) -> dict[str,Any]:
    """Read the last verified assembly component list, native transforms and placement status."""
    model=await invoke(general.model_info,model_id)
    if model.get("model_type")!="assembly": raise ToolError("Assembly model required")
    return {"model_id":model_id,"revision":model["revision"],"components":model.get("inspection",{}).get("components",[]),"aliases":model["aliases"]}


@mcp.tool(annotations=CREATE)
async def creo_set_sketch_dimensions(model_id: str, expected_revision: int, sketch: str | int,
                                     values: dict[str,float]) -> dict[str,Any]:
    """Modify named explicit sketch dimensions, or numeric sketch dimension IDs, and regenerate dependent features."""
    return await invoke(general.submit,[{"op":"set_sketch_dimensions","sketch":sketch,"values":values}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_set_parameters(model_id: str, expected_revision: int,
                              values: dict[str,float | str | bool | int]) -> dict[str,Any]:
    """Create/update native part parameters. Supports numbers, booleans and strings."""
    return await invoke(general.submit,[{"op":"set_parameters","values":values}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_set_relations(model_id: str, expected_revision: int, lines: list[str]) -> dict[str,Any]:
    """Set native part relations using simple arithmetic assignments, e.g. d12 = SIZE / 2. Replaces the relation set."""
    return await invoke(general.submit,[{"op":"set_relations","lines":lines}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_create_feature_tree(model_id: str, expected_revision: int, label: str,
                                   tree: dict[str,Any]) -> dict[str,Any]:
    """Advanced native feature creation from Toolkit element tree JSON. Nodes: id, integer/double/string/reference/references, children.

    Element IDs and integer enum values can be symbolic SDK constants. Use creo_lookup_constants.
    Reference existing native sketches/model items. Feature-specific trees must follow installed
    SDK documentation. This low-level route does not automatically supply missing sections/collections.
    """
    return await invoke(general.submit,[{"op":"feature_tree","label":label,"tree":tree}],model_id,None,expected_revision)


@mcp.tool(annotations=READ)
async def creo_lookup_constants(prefix: str, limit: int=100) -> dict[str,Any]:
    """Look up installed SDK element IDs and feature enum constants for advanced element-tree operations."""
    if not 1<=limit<=500: raise ToolError("limit must be 1–500")
    path=bridge.ROOT/"build/constants.json"
    if not path.exists(): raise ToolError("Call creo_session_status to build the native worker first")
    constants=bridge.read_json(path)
    items={k:v for k,v in constants.items() if k.startswith(prefix)}
    return {"constants":dict(list(items.items())[:limit]),"total_matches":len(items)}


@mcp.tool(annotations=READ)
async def creo_inspect_model(model_id: str) -> dict[str,Any]:
    """Get the latest verified model snapshot: revision, feature labels/IDs, dimensions, faces, edges, bodies and parameters. This is the saved snapshot; use refresh_model to inspect live Creo."""
    return await invoke(general.model_info,model_id)


@mcp.tool(annotations=READ)
async def creo_refresh_model(model_id: str) -> dict[str,Any]:
    """Query live native model through Toolkit. Returns a job_id; poll get_job for the actual snapshot."""
    return await invoke(general.submit,[],model_id,None,None,None,True)


@mcp.tool(annotations=READ)
async def creo_list_models(limit: int=10) -> dict[str,Any]:
    """List persistent MCP-owned part models and their latest verified snapshots."""
    return await invoke(general.list_models,limit)


@mcp.tool(annotations=CREATE)
async def creo_regenerate(model_id: str, expected_revision: int) -> dict[str,Any]:
    """Regenerate, verify, save and reload a native model."""
    return await invoke(general.submit,[{"op":"regenerate"}],model_id,None,expected_revision)


@mcp.tool(annotations=CREATE)
async def creo_save_model(model_id: str, expected_revision: int) -> dict[str,Any]:
    """Save a new native PRT version to the owned model directory, then reload and verify it."""
    return await invoke(general.submit,[{"op":"save"}],model_id,None,expected_revision)


@mcp.tool(annotations=READ)
async def creo_export_model(model_id: str, format: Literal["step","stl","iges","jpeg"]="step") -> dict[str,Any]:
    """Export native model geometry through Creo to STEP, STL, IGES or JPEG, inside the job output directory."""
    return await invoke(general.submit,[{"op":"export","format":format}],model_id,None,None,None,True)


@mcp.tool(annotations=READ)
async def creo_dump_feature_tree(model_id: str, feature: str | int) -> dict[str,Any]:
    """Export a native feature's Toolkit element tree to XML for inspection; returns a job_id."""
    return await invoke(general.submit,[{"op":"dump_tree","feature":feature}],model_id,None,None,None,True)


if __name__ == "__main__":
    mcp.run(transport="stdio")
