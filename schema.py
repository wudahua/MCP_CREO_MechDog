"""Schemas for general feature operations. Each operation is validated before queuing."""
from __future__ import annotations
import math
import re
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

Point2 = Annotated[list[float], Field(min_length=2, max_length=2)]
Point3 = Annotated[list[float], Field(min_length=3, max_length=3)]
Label = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,27}$")]
Positive = Annotated[float, Field(gt=0, le=100000)]

class Line(StrictModel):
    type: Literal["line", "centerline"]
    name: Label
    start: Point2
    end: Point2
    construction: bool = False
    @model_validator(mode="after")
    def nonzero(self):
        if math.dist(self.start,self.end)<1e-8: raise ValueError("Line endpoints coincide")
        return self

class Circle(StrictModel):
    type: Literal["circle"]
    name: Label
    center: Point2
    radius: Positive
    construction: bool = False

class Arc(Circle):
    type: Literal["arc"]
    start_angle: float
    end_angle: float

class Polyline(StrictModel):
    type: Literal["polyline", "spline"]
    name: Label
    points: Annotated[list[Point2], Field(min_length=2, max_length=200)]
    closed: bool = False
    construction: bool = False

class Rectangle(StrictModel):
    type: Literal["rectangle"]
    name: Label
    min: Point2
    max: Point2
    construction: bool = False
    @model_validator(mode="after")
    def corners(self):
        if self.max[0]<=self.min[0] or self.max[1]<=self.min[1]: raise ValueError("Rectangle max must exceed min")
        return self

class Ellipse(StrictModel):
    type: Literal["ellipse"]
    name: Label
    center: Point2
    x_radius: Positive
    y_radius: Positive
    construction: bool = False

Entity = Annotated[Union[Line,Circle,Arc,Polyline,Rectangle,Ellipse],Field(discriminator="type")]

class EntityRef(StrictModel):
    entity: str
    point: Literal["whole","start","end","center"] = "whole"

class SketchDimension(StrictModel):
    name: Label
    type: Literal["length","radius","diameter","distance","horizontal","vertical","line_distance","angle","arc_angle","ellipse_x_radius","ellipse_y_radius"]
    refs: Annotated[list[EntityRef],Field(min_length=1,max_length=3)]
    value: Positive
    position: Point2 = [0,0]

class SketchConstraint(StrictModel):
    type: Literal["coincident","horizontal","vertical","point_on","tangent","perpendicular","equal_radius","parallel","equal_length","collinear"]
    refs: Annotated[list[EntityRef],Field(min_length=1,max_length=2)]

class SketchOp(StrictModel):
    op: Literal["sketch"]
    label: Label
    plane: Literal["XY","XZ","YZ"] | dict[str,Any] = "XY"
    offset: float = 0
    entities: Annotated[list[Entity],Field(min_length=1,max_length=500)]
    dimensions: list[SketchDimension] = []
    constraints: list[SketchConstraint] = []
    @model_validator(mode="after")
    def entities_unique(self):
        names=[e.name for e in self.entities]
        if len(names)!=len(set(names)): raise ValueError("Sketch entity names must be unique")
        if sum(e.type=="centerline" for e in self.entities)>1: raise ValueError("One revolve centerline is supported per sketch")
        expanded=[]
        for entity in self.entities:
            if entity.type=="rectangle": expanded += [entity.name+'_'+str(i) for i in range(4)]
            elif entity.type=="polyline": expanded += [entity.name+'_'+str(i) for i in range(len(entity.points)-1+int(entity.closed))]
            else: expanded.append(entity.name)
        if len(expanded)!=len(set(expanded)): raise ValueError("Expanded sketch entity names collide")
        for item in [*self.dimensions,*self.constraints]:
            for ref in item.refs:
                if ref.entity not in expanded: raise ValueError(f"Unknown sketch entity reference: {ref.entity}")
        if len({d.name for d in self.dimensions})!=len(self.dimensions): raise ValueError("Dimension names must be unique")
        return self

