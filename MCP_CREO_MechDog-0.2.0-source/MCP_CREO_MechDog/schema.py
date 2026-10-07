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
    format: Literal["step","stl","iges","jpeg"] = "step"

class DumpTreeOp(StrictModel):
    op: Literal["dump_tree"]
    feature: str | int

Operation=Annotated[Union[SketchOp,ExtrudeOp,RevolveOp,HoleOp,RoundOp,PlaneOp,AxisOp,ShellOp,DimensionsOp,SketchDimensionsOp,ParametersOp,RelationsOp,PatternOp,GenericFeatureOp,SimpleOp,ExportOp,DumpTreeOp],Field(discriminator="op")]
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
                if k in ('surface','edge','axis','curve','dimension'):
                    if type(x.get('id')) is not int or x['id']<0: raise ValueError("Model item reference requires a nonnegative integer id")
                elif k=='feature':
                    if ('label' in x)==('id' in x): raise ValueError("Feature reference requires one label or id")
                elif k in ('datum_feature','datum_axis_feature'):
                    if not isinstance(x.get('label'),str): raise ValueError("Datum reference requires a label")
                elif k in ('plane','datum_plane'):
                    if 'normal' in x:
                        if not isinstance(x['normal'],list) or len(x['normal'])!=3 or sum(v*v for v in x['normal'])<1e-12: raise ValueError("Plane normal requires a nonzero 3D vector")
                    elif x.get('axis','z') not in ('x','y','z'): raise ValueError("Plane axis must be x, y or z")
                elif k!='body': raise ValueError(f"Unsupported model reference kind: {k}")
            for v in x.values(): references(v)
    references(dumped)
    return dumped