class ExtrudeOp(StrictModel):
    op: Literal["extrude"]
    label: Label
    sketch: str | int
    depth: Positive = 1
    mode: Literal["add","cut","surface"] = "add"
    direction: Literal["positive","negative","symmetric"] = "positive"
    depth_type: Literal["blind","through_all"] = "blind"
    new_body: bool = False
    thin: float | None = Field(default=None,gt=0)
    @model_validator(mode="after")
    def through_cut(self):
        if self.depth_type=="through_all" and self.mode!="cut": raise ValueError("through_all is supported for cuts")
        return self

class RevolveOp(StrictModel):
    op: Literal["revolve"]
    label: Label
    sketch: str | int
    angle: Annotated[float,Field(gt=0,le=360)] = 360
    mode: Literal["add","cut","surface"] = "add"
    direction: Literal["positive","negative","symmetric"] = "positive"
    axis: dict[str,Any] | None = None
    new_body: bool = False
    thin: float | None = Field(default=None,gt=0)

class HoleOp(StrictModel):
    op: Literal["hole"]
    label: Label
    placement: dict[str,Any]
    reference1: dict[str,Any]
    reference2: dict[str,Any]
    offset1: float = 0
    offset2: float = 0
    diameter: Positive
    depth: Positive | None = None
    flip: bool = False

class RoundOp(StrictModel):
    op: Literal["round","chamfer"]
    label: Label
    size: Positive
    references: Annotated[list[dict[str,Any]],Field(min_length=1,max_length=100)]

class PlaneOp(StrictModel):
    op: Literal["datum_plane"]
    label: Label
    reference: dict[str,Any]
    offset: float = 0
    angle: float | None = Field(default=None,ge=-360,le=360)
    axis: dict[str,Any] | None = None

class AxisOp(StrictModel):
    op: Literal["datum_axis"]
    label: Label
    references: Annotated[list[dict[str,Any]],Field(min_length=1,max_length=2)]

class ShellOp(StrictModel):
    op: Literal["shell"]
    label: Label
    thickness: Positive
    remove_surfaces: list[dict[str,Any]] = []
    outward: bool = False

class DimensionValue(StrictModel):
    id: int
    value: float

class DimensionsOp(StrictModel):
    op: Literal["set_dimensions"]
    values: Annotated[list[DimensionValue],Field(min_length=1,max_length=200)]

class SketchDimensionsOp(StrictModel):
    op: Literal["set_sketch_dimensions"]
    sketch: str | int
    values: dict[str,float]

class ParametersOp(StrictModel):
    op: Literal["set_parameters"]
    values: dict[str,float | str | bool | int]
    @model_validator(mode="after")
    def names(self):
        for name,value in self.values.items():
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,30}",name): raise ValueError("Parameter names must be 1–31 letters/digits/_ starting with a letter")
            if isinstance(value,str) and len(value)>80: raise ValueError("String parameters support at most 80 characters")
        return self

class RelationsOp(StrictModel):
    op: Literal["set_relations"]
    lines: list[str]
    @model_validator(mode="after")
    def expressions(self):
        allowed={"abs","ceil","floor","sin","cos","tan","asin","acos","atan","atan2","sqrt","exp","ln","log","mod","min","max"}
        for line in self.lines:
            if not re.fullmatch(r"\s*[a-zA-Z][a-zA-Z0-9_]*\s*=\s*[a-zA-Z0-9_ .+*/()^,\-]+",line): raise ValueError("Relations currently support simple arithmetic assignments")
            for fn in re.findall(r"\b([a-zA-Z][a-zA-Z0-9_]*)\s*\(",line):
                if fn.lower() not in allowed: raise ValueError(f"Unsupported relation function: {fn}")
        return self

class PatternOp(StrictModel):
    op: Literal["dimension_pattern"]
    label: Label
    feature: str | int
    dimension_id: int
    count: Annotated[int,Field(ge=2,le=100)]
    increment: float
    @model_validator(mode="after")
    def nonzero(self):
        if abs(self.increment)<1e-9: raise ValueError("Pattern increment must be nonzero")
        return self

class MirrorOp(StrictModel):
    op: Literal["mirror"]
    label: Label
    plane: dict[str,Any]
    references: list[dict[str,Any]] = []
    keep_original: bool = True
    @model_validator(mode="after")
    def geometry_references(self):
        allowed={"curve","axis","quilt","csys","point","part","datum_feature","datum_axis_feature","datum_plane"}
        if any(r.get("kind") not in allowed for r in self.references): raise ValueError("Toolkit mirror supports geometry/part references, not feature-tree selections")
        if any(r.get("kind")=="part" for r in self.references) and len(self.references)!=1: raise ValueError("Whole-part mirror cannot mix reference types")
        return self

class SweepOp(StrictModel):
    op: Literal["sweep"]
    label: Label
    trajectory: str | int | list[dict[str,Any]]
    profile: Annotated[list[Entity],Field(min_length=1,max_length=500)]
    dimensions: list[SketchDimension] = []
    constraints: list[SketchConstraint] = []
    mode: Literal["add","cut","surface"] = "add"
    new_body: bool = False
    thin: float | None = Field(default=None,gt=0)
    capped: bool = False
    @model_validator(mode="after")
    def profile_valid(self):
        SketchOp(label=self.label,op="sketch",entities=self.profile,dimensions=self.dimensions,constraints=self.constraints)
        if isinstance(self.trajectory,list) and not self.trajectory: raise ValueError("Sweep trajectory cannot be empty")
        return self

class LoftOp(StrictModel):
    op: Literal["loft"]
    label: Label
    sections: Annotated[list[str | int],Field(min_length=2,max_length=20)]
    mode: Literal["add","cut","surface"] = "add"
    interpolation: Literal["straight","smooth"] = "straight"
    new_body: bool = False
    @model_validator(mode="after")
    def unique_sections(self):
        if len(self.sections)!=len(set(self.sections)): raise ValueError("Loft sections must be distinct")
        return self

class DraftOp(StrictModel):
    op: Literal["draft"]
    label: Label
    surfaces: Annotated[list[dict[str,Any]],Field(min_length=1,max_length=200)]
    neutral_plane: dict[str,Any]
    pull_direction: dict[str,Any] | None = None
    angle: Annotated[float,Field(gt=-85,lt=85)]
    flip: bool = False
    include_tangent: bool = False
    @model_validator(mode="after")
    def nonzero_angle(self):
        if abs(self.angle)<1e-9: raise ValueError("Draft angle must be nonzero")
        return self

class SheetmetalWallOp(StrictModel):
    op: Literal["sheetmetal_wall"]
    label: Label
    sketch: str | int
    depth: Positive
    thickness: Positive
    direction: Literal["positive","negative"] = "positive"

class SheetmetalFlangeOp(StrictModel):
    op: Literal["sheetmetal_flange"]
    label: Label
    edge: dict[str,Any]
    height: Positive
    angle: Annotated[float,Field(gt=0,lt=180)] = 90
    radius: Positive = 1
    flip: bool = False
    y_factor: Annotated[float,Field(gt=0,le=1)] = 0.5

class SheetmetalUnbendOp(StrictModel):
    op: Literal["sheetmetal_unbend","sheetmetal_flat_pattern","sheetmetal_bend_back"]
    label: Label
    fixed_surface: dict[str,Any]
    references: list[dict[str,Any]] = []

class AssemblyConstraint(StrictModel):
    type: Literal["mate","align","mate_offset","align_offset","insert","csys"]
    assembly_reference: dict[str,Any]
    component_reference: dict[str,Any]
    offset: float = 0
    assembly_side: Literal["yellow","red"] = "yellow"
    component_side: Literal["yellow","red"] = "yellow"

class AssembleOp(StrictModel):
    op: Literal["assemble_component"]
    label: Label
    source_model_id: Annotated[str,Field(pattern=r"^[a-f0-9]{32}$")]
    translation: Point3 = [0,0,0]
    rotation: Point3 = [0,0,0]
    placement: Literal["fixed","default","constraints"] = "fixed"
    constraints: list[AssemblyConstraint] = []
    @model_validator(mode="after")
    def placement_valid(self):
        if self.placement=="constraints" and not self.constraints: raise ValueError("Constraint placement needs constraints")
        if self.placement!="constraints" and self.constraints: raise ValueError("Use placement=constraints when providing constraints")
        return self

class ComponentPlacementOp(StrictModel):
    op: Literal["component_placement"]
    component: str | int
    translation: Point3 = [0,0,0]
    rotation: Point3 = [0,0,0]

class ComponentConstraintsOp(StrictModel):
    op: Literal["component_constraints"]
    component: str | int
    constraints: Annotated[list[AssemblyConstraint],Field(min_length=1,max_length=20)]

class RemoveComponentOp(StrictModel):
    op: Literal["remove_component"]
    component: str | int

class GenericFeatureOp(StrictModel):
    op: Literal["feature_tree"]
    label: Label
    tree: dict[str,Any]
    @model_validator(mode="after")
    def valid_tree(self):
        count=0
        def walk(node,depth=0):
            nonlocal count
            count+=1
            if depth>40 or count>5000: raise ValueError("Element tree exceeds 40 levels or 5000 nodes")
            if not isinstance(node,dict) or set(node)-{'id','integer','double','string','reference','references','curve_collection','children'}:
                raise ValueError("Invalid element tree node fields")
            identifier=node.get('id')
            if not (type(identifier) is int or isinstance(identifier,str) and re.fullmatch(r'PRO_[A-Z0-9_]+',identifier)):
                raise ValueError("Element id must be a native integer or SDK constant name")
            if sum(k in node for k in ('integer','double','string','reference','references','curve_collection'))>1:
                raise ValueError("Element node may have only one value type")
            if 'integer' in node and not (type(node['integer']) is int or isinstance(node['integer'],str) and re.fullmatch(r'PRO_[A-Z0-9_]+',node['integer'])):
                raise ValueError("Invalid integer element value")
            if 'double' in node and type(node['double']) not in (float,int): raise ValueError("Invalid double element value")
            if 'string' in node and (not isinstance(node['string'],str) or len(node['string'])>4096): raise ValueError("Invalid string element value")
            if not isinstance(node.get('children',[]),list): raise ValueError("Element children must be a list")
            for child in node.get('children',[]): walk(child,depth+1)
        walk(self.tree)
        return self

class SimpleOp(StrictModel):
    op: Literal["regenerate","save"]

class Assertions(StrictModel):
    require_solid: bool = False
    volume_mm3: float | None = Field(default=None,ge=0)
    volume_tolerance: float = Field(default=0.01,gt=0)

class ExportOp(StrictModel):
    op: Literal["export"]
    format: Literal["step","stl","iges","jpeg","pdf"] = "step"

class DrawingModelOp(StrictModel):
    op: Literal["drawing_model"]
    label: Label
    source_model_id: Annotated[str,Field(pattern=r"^[a-f0-9]{32}$")]

class DrawingSheetOp(StrictModel):
    op: Literal["drawing_sheet"]
    action: Literal["add","resize"] = "add"
    sheet: Annotated[int,Field(ge=1,le=100)] = 1
    width: Annotated[float,Field(gt=10,le=5000)] = 297
    height: Annotated[float,Field(gt=10,le=5000)] = 210
    name: Label | None = None

ViewStyle = Literal["wireframe","hidden","no_hidden","shaded","shaded_edges"]
class DrawingViewOp(StrictModel):
    op: Literal["drawing_view"]
    label: Label
    model: Label
    sheet: Annotated[int,Field(ge=1,le=100)] = 1
    position: Point2
    orientation: Literal["front","back","top","bottom","left","right","isometric"] = "front"
    scale: Annotated[float,Field(gt=0,le=1000)] = 1
    display: ViewStyle = "no_hidden"

class DrawingProjectionOp(StrictModel):
    op: Literal["drawing_projection"]
    label: Label
    parent: str | int
    position: Point2
    display: ViewStyle = "no_hidden"

class DrawingViewUpdateOp(StrictModel):
    op: Literal["drawing_view_update"]
    view: str | int
    scale: Annotated[float,Field(gt=0,le=1000)] | None = None
    move: Point2 | None = None
    display: ViewStyle | None = None
    @model_validator(mode="after")
    def has_change(self):
        if all(v is None for v in (self.scale,self.move,self.display)): raise ValueError("Specify scale, move or display")
        return self

NoteLines = Annotated[list[Annotated[str,Field(min_length=1,max_length=79)]],Field(min_length=1,max_length=50)]
class DrawingNoteOp(StrictModel):
    op: Literal["drawing_note"]
    label: Label
    sheet: Annotated[int,Field(ge=1,le=100)] = 1
    position: Point2
    lines: NoteLines
    text_height: Annotated[float,Field(gt=0,le=100)] = 3.5

class DrawingNoteUpdateOp(StrictModel):
    op: Literal["drawing_note_update"]
    note: str | int
    lines: NoteLines | None = None
    position: Point2 | None = None
    text_height: Annotated[float,Field(gt=0,le=100)] | None = None
    @model_validator(mode="after")
    def has_change(self):
        if all(v is None for v in (self.lines,self.position,self.text_height)): raise ValueError("Specify lines, position or text_height")
        return self

class DrawingTableOp(StrictModel):
    op: Literal["drawing_table"]
    label: Label
    sheet: Annotated[int,Field(ge=1,le=100)] = 1
    position: Point2
    columns: Annotated[list[Positive],Field(min_length=1,max_length=50)]
    row_height: Positive = 8
    cells: Annotated[list[list[Annotated[str,Field(max_length=79)]]],Field(min_length=1,max_length=100)]
    @model_validator(mode="after")
    def rectangular(self):
        if any(len(row)!=len(self.columns) for row in self.cells): raise ValueError("Each table row must match the column widths")
        return self

class DrawingTableCellOp(StrictModel):
    op: Literal["drawing_table_cell"]
    table: str | int
    row: Annotated[int,Field(ge=1,le=100)]
    column: Annotated[int,Field(ge=1,le=50)]
    text: Annotated[str,Field(max_length=79)]

class DrawingDimensionOp(StrictModel):
    op: Literal["drawing_dimension"]
    label: Label
    view: str | int
    dimension_id: Annotated[int,Field(ge=0)]
    position: Point2 | None = None

class DrawingDeleteOp(StrictModel):
    op: Literal["drawing_delete"]
    kind: Literal["view","note","table","dimension"]
    target: str | int

    @model_validator(mode='after')
    def dimension_label(self):
        if self.kind=='dimension' and not isinstance(self.target,str): raise ValueError('Use a dimension label to identify its source model')
        return self

class UdfInspectOp(StrictModel):
    op: Literal['udf_inspect']
    file_path: Annotated[str,Field(min_length=1,max_length=250)]
    instance: Label | None = None

class UdfCreateOp(StrictModel):
    op: Literal['udf_create']
    label: Label
    file_path: Annotated[str,Field(min_length=1,max_length=250)]
    instance: Label | None = None
    references: dict[str,dict[str,Any]]
    dimensions: dict[str,float] = {}

class DumpTreeOp(StrictModel):
    op: Literal["dump_tree"]
    feature: str | int

class CsysOp(StrictModel):
    op: Literal['datum_csys']
    label: Label
    reference: dict[str,Any] = {'kind':'default_csys'}
    translation: Point3 = [0,0,0]
    rotation: Point3 = [0,0,0]

class DatumPoint(StrictModel):
    name: Label
    position: Point3

class PointsOp(StrictModel):
    op: Literal['datum_points']
    label: Label
    reference: dict[str,Any] = {'kind':'default_csys'}
    points: Annotated[list[DatumPoint],Field(min_length=1,max_length=200)]
    @model_validator(mode='after')
    def unique_names(self):
        if len({p.name for p in self.points})!=len(self.points): raise ValueError('Datum point names must be unique')
        return self

class FillOp(StrictModel):
    op: Literal['surface_fill']
    label: Label
    sketch: str | int

class ThickenOp(StrictModel):
    op: Literal['thicken']
    label: Label
    reference: dict[str,Any]
    thickness: Positive
    side: Literal['positive','negative','symmetric'] = 'symmetric'
    mode: Literal['add','cut'] = 'add'
    new_body: bool = False

class SolidifyOp(StrictModel):
    op: Literal['solidify']
    label: Label
    reference: dict[str,Any]
    side: Literal['positive','negative'] = 'positive'
    mode: Literal['add','cut'] = 'add'
    new_body: bool = False

class BooleanOp(StrictModel):
    op: Literal['boolean_bodies']
    label: Label
    method: Literal['union','subtract','intersect']
    targets: Annotated[list[dict[str,Any]],Field(min_length=1,max_length=100)]
    tools: Annotated[list[dict[str,Any]],Field(min_length=1,max_length=100)]
    keep_tools: bool = False
    @model_validator(mode='after')
    def valid_bodies(self):
        if self.method!='subtract' and len(self.targets)!=1: raise ValueError('Union/intersection require one target body')
        if self.method=='subtract' and len(self.tools)!=1: raise ValueError('Subtract requires one tool body')
        if self.method!='subtract' and self.keep_tools: raise ValueError('keep_tools only applies to subtraction')
        refs=[*self.targets,*self.tools]
        if any(r.get('kind')!='body' or type(r.get('id')) is not int or r['id']<0 for r in refs): raise ValueError('Explicit body IDs are required')
        if len({r['id'] for r in refs})!=len(refs): raise ValueError('Target and tool bodies must be distinct')
        return self

class RibOp(StrictModel):
    op: Literal['rib']
    label: Label
    sketch: str | int
    thickness: Positive
    side: Literal['positive','negative','symmetric'] = 'symmetric'
    flip: bool = False

Operation=Annotated[Union[UdfInspectOp,UdfCreateOp,SketchOp,ExtrudeOp,RevolveOp,HoleOp,RoundOp,PlaneOp,AxisOp,ShellOp,DimensionsOp,SketchDimensionsOp,ParametersOp,RelationsOp,PatternOp,MirrorOp,SweepOp,LoftOp,DraftOp,SheetmetalWallOp,SheetmetalFlangeOp,SheetmetalUnbendOp,AssembleOp,ComponentPlacementOp,ComponentConstraintsOp,RemoveComponentOp,GenericFeatureOp,SimpleOp,ExportOp,DumpTreeOp,DrawingModelOp,DrawingSheetOp,DrawingViewOp,DrawingProjectionOp,DrawingViewUpdateOp,DrawingNoteOp,DrawingNoteUpdateOp,DrawingTableOp,DrawingTableCellOp,DrawingDimensionOp,DrawingDeleteOp,CsysOp,PointsOp,FillOp,ThickenOp,SolidifyOp,BooleanOp,RibOp],Field(discriminator="op")]
OPERATIONS=TypeAdapter(list[Operation])

def validate_operations(operations: list[dict]) -> list[dict]:
    if not 0<=len(operations)<=200: raise ValueError("A plan supports at most 200 operations")
    result=OPERATIONS.validate_python(operations)
    labels=[x.label for x in result if hasattr(x,"label")]
    if len(labels)!=len(set(labels)): raise ValueError("Feature labels must be unique within a plan")
    dumped=[x.model_dump(exclude_none=True) for x in result]
    def finite(x):
        if isinstance(x,float) and not math.isfinite(x): raise ValueError("All numeric values must be finite")
        if isinstance(x,list):
            for v in x: finite(v)
        if isinstance(x,dict):
            for v in x.values(): finite(v)
    finite(dumped)
    def references(x):
        if isinstance(x,list):
            for v in x: references(v)
        if isinstance(x,dict):
            if 'kind' in x:
                k=x['kind']
                if k in ('surface','edge','axis','curve','dimension','csys','point','quilt'):
                    if type(x.get('id')) is not int or x['id']<0: raise ValueError("Model item reference requires a nonnegative integer id")
                elif k=='feature':
                    if ('label' in x)==('id' in x): raise ValueError("Feature reference requires one label or id")
                elif k in ('datum_feature','datum_axis_feature','sketch_curves','quilt_feature','datum_csys_feature','datum_point_feature'):
                    if not isinstance(x.get('label'),str): raise ValueError("Datum reference requires a label")
                elif k in ('plane','datum_plane'):
                    if 'normal' in x:
                        if not isinstance(x['normal'],list) or len(x['normal'])!=3 or sum(v*v for v in x['normal'])<1e-12: raise ValueError("Plane normal requires a nonzero 3D vector")
                    elif x.get('axis','z') not in ('x','y','z'): raise ValueError("Plane axis must be x, y or z")
                elif k not in ('body','part','default_csys'): raise ValueError(f"Unsupported model reference kind: {k}")
            for v in x.values(): references(v)
    references([op for op in dumped if not op['op'].startswith('drawing_')])
    return dumped
