// Composable Creo feature operations, using the installed Creo 10 Toolkit.
#include "third_party/json.hpp"
#include <map>
#include <set>
#include <array>
#include <ProDtmCrv.h>
#include <ProDtmPln.h>
#include <ProDtmAxis.h>
#include <ProRevolve.h>
#include <ProChamfer.h>
#include <ProShell.h>
#include <ProPattern.h>
#include <ProDimension.h>
#include <ProSecconstr.h>
#include <ProParameter.h>
#include <ProParamval.h>
#include <ProRelSet.h>
#include <ProContour.h>
#include <ProEdge.h>
#include <ProCurvedata.h>
#include <ProIntf3dExport.h>
#include <ProPart.h>
#include <ProCollect.h>
#include <ProCrvcollection.h>
#include <ProMirror.h>
#include <ProSweep.h>
#include <ProDraft.h>
#include <ProSrfcollection.h>
#include <ProSmtFlangeWall.h>
#include <ProSmtFlatWall.h>
#include <ProRegularUnbend.h>
#include <ProSmtBendBack.h>
#include <ProAsmcomp.h>
#include <ProAsmcomppath.h>
#include <ProSheetmetal.h>
#include <ProSmtDrvSurf.h>
#include "constants.inc"
using J=nlohmann::json;
using V=std::array<double,3>;
static J aliases=J::object(),gfeatures=J::array(),gsurfaces=J::array(),gedges=J::array();
static std::set<int> visited_edges;
static std::wstring generic_job;
static J operation_results=J::array();
static V vec(const J& j){return {j.at(0).get<double>(),j.at(1).get<double>(),j.at(2).get<double>()};}
static double dot(const V&a,const V&b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static V cross(const V&a,const V&b){return {a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};}
static V scale(const V&a,double s){return {a[0]*s,a[1]*s,a[2]*s};}
static V add(const V&a,const V&b){return {a[0]+b[0],a[1]+b[1],a[2]+b[2]};}
static V normalized(const V&a){double n=sqrt(dot(a,a));if(n<1e-9)throw std::runtime_error("Zero direction vector");return scale(a,1/n);}
static J xyz(const double* a){return J::array({a[0],a[1],a[2]});}
static int constant(const J& value){if(value.is_number_integer())return value.get<int>();auto it=tk_constants.find(value.get<std::string>());if(it==tk_constants.end())throw std::runtime_error("Unknown Toolkit constant: "+value.get<std::string>());return it->second;}
static int feature_id(const J& ref){if(ref.is_number_integer())return ref.get<int>();std::string label=ref.get<std::string>();if(!aliases.contains(label))throw std::runtime_error("Unknown feature label: "+label);return aliases[label].at("feature_id").get<int>();}
static ProFeature feature(const J& ref){ProFeature f;CK(ProModelitemInit(board,feature_id(ref),PRO_FEATURE,&f));return f;}
static std::string type_name(int t){if(t==PRO_FEAT_CURVE)return "sketch_or_curve";if(t==PRO_FEAT_PROTRUSION||t==PRO_FEAT_FIRST_FEAT)return "protrusion";if(t==PRO_FEAT_CUT)return "cut";if(t==PRO_FEAT_ROUND)return "round";if(t==PRO_FEAT_CHAMFER)return "chamfer";if(t==PRO_FEAT_HOLE)return "hole";if(t==PRO_FEAT_SHELL)return "shell";if(t==PRO_FEAT_DATUM)return "datum_plane";if(t==PRO_FEAT_DATUM_AXIS)return "datum_axis";return "other";}
static ProError dimension_cb(ProDimension* dim,ProError status,ProAppData data){
 if(status)return PRO_TK_NO_ERROR;J* list=(J*)data;double value;ProName symbol=L"";ProDimensiontype type;ProError e=ProDimensionValueGet(dim,&value);if(!e){ProDimensionSymbolGet(dim,symbol);ProDimensionTypeGet(dim,&type);list->push_back({{"id",dim->id},{"value",value},{"symbol",utf8(symbol)},{"type",(int)type}});}return PRO_TK_NO_ERROR;
}
static ProError collect_geom_ids(ProGeomitem* item,ProError status,ProAppData data){if(!status)((J*)data)->push_back({{"id",item->id},{"type",(int)item->type}});return PRO_TK_NO_ERROR;}
static ProError inspect_feature(ProFeature* f,ProError status,ProAppData){
 if(status)return PRO_TK_NO_ERROR;ProFeattype t;ProFeatStatus state;ProName name=L"";ProBoolean incomplete=PRO_B_FALSE;CK(ProFeatureTypeGet(f,&t));CK(ProFeatureStatusGet(f,&state));CK(ProFeatureIsIncomplete(f,&incomplete));ProModelitemNameGet(f,name);
 J item={{"id",f->id},{"type",(int)t},{"type_name",type_name(t)},{"status",(int)state},{"incomplete",incomplete==PRO_B_TRUE},{"name",utf8(name)}};J dims=J::array();ProFeatureDimensionVisit(f,dimension_cb,nullptr,&dims);item["dimensions"]=dims;
 if(t==PRO_FEAT_CURVE){ProSection section=nullptr;if(!ProFeatureSectionCopy(f,0,&section)){J sd=J::array();ProIntlist ids=nullptr;int count=0;if(!ProSecdimIdsGet(section,&ids,&count)){for(int i=0;i<count;i++){double v;ProSecdimType dt;if(!ProSecdimValueGet(section,ids[i],&v)){ProSecdimTypeGet(section,ids[i],&dt);sd.push_back({{"id",ids[i]},{"value",v},{"type",(int)dt}});}}ProArrayFree((ProArray*)&ids);}item["sketch_dimensions"]=sd;ProIntlist cs=nullptr;int nc=0;if(!ProSectionConstraintsIdsGet(section,&cs,&nc)){item["sketch_constraint_count"]=nc;ProArrayFree((ProArray*)&cs);}ProSectionFree(&section);}}
 J geometry=J::array();ProFeatureGeomitemVisit(f,PRO_TYPE_UNUSED,collect_geom_ids,nullptr,&geometry);item["geometry_items"]=geometry;gfeatures.push_back(item);return PRO_TK_NO_ERROR;
}
static ProError inspect_edge(ProEdge edge,ProError status,ProAppData){
 if(status)return PRO_TK_NO_ERROR;int id;CK(ProEdgeIdGet(edge,&id));if(!visited_edges.insert(id).second)return PRO_TK_NO_ERROR;J item={{"id",id}};ProGeomitemdata* data=nullptr;
 ProEnttype curve_type;ProEdgeTypeGet(edge,&curve_type);item["type"]=(int)curve_type;if(!ProEdgeDataGet(edge,&data)&&data){auto c=data->data.p_curve_data;if(c){Pro3dPnt a,b;if(!ProLinedataGet(c,a,b)){item["start"]=xyz(a);item["end"]=xyz(b);}}ProGeomitemdataFree(&data);}
 ProEdge ea,eb;ProSurface sa,sb;if(!ProEdgeNeighborsGet(edge,&ea,&eb,&sa,&sb)){int a,b;ProSurfaceIdGet(sa,&a);ProSurfaceIdGet(sb,&b);item["adjacent_surfaces"]=J::array({a,b});}gedges.push_back(item);return PRO_TK_NO_ERROR;
}
static ProError inspect_contour(ProContour contour,ProError status,ProAppData data){if(status)return PRO_TK_NO_ERROR;return ProContourEdgeVisit((ProSurface)data,contour,inspect_edge,nullptr,nullptr);}
static ProError inspect_surface(ProSurface surface,ProError status,ProAppData body_id){
 if(status)return PRO_TK_NO_ERROR;ProGeomitemdata* data=nullptr;CK(ProSurfaceDataGet(surface,&data));auto p=data->data.p_surface_data;int id;CK(ProSurfaceIdGet(surface,&id));J item={{"id",id},{"body_id",(int)(intptr_t)body_id}};
 if(p){item["type"]=(int)p->type;item["bbox"]=J::array({xyz(p->xyz_min),xyz(p->xyz_max)});if(p->type==PRO_SRF_PLANE){item["normal"]=xyz(p->srf_shape.plane.e3);item["origin"]=xyz(p->srf_shape.plane.origin);}if(p->type==PRO_SRF_CYL){item["radius"]=p->srf_shape.cylinder.radius;item["origin"]=xyz(p->srf_shape.cylinder.origin);item["axis"]=xyz(p->srf_shape.cylinder.e3);}}ProSmtSurfType st;if(!ProSmtSurfaceTypeGet((ProPart)board,surface,&st))item["sheetmetal_type"]=(int)st;gsurfaces.push_back(item);ProGeomitemdataFree(&data);CK(ProSurfaceContourVisit(surface,inspect_contour,nullptr,surface));return PRO_TK_NO_ERROR;
}
static ProError parameter_cb(ProParameter* param,ProError status,ProAppData data){if(status)return PRO_TK_NO_ERROR;ProParamvalue value;ProUnititem unit;J* params=(J*)data;if(!ProParameterValueWithUnitsGet(param,&value,&unit)){J v;if(value.type==PRO_PARAM_DOUBLE)v=value.value.d_val;else if(value.type==PRO_PARAM_INTEGER)v=value.value.i_val;else if(value.type==PRO_PARAM_BOOLEAN)v=value.value.l_val!=0;else if(value.type==PRO_PARAM_STRING)v=utf8(value.value.s_val);else return PRO_TK_NO_ERROR;(*params)[utf8(param->id)]={ {"value",v},{"type",(int)value.type} };}return PRO_TK_NO_ERROR;}
static J assembly_inspection();
static void verify_saved(const J& before,const J& after);
static bool assembly_model(){ProMdlType t;CK(ProMdlTypeGet(board,&t));return t==PRO_MDL_ASSEMBLY;}
static J inspection(bool require_healthy=true){
 gfeatures=J::array();gsurfaces=J::array();gedges=J::array();visited_edges.clear();CK(ProSolidFeatVisit((ProSolid)board,inspect_feature,nullptr,nullptr));bool healthy=true;for(auto& f:gfeatures)if(f["incomplete"].get<bool>()||f["status"].get<int>()!=PRO_FEAT_ACTIVE)healthy=false;
 if(require_healthy&&!healthy){log("UNHEALTHY_FEATURES=%s\n",gfeatures.dump().c_str());throw std::runtime_error("Regeneration produced a failed, suppressed or incomplete feature");}
 J bodies=J::array();bool isasm=assembly_model(),solid=false;ProSolidBody* list=nullptr;int n=0;if(!isasm){CK(ProSolidBodiesCollect((ProSolid)board,&list));CK(ProArraySizeGet((ProArray)list,&n));}
 for(int i=0;i<n;i++){ProSolidBodyState state;CK(ProSolidBodyStateGet(&list[i],&state));J b={{"id",list[i].id},{"state",(int)state}};if(state==PRO_BODY_STATE_ACTIVE){solid=true;Pro3dPnt bounds[2];CK(ProSolidBodyOutlineGet(&list[i],bounds));b["bbox"]=J::array({xyz(bounds[0]),xyz(bounds[1])});CK(ProSolidBodySurfaceVisit(&list[i],inspect_surface,(ProAppData)(intptr_t)list[i].id));}bodies.push_back(b);}if(list)ProArrayFree((ProArray*)&list);if(isasm)for(auto f:gfeatures)if(f["type"].get<int>()==PRO_FEAT_COMPONENT)solid=true;
 J result={{"features",gfeatures},{"surfaces",gsurfaces},{"edges",gedges},{"bodies",bodies},{"healthy",healthy},{"units","mm"},{"has_solid",solid},{"volume_mm3",nullptr}};
 result["model_type"]=isasm?"assembly":"part";if(isasm)result["components"]=assembly_inspection();else{ProMdlsubtype subtype;if(!ProMdlSubtypeGet(board,&subtype)&&subtype==PROMDLSTYPE_PART_SHEETMETAL)result["model_type"]="sheetmetal";}
 if(solid){ProMassProperty mp;ProError e=ProSolidMassPropertyWithDensityGet((ProSolid)board,nullptr,PRO_MP_DENS_USE_ALWAYS,1,&mp);result["volume_query_code"]=e;if(!e)result["volume_mm3"]=mp.volume;}
 planes.clear();CK(ProSolidFeatVisit((ProSolid)board,datum_cb,nullptr,nullptr));J ds=J::array();for(auto p:planes)ds.push_back({{"id",p.id},{"normal",xyz(p.n)},{"origin",xyz(p.o)}});result["datum_planes"]=ds;ProModelitem owner;CK(ProMdlToModelitem(board,&owner));J params=J::object();ProParameterVisit(&owner,nullptr,parameter_cb,&params);result["parameters"]=params;return result;
}
static ProSelection resolve(const J& r){
 std::string kind=r.at("kind");if(kind=="part"){ProModelitem mi;CK(ProMdlToModelitem(board,&mi));ProSelection s;CK(ProSelectionAlloc(nullptr,&mi,&s));return s;}if(kind=="csys"||kind=="point"||kind=="quilt")return selection(r.at("id"),kind=="csys"?PRO_CSYS:kind=="point"?PRO_POINT:PRO_QUILT);if(kind=="feature")return selection(feature_id(r.contains("label")?r["label"]:r["id"]),PRO_FEATURE);
 if(kind=="body"){int id=r.value("id",-1);if(id<0){ProSolidBody b;CK(ProSolidDefaultBodyGet((ProSolid)board,&b));id=b.id;}return selection(id,PRO_BODY);}
 if(kind=="surface"||kind=="edge"||kind=="axis"||kind=="curve"||kind=="dimension"){int id=r.at("id");return selection(id,kind=="surface"?PRO_SURFACE:kind=="edge"?PRO_EDGE:kind=="axis"?PRO_AXIS:kind=="curve"?PRO_CURVE:PRO_DIMENSION);}
 if(kind=="plane"||kind=="datum_plane"){
  J state=inspection(false);J candidates=kind=="datum_plane"?state["datum_planes"]:state["surfaces"];V desired;
  if(r.contains("normal"))desired=normalized(vec(r["normal"]));else{std::string axis=r.value("axis","z");desired=axis=="x"?V{1,0,0}:axis=="y"?V{0,1,0}:V{0,0,1};}
  double offset=r.value("offset",0.0);std::vector<int> matches;for(auto& p:candidates){if(!p.contains("normal"))continue;V normal=normalized(vec(p["normal"])),origin=vec(p["origin"]);if(fabs(fabs(dot(normal,desired))-1)<1e-7&&fabs(dot(origin,desired)-offset)<1e-6)matches.push_back(p["id"].get<int>());}if(kind=="datum_plane"&&fabs(offset)<1e-9&&matches.size()>1)matches={*std::min_element(matches.begin(),matches.end())};if(matches.size()!=1)throw std::runtime_error("Plane reference must identify exactly one surface; inspect the model and use a surface ID");return selection(matches[0],PRO_SURFACE);
 }
 if(kind=="datum_axis_feature"){ProFeature f=feature(r.at("label"));J ids=J::array();CK(ProFeatureGeomitemVisit(&f,PRO_AXIS,collect_geom_ids,nullptr,&ids));if(ids.size()!=1)throw std::runtime_error("Datum feature must have one axis");return selection(ids[0]["id"],PRO_AXIS);}
 if(kind=="datum_feature"){
  int fid=feature_id(r.at("label"));ProFeature f=feature(fid);planes.clear();CK(ProFeatureGeomitemVisit(&f,PRO_SURFACE,geom_cb,nullptr,nullptr));if(planes.size()!=1)throw std::runtime_error("Datum feature does not contain one plane");return selection(planes[0].id,PRO_SURFACE);
 }
 throw std::runtime_error("Unknown model reference kind: "+kind);
}
static void set_refs(ProElement e,const J& refs){ProReference* values=nullptr;CK(ProArrayAlloc((int)refs.size(),sizeof(ProReference),1,(ProArray*)&values));for(size_t i=0;i<refs.size();i++){ProSelection s=resolve(refs[i]);CK(ProSelectionToReference(s,&values[i]));ProSelectionFree(&s);}CK(ProElementReferencesSet(e,values));ProArrayFree((ProArray*)&values);}
static void remember(const J& op,ProFeature f,J extra=J::object()){std::string label=op.at("label");extra["feature_id"]=f.id;extra["op"]=op.at("op");aliases[label]=extra;}
static void body_options(ProElement root,const J& op){std::string mode=op.value("mode","add");bool new_body=op.value("new_body",false);ProElement b=node(root,PRO_E_BODY);if(mode=="cut"){integer(b,PRO_E_BODY_USE,PRO_BODY_USE_ALL);return;}J state=inspection();if(!state["has_solid"].get<bool>()||new_body)integer(b,PRO_E_BODY_USE,PRO_BODY_USE_NEW);else{integer(b,PRO_E_BODY_USE,PRO_BODY_USE_SELECTED);ProSelection s=resolve({{"kind","body"}});ref(b,PRO_E_BODY_SELECT,s);ProSelectionFree(&s);}}
static ProFeature offset_plane(const J& reference,double offset,const std::wstring& name,double* angle=nullptr,const J* axis=nullptr){
 ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,PRO_FEAT_DATUM);text(root,PRO_E_STD_FEATURE_NAME,name.c_str());ProElement constraints=node(root,PRO_E_DTMPLN_CONSTRAINTS);ProElement c=node(constraints,PRO_E_DTMPLN_CONSTRAINT);ProSelection s=resolve(reference);integer(c,PRO_E_DTMPLN_CONSTR_TYPE,angle?PRO_DTMPLN_ANG:PRO_DTMPLN_OFFS);ref(c,PRO_E_DTMPLN_CONSTR_REF,s);real(c,angle?PRO_E_DTMPLN_CONSTR_REF_ANGLE:PRO_E_DTMPLN_CONSTR_REF_OFFSET,angle?*angle:offset);ProSelectionFree(&s);
 if(angle){if(!axis)throw std::runtime_error("Angled plane requires an axis");ProElement through=node(constraints,PRO_E_DTMPLN_CONSTRAINT);integer(through,PRO_E_DTMPLN_CONSTR_TYPE,PRO_DTMPLN_THRU);s=resolve(*axis);ref(through,PRO_E_DTMPLN_CONSTR_REF,s);ProSelectionFree(&s);}ProFeature f=create(root);CK(ProElementFree(&root));return f;
}
struct Frame {V origin,u,v,n;int surface,orientation;};
static Frame sketch_frame(const J& op){
 Frame f={};J p=op.at("plane");if(p.is_string()){
  std::string name=p;int axis=name=="XY"?2:name=="XZ"?1:0;f.n=axis==2?V{0,0,1}:axis==1?V{0,-1,0}:V{1,0,0};f.u=axis==0?V{0,1,0}:V{1,0,0};f.v=cross(f.n,f.u);double offset=op.value("offset",0.0);f.origin=axis==2?V{0,0,offset}:axis==1?V{0,offset,0}:V{offset,0,0};
  J reference={{"kind","datum_plane"},{"axis",axis==0?"x":axis==1?"y":"z"},{"offset",0}};if(fabs(offset)>1e-9){auto df=offset_plane(reference,offset,wide(op.at("label").get<std::string>()+"_plane"));planes.clear();CK(ProFeatureGeomitemVisit(&df,PRO_SURFACE,geom_cb,nullptr,nullptr));if(planes.size()!=1)throw PRO_TK_GENERAL_ERROR;f.surface=planes[0].id;}else{ProSelection s=resolve(reference);ProModelitem mi;CK(ProSelectionModelitemGet(s,&mi));f.surface=mi.id;ProSelectionFree(&s);}
 }else{
  ProSelection s=resolve(p.at("reference"));ProModelitem mi;CK(ProSelectionModelitemGet(s,&mi));f.surface=mi.id;ProSurface sf;CK(ProSurfaceInit((ProSolid)board,f.surface,&sf));ProGeomitemdata* d;CK(ProSurfaceDataGet(sf,&d));auto shape=d->data.p_surface_data;if(!shape||shape->type!=PRO_SRF_PLANE)throw std::runtime_error("Sketch support must be planar");f.n=normalized({shape->srf_shape.plane.e3[0],shape->srf_shape.plane.e3[1],shape->srf_shape.plane.e3[2]});double dist=dot(f.n,{shape->srf_shape.plane.origin[0],shape->srf_shape.plane.origin[1],shape->srf_shape.plane.origin[2]});f.origin=p.contains("origin")?vec(p["origin"]):scale(f.n,dist);if(fabs(dot(f.n,f.origin)-dist)>1e-6)throw std::runtime_error("Sketch origin is outside support plane");V preferred=p.contains("u_axis")?vec(p["u_axis"]):(fabs(f.n[0])<0.9?V{1,0,0}:V{0,1,0});f.u=normalized(add(preferred,scale(f.n,-dot(preferred,f.n))));f.v=cross(f.n,f.u);ProGeomitemdataFree(&d);ProSelectionFree(&s);
 }
 double best=10;f.orientation=-1;planes.clear();CK(ProSolidFeatVisit((ProSolid)board,datum_cb,nullptr,nullptr));for(auto p:planes){V normal={p.n[0],p.n[1],p.n[2]};double d=fabs(dot(f.n,normal));if(d<best&&d<0.95){best=d;f.orientation=p.id;}}if(f.orientation<0)throw std::runtime_error("No sketch orientation reference");return f;
}
static ProSectionPointType point_type(const std::string& s){return s=="start"?PRO_ENT_START:s=="end"?PRO_ENT_END:s=="center"?PRO_ENT_CENTER:PRO_ENT_WHOLE;}
static void redefine(ProFeature* f,ProElement root){ProFeatureCreateOptions* options=nullptr;CK(ProArrayAlloc(1,sizeof(ProFeatureCreateOptions),1,(ProArray*)&options));options[0]=PRO_FEAT_CR_NO_OPTS;ProErrorlist es={};ProError e=ProFeatureWithoptionsRedefine(nullptr,f,root,options,PRO_REGEN_NO_FLAGS,&es);errors(es);ProArrayFree((ProArray*)&options);check(e,"CompleteFeature");}
static void sketch(const J& op){
 Frame frame=sketch_frame(op);ProSelection plane_ref=selection(frame.surface,PRO_SURFACE),orient=selection(frame.orientation,PRO_SURFACE);ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,PRO_FEAT_CURVE);integer(root,PRO_E_CURVE_TYPE,PRO_CURVE_TYPE_SKETCHED);std::wstring label=wide(op.at("label"));text(root,PRO_E_STD_FEATURE_NAME,label.c_str());ProElement setup=node(node(root,PRO_E_STD_SECTION),PRO_E_STD_SEC_SETUP_PLANE);ref(setup,PRO_E_STD_SEC_PLANE,plane_ref);integer(setup,PRO_E_STD_SEC_PLANE_VIEW_DIR,PRO_SEC_VIEW_DIR_SIDE_ONE);integer(setup,PRO_E_STD_SEC_PLANE_ORIENT_DIR,PRO_SEC_ORIENT_DIR_UP);ref(setup,PRO_E_STD_SEC_PLANE_ORIENT_REF,orient);
 ProFeature f=create(root,PRO_FEAT_CR_INCOMPLETE_FEAT);CK(ProElementFree(&root));CK(ProFeatureElemtreeExtract(&f,nullptr,PRO_FEAT_EXTRACT_NO_OPTS,&root));ProElement sk=get(root,{PRO_E_STD_SECTION,PRO_E_SKETCHER});ProSection section=nullptr;CK(ProElementSpecialvalueGet(sk,nullptr,(ProAppData*)&section));int projected;CK(ProSectionEntityFromProjection(section,orient,&projected));
 planes.clear();CK(ProSolidFeatVisit((ProSolid)board,datum_cb,nullptr,nullptr));for(auto p:planes){V n={p.n[0],p.n[1],p.n[2]};if(p.id!=frame.orientation&&fabs(dot(n,frame.n))<0.95){ProSelection s=selection(p.id,PRO_SURFACE);ProError e=ProSectionEntityFromProjection(section,s,&projected);ProSelectionFree(&s);log("PROJECT_REFERENCE=%d code=%d entity=%d\n",p.id,e,projected);if(!e)break;}}
 ProMatrix loc;CK(ProSectionLocationGet(section,loc));for(int row=0;row<4;row++)log("SECTION_MATRIX_%d=%.9f,%.9f,%.9f,%.9f\n",row,loc[row][0],loc[row][1],loc[row][2],loc[row][3]);auto project=[&](const J& p,double* out){V w=add(frame.origin,add(scale(frame.u,p.at(0).get<double>()),scale(frame.v,p.at(1).get<double>())));for(int i=0;i<2;i++)out[i]=(w[0]-loc[3][0])*loc[i][0]+(w[1]-loc[3][1])*loc[i][1]+(w[2]-loc[3][2])*loc[i][2];};
 CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));Pro2dCoordSysdef cs={};cs.type=PRO_2D_COORD_SYS;int csid;CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&cs,&csid));std::map<std::string,int> entities;
 auto add_line=[&](const std::string& name,const J& a,const J& b,bool centerline,bool construction){Pro2dLinedef l={};l.type=centerline?PRO_2D_CENTER_LINE:PRO_2D_LINE;project(a,l.end1);project(b,l.end2);log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n",name.c_str(),l.end1[0],l.end1[1],l.end2[0],l.end2[1]);int id;CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&l,&id));if(!centerline)CK(ProSectionEntityConstructionSet(section,id,construction?PRO_B_TRUE:PRO_B_FALSE));entities[name]=id;};
 for(auto e:op.at("entities")){
  std::string type=e.at("type"),name=e.at("name");bool construction=e.value("construction",false);int id=-1;
  if(type=="line"||type=="centerline"){add_line(name,e["start"],e["end"],type=="centerline",construction);continue;}
  if(type=="rectangle"||type=="polyline"){
   J points;if(type=="rectangle"){auto a=e["min"],b=e["max"];points=J::array({a,J::array({b[0],a[1]}),b,J::array({a[0],b[1]})});}else points=e["points"];int count=(int)points.size(),segments=count-1+((type=="rectangle"||e.value("closed",false))?1:0);for(int i=0;i<segments;i++)add_line(name+"_"+std::to_string(i),points[i],points[(i+1)%count],false,construction);continue;
  }
  if(type=="circle"){Pro2dCircledef c={};c.type=PRO_2D_CIRCLE;project(e["center"],c.center);c.radius=e["radius"];CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&c,&id));}
  else if(type=="arc"){Pro2dArcdef a={};a.type=PRO_2D_ARC;project(e["center"],a.center);a.radius=e["radius"];double start=e["start_angle"].get<double>()*acos(-1.0)/180,end=e["end_angle"].get<double>()*acos(-1.0)/180;double p[2],q[2];J center=e["center"];project(J::array({center[0].get<double>()+a.radius*cos(start),center[1].get<double>()+a.radius*sin(start)}),p);project(J::array({center[0].get<double>()+a.radius*cos(end),center[1].get<double>()+a.radius*sin(end)}),q);a.start_angle=atan2(p[1]-a.center[1],p[0]-a.center[0]);a.end_angle=atan2(q[1]-a.center[1],q[0]-a.center[0]);if(dot(V{loc[2][0],loc[2][1],loc[2][2]},frame.n)<0)std::swap(a.start_angle,a.end_angle);CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&a,&id));}
  else if(type=="spline"){auto points=e["points"];std::vector<std::array<double,2>> xy(points.size());for(size_t i=0;i<xy.size();i++)project(points[i],xy[i].data());Pro2dSplinedef s={};s.type=PRO_2D_SPLINE;s.tangency_type=e.value("closed",false)?PRO_2D_SPLINE_TAN_PERIODIC:PRO_2D_SPLINE_TAN_NONE;s.n_points=(unsigned)xy.size();s.point_arr=(Pro2dPnt*)xy.data();CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&s,&id));}
  else if(type=="ellipse"){Pro2dEllipsedef ell={};ell.type=PRO_2D_ELLIPSE;project(e["center"],ell.origin);double align=fabs(dot(frame.u,V{loc[0][0],loc[0][1],loc[0][2]}));if(align>0.99999){ell.x_radius=e["x_radius"];ell.y_radius=e["y_radius"];}else if(align<0.00001){ell.x_radius=e["y_radius"];ell.y_radius=e["x_radius"];}else throw std::runtime_error("Ellipse axes must align with the section axes");CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&ell,&id));}
  else throw std::runtime_error("Unknown sketch entity type");CK(ProSectionEntityConstructionSet(section,id,construction?PRO_B_TRUE:PRO_B_FALSE));entities[name]=id;
 }
 if(!op.value("constraints",J::array()).empty()){
  CK(ProSectionIntentManagerModeSet(section,PRO_B_TRUE));std::map<std::string,ProConstraintType> ct={{"coincident",PRO_CONSTRAINT_SAME_POINT},{"horizontal",PRO_CONSTRAINT_HORIZONTAL_ENT},{"vertical",PRO_CONSTRAINT_VERTICAL_ENT},{"point_on",PRO_CONSTRAINT_PNT_ON_ENT},{"tangent",PRO_CONSTRAINT_TANGENT_ENTS},{"perpendicular",PRO_CONSTRAINT_ORTHOG_ENTS},{"equal_radius",PRO_CONSTRAINT_EQUAL_RADII},{"parallel",PRO_CONSTRAINT_PARALLEL_ENTS},{"equal_length",PRO_CONSTRAINT_EQUAL_SEGMENTS},{"collinear",PRO_CONSTRAINT_COLLINEAR_LINES}};
  for(auto c:op["constraints"]){std::vector<ProSelection> refs;for(auto r:c["refs"]){ProSelection s;Pro2dPnt p={0,0};CK(ProSectionEntityGetSelected(section,entities.at(r["entity"].get<std::string>()),point_type(r.value("point","whole")),p,0,&s));refs.push_back(s);}int cid;ProError err=ProSectionConstraintCreate(section,refs.data(),(int)refs.size(),ct.at(c["type"]),&cid);for(auto s:refs)ProSelectionFree(&s);if(err!=PRO_TK_E_FOUND)check(err,"CreateSketchConstraint");}CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));
 }
 std::map<std::string,ProSecdimType> dt={{"length",PRO_TK_DIM_LINE},{"radius",PRO_TK_DIM_RAD},{"diameter",PRO_TK_DIM_DIA},{"distance",PRO_TK_DIM_PNT_PNT},{"horizontal",PRO_TK_DIM_PNT_PNT_HORIZ},{"vertical",PRO_TK_DIM_PNT_PNT_VERT},{"line_distance",PRO_TK_DIM_LINE_LINE},{"angle",PRO_TK_DIM_LINES_ANGLE},{"arc_angle",PRO_TK_DIM_ARC_ANGLE},{"ellipse_x_radius",PRO_TK_DIM_ELLIPSE_X_RADIUS},{"ellipse_y_radius",PRO_TK_DIM_ELLIPSE_Y_RADIUS}};J dims=J::object();
 for(auto d:op.value("dimensions",J::array())){std::vector<int> ids;std::vector<ProSectionPointType> senses;for(auto r:d["refs"]){ids.push_back(entities.at(r["entity"].get<std::string>()));senses.push_back(point_type(r.value("point","whole")));}double place[2];project(d["position"],place);int id;CK(ProSecdimCreate(section,ids.data(),senses.data(),(int)ids.size(),dt.at(d["type"]),place,&id));CK(ProSecdimValueSet(section,id,d["value"]));dims[d["name"].get<std::string>()]=id;}
 CK(ProSectionEpsilonSet(section,0.0001));ProWSecerror secerr=nullptr;CK(ProSecerrorAlloc(&secerr));if(op["plane"].is_object()){CK(ProSectionIntentManagerModeSet(section,PRO_B_TRUE));log("INTENT_SOLVE=%d\n",ProSectionSolve(section,&secerr));CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));}log("SKETCH_SOLVE=%d\n",ProSectionSolve(section,&secerr));int solve_errors=0;ProSecerrorCount(&secerr,&solve_errors);for(int i=0;i<solve_errors;i++){ProMsg msg;ProSecerrorMsgGet(secerr,i,msg);log("SOLVE_ERROR=%ls\n",msg);}ProError solved=ProSectionAutodim(section,&secerr);if(solved){int count=0;ProSecerrorCount(&secerr,&count);for(int i=0;i<count;i++){ProMsg msg;ProSecerrorMsgGet(secerr,i,msg);log("SKETCH_ERROR=%ls\n",msg);}}check(solved,"AutodimensionSketch");CK(ProSectionRegenerate(section,&secerr));CK(ProSecerrorFree(&secerr));CK(ProElementSpecialvalueSet(sk,(ProAppData)section));redefine(&f,root);CK(ProFeatureElemtreeFree(&f,root));ProSelectionFree(&plane_ref);ProSelectionFree(&orient);
 J ids=J::object();for(auto item:entities)ids[item.first]=item.second;remember(op,f,{{"entity_ids",ids},{"dimension_ids",dims},{"normal",frame.n},{"origin",frame.origin},{"u_axis",frame.u},{"v_axis",frame.v},{"section_normal_sign",dot(V{loc[2][0],loc[2][1],loc[2][2]},frame.n)>0?1:-1}});
}
static void extrude_or_revolve(const J& op,bool revolve){
 ProFeature sketch_f=feature(op.at("sketch"));ProSelection s=selection(sketch_f.id,PRO_FEATURE);std::string mode=op.value("mode","add"),direction=op.value("direction","positive");ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,mode=="cut"?PRO_FEAT_CUT:mode=="surface"?PRO_FEAT_DATUM_SURF:PRO_FEAT_PROTRUSION);integer(root,PRO_E_FEATURE_FORM,revolve?PRO_REVOLVE:PRO_EXTRUDE);integer(root,PRO_E_EXT_SURF_CUT_SOLID_TYPE,mode=="surface"?PRO_EXT_FEAT_TYPE_SURFACE:PRO_EXT_FEAT_TYPE_SOLID);integer(root,PRO_E_REMOVE_MATERIAL,mode=="cut"?PRO_EXT_MATERIAL_REMOVE:PRO_EXT_MATERIAL_ADD);text(root,PRO_E_STD_FEATURE_NAME,wide(op.at("label")).c_str());ref(node(root,PRO_E_STD_SECTION),PRO_E_SEC_USE_SKETCH,s);ProSelectionFree(&s);if(mode!="surface")body_options(root,op);
 int sign=1;if(op["sketch"].is_string()){std::string label=op["sketch"];sign=aliases[label].value("section_normal_sign",1);}if(direction=="negative")sign=-sign;log("DIRECTION_SIGN=%d\n",sign);integer(root,PRO_E_STD_DIRECTION,sign>0?1:-1);
 if(op.contains("thin")){integer(root,PRO_E_FEAT_FORM_IS_THIN,revolve?PRO_REV_FEAT_FORM_THIN:PRO_EXT_FEAT_FORM_THIN);real(root,PRO_E_THICKNESS,op["thin"]);integer(root,PRO_E_STD_MATRLSIDE,revolve?PRO_REV_MATERIAL_BOTH_SIDES:PRO_EXT_MATERIAL_BOTH_SIDES);}
 if(revolve){
  if(op.contains("axis")){integer(root,PRO_E_REVOLVE_AXIS_OPT,PRO_REV_AXIS_EXT_REF);ProSelection a=resolve(op["axis"]);ref(root,PRO_E_REVOLVE_AXIS,a);ProSelectionFree(&a);}else integer(root,PRO_E_REVOLVE_AXIS_OPT,PRO_REV_AXIS_INT_REF);
  ProElement angles=node(root,PRO_E_REV_ANGLE),from=node(angles,PRO_E_REV_ANGLE_FROM),to=node(angles,PRO_E_REV_ANGLE_TO);integer(from,PRO_E_REV_ANGLE_FROM_TYPE,PRO_REV_ANG_FROM_NONE);integer(to,PRO_E_REV_ANGLE_TO_TYPE,direction=="symmetric"?PRO_REV_ANG_SYMMETRIC:PRO_REV_ANG_TO_ANGLE);real(to,PRO_E_REV_ANGLE_TO_VAL,op.value("angle",360.0));
 }else{ProElement dep=node(root,PRO_E_STD_EXT_DEPTH),from=node(dep,PRO_E_EXT_DEPTH_FROM),to=node(dep,PRO_E_EXT_DEPTH_TO);integer(from,PRO_E_EXT_DEPTH_FROM_TYPE,PRO_EXT_DEPTH_FROM_NONE);integer(to,PRO_E_EXT_DEPTH_TO_TYPE,op.value("depth_type","blind")=="through_all"?PRO_EXT_DEPTH_TO_ALL:direction=="symmetric"?PRO_EXT_DEPTH_SYMMETRIC:PRO_EXT_DEPTH_TO_BLIND);if(op.value("depth_type","blind")!="through_all")real(to,PRO_E_EXT_DEPTH_TO_VALUE,op.at("depth"));}
 ProFeature f=create(root);CK(ProElementFree(&root));remember(op,f);J state=inspection();int active=0;for(auto b:state["bodies"])if(b["state"].get<int>()==PRO_BODY_STATE_ACTIVE)active++;if(active==1&&!op.value("skip_empty_body_cleanup",false))remove_empty_body();
}
static void generic_hole(const J& op){
 ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,PRO_FEAT_HOLE);integer(root,PRO_E_FEATURE_FORM,PRO_HLE_TYPE_STRAIGHT);text(root,PRO_E_STD_FEATURE_NAME,wide(op.at("label")).c_str());ProElement com=node(root,PRO_E_HLE_COM);integer(com,PRO_E_HLE_TYPE_NEW,PRO_HLE_NEW_TYPE_STRAIGHT);integer(com,PRO_E_HLE_MAKE_LIGHTWT,PRO_HLE_REGULAR);real(com,PRO_E_DIAMETER,op.at("diameter"));ProElement dep=node(com,PRO_E_HOLE_STD_DEPTH);ProElement to=node(dep,PRO_E_HOLE_DEPTH_TO);integer(to,PRO_E_HOLE_DEPTH_TO_TYPE,op.contains("depth")?PRO_HLE_STRGHT_BLIND_DEPTH:PRO_HLE_STRGHT_THRU_ALL_DEPTH);if(op.contains("depth"))real(to,PRO_E_EXT_DEPTH_TO_VALUE,op.at("depth"));integer(node(dep,PRO_E_HOLE_DEPTH_FROM),PRO_E_HOLE_DEPTH_FROM_TYPE,PRO_HLE_STRGHT_NONE_DEPTH);integer(com,PRO_E_HLE_CRDIR_FLIP,op.value("flip",false)?PRO_HLE_CR_IN_SIDE_TWO:PRO_HLE_CR_IN_SIDE_ONE);integer(com,PRO_E_HLE_TOP_CLEARANCE,PRO_HOLE_GEN_CLRNCE);integer(com,PRO_E_HLE_ADD_PARAMETERS,PRO_HOLE_NO_PARAMETERS_FLAG);integer(com,PRO_E_HLE_ADD_NOTE,PRO_HOLE_NO_NOTE_FLAG);
 ProElement placement=node(root,PRO_E_HLE_PLACEMENT);ProSelection face=resolve(op["placement"]),r1=resolve(op["reference1"]),r2=resolve(op["reference2"]);ref(placement,PRO_E_HLE_PRIM_REF,face);integer(placement,PRO_E_HLE_PL_TYPE,PRO_HLE_PL_TYPE_LIN);ref(placement,PRO_E_HLE_DIM_REF1,r1);ref(placement,PRO_E_HLE_DIM_REF2,r2);double a=op.value("offset1",0.0),b=op.value("offset2",0.0);integer(placement,PRO_E_HLE_PLC_ALIGN_OPT1,a==0?PRO_HLE_PLC_ALIGN:PRO_HLE_PLC_NOT_ALIGN);integer(placement,PRO_E_HLE_PLC_ALIGN_OPT2,b==0?PRO_HLE_PLC_ALIGN:PRO_HLE_PLC_NOT_ALIGN);real(placement,PRO_E_HLE_DIM_DIST1,a);real(placement,PRO_E_HLE_DIM_DIST2,b);integer(node(root,PRO_E_BODY),PRO_E_BODY_USE,PRO_BODY_USE_ALL);ProFeature f=create(root);CK(ProElementFree(&root));ProSelectionFree(&face);ProSelectionFree(&r1);ProSelectionFree(&r2);remember(op,f);
}
static void curve_collection(ProElement element,const J& refs){
 ProCollection coll;CK(ProCrvcollectionAlloc(&coll));for(auto item:refs){ProSelection s=resolve(item);ProReference reference;CK(ProSelectionToReference(s,&reference));ProCrvcollinstr instr;CK(ProCrvcollinstrAlloc(PRO_CURVCOLL_ADD_ONE_INSTR,&instr));CK(ProCrvcollinstrReferenceAdd(instr,reference));CK(ProCrvcollectionInstructionAdd(coll,instr));CK(ProCrvcollinstrFree(instr));ProSelectionFree(&s);}CK(ProElementCollectionSet(element,coll));CK(ProCollectionFree(&coll));
}
static void generic_round(const J& op,bool chamfer){
 ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,chamfer?PRO_FEAT_CHAMFER:PRO_FEAT_ROUND);text(root,PRO_E_STD_FEATURE_NAME,wide(op.at("label")).c_str());ProElement sets=node(root,PRO_E_RNDCH_SETS);
 for(auto refs:op["references"]){ProElement set=node(sets,PRO_E_RNDCH_SET);if(chamfer){integer(set,PRO_E_RNDCH_DIMENSIONAL_SCHEMA,PRO_CHM_D_X_D);integer(set,PRO_E_RNDCH_CHAMFER_SHAPE,PRO_CHM_TANGENT_LEGS);}else{integer(set,PRO_E_RNDCH_SHAPE_OPTIONS,PRO_ROUND_TYPE_CONSTANT);integer(node(set,PRO_E_RNDCH_COMPOUND_CONIC),PRO_E_RNDCH_CONIC_TYPE,PRO_ROUND_CONIC_DISABLE);integer(node(set,PRO_E_RNDCH_COMPOUND_SPINE),PRO_E_RNDCH_BALL_SPINE,PRO_ROUND_ROLLING_BALL);}ProElement r=node(set,PRO_E_RNDCH_REFERENCES);
  if(refs.contains("surfaces")){integer(r,PRO_E_RNDCH_REFERENCE_TYPE,PRO_ROUND_REF_SURF_SURF);ProSelection a=resolve(refs["surfaces"][0]),b=resolve(refs["surfaces"][1]);ref(r,PRO_E_RNDCH_REFERENCE_SURFACE1,a);ref(r,PRO_E_RNDCH_REFERENCE_SURFACE2,b);ProSelectionFree(&a);ProSelectionFree(&b);}else{integer(r,PRO_E_RNDCH_REFERENCE_TYPE,PRO_ROUND_REF_EDGE);ProSelection e=resolve(refs.at("edge"));ProSelectionFree(&e);curve_collection(node(r,PRO_E_STD_CURVE_COLLECTION_APPL),J::array({refs.at("edge")}));}ProElement radius=node(node(set,PRO_E_RNDCH_RADII),PRO_E_RNDCH_RADIUS),leg=node(radius,PRO_E_RNDCH_LEG1);integer(leg,PRO_E_RNDCH_LEG_TYPE,PRO_ROUND_RADIUS_TYPE_VALUE);real(leg,PRO_E_RNDCH_LEG_VALUE,op.at("size"));}
 integer(root,PRO_E_RNDCH_ATTACH_TYPE,PRO_ROUND_ATTACHED);node(root,PRO_E_RNDCH_TRANSITIONS);ProFeature f=create(root);CK(ProElementFree(&root));remember(op,f);
}
static void generic_shell(const J& op){ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,PRO_FEAT_SHELL);text(root,PRO_E_STD_FEATURE_NAME,wide(op.at("label")).c_str());ProElement b=node(root,PRO_E_BODY);integer(b,PRO_E_BODY_USE,PRO_BODY_USE_SELECTED);ProSelection body=resolve({{"kind","body"}});ref(b,PRO_E_BODY_SELECT,body);ProSelectionFree(&body);real(root,PRO_E_SHELL_THICK,op.at("thickness"));integer(root,PRO_E_SHELL_FLIP,op.value("outward",false)?PRO_SHELL_OUTSIDE:PRO_SHELL_INSIDE);if(!op["remove_surfaces"].empty())set_refs(node(root,PRO_E_SHELL_SRF),op["remove_surfaces"]);ProFeature f=create(root);CK(ProElementFree(&root));remember(op,f);}
static ProElement tree_from_json(const J& spec,ProElement parent=nullptr,int depth=0){if(depth>40)throw std::runtime_error("Element tree is too deep");ProElement e=node(parent,constant(spec.at("id")));if(spec.contains("integer"))CK(ProElementIntegerSet(e,constant(spec["integer"])));if(spec.contains("double")){CK(ProElementDecimalsSet(e,8));CK(ProElementDoubleSet(e,spec["double"]));}if(spec.contains("string"))CK(ProElementWstringSet(e,const_cast<wchar_t*>(wide(spec["string"]).c_str())));if(spec.contains("reference")){ProSelection s=resolve(spec["reference"]);ProReference r;CK(ProSelectionToReference(s,&r));CK(ProElementReferenceSet(e,r));ProSelectionFree(&s);}if(spec.contains("references"))set_refs(e,spec["references"]);if(spec.contains("curve_collection"))curve_collection(e,spec["curve_collection"]);for(auto child:spec.value("children",J::array()))tree_from_json(child,e,depth+1);return e;}
static void parameters(const J& op){ProModelitem owner;CK(ProMdlToModelitem(board,&owner));for(auto it=op["values"].begin();it!=op["values"].end();++it){ProName name;wcscpy_s(name,wide(it.key()).c_str());ProParamvalue v={};J value=it.value();if(value.is_boolean()){v.type=PRO_PARAM_BOOLEAN;v.value.l_val=value.get<bool>()?1:0;}else if(value.is_number_integer()){v.type=PRO_PARAM_INTEGER;v.value.i_val=value.get<int>();}else if(value.is_number()){v.type=PRO_PARAM_DOUBLE;v.value.d_val=value.get<double>();}else{v.type=PRO_PARAM_STRING;wcscpy_s(v.value.s_val,wide(value).c_str());}ProParameter param;ProError e=ProParameterInit(&owner,name,&param);if(e==PRO_TK_E_NOT_FOUND)CK(ProParameterWithUnitsCreate(&owner,name,&v,nullptr,&param));else{check(e,"FindParameter");CK(ProParameterValueWithUnitsSet(&param,&v,nullptr));}}}
static void write_stl(const std::wstring& file){
 ProSurfaceTessellationData* surfaces=nullptr;CK(ProPartTessellate((ProPart)board,0.05,0.1,PRO_B_FALSE,&surfaces));int n;CK(ProArraySizeGet((ProArray)surfaces,&n));std::ofstream out(file);if(!out)throw std::runtime_error("Cannot open STL output");out.precision(12);out<<"solid creo_native\n";int count=0;
 for(int i=0;i<n;i++){auto s=surfaces[i];for(int j=0;j<s.n_facets;j++){auto indices=s.facets[j];V a={s.vertices[indices[0]][0],s.vertices[indices[0]][1],s.vertices[indices[0]][2]},b={s.vertices[indices[1]][0],s.vertices[indices[1]][1],s.vertices[indices[1]][2]},c={s.vertices[indices[2]][0],s.vertices[indices[2]][1],s.vertices[indices[2]][2]};V normal=normalized(cross(add(b,scale(a,-1)),add(c,scale(a,-1))));out<<"facet normal "<<normal[0]<<' '<<normal[1]<<' '<<normal[2]<<"\n outer loop\n";for(auto v:{a,b,c})out<<" vertex "<<v[0]<<' '<<v[1]<<' '<<v[2]<<'\n';out<<" endloop\nendfacet\n";count++;}}out<<"endsolid creo_native\n";out.close();CK(ProPartTessellationFree(&surfaces));if(!count)throw std::runtime_error("No solid facets to export");
}
static void generic_pattern(const J& op){
 ProFeature leader=feature(op["feature"]);ProElement root=node(nullptr,PRO_E_PATTERN_ROOT);integer(root,PRO_E_GENPAT_TYPE,PRO_GENPAT_DIM_DRIVEN);integer(root,PRO_E_GENPAT_REGEN_METHOD,PRO_PAT_GENERAL);ProElement dims=node(root,PRO_E_GENPAT_DIM),dir=node(dims,PRO_E_GENPAT_DIM_FIRST_DIR),item=node(dir,PRO_E_GENPAT_DIM_DIR_COMPOUND);ProSelection d=resolve({{"kind","dimension"},{"id",op["dimension_id"]}});ref(item,PRO_E_GENPAT_DIR_DIMENSION,d);ProSelectionFree(&d);integer(item,PRO_E_GENPAT_DIR_VAR_TYPE,PRO_PAT_VALUE_DRIVEN);real(item,PRO_E_GENPAT_DIR_VAR_VALUE,op["increment"]);integer(dims,PRO_E_GENPAT_DIM_FIRST_DIR_NUM_INST,op["count"]);CK(ProPatternCreate(&leader,PRO_FEAT_PATTERN,root));CK(ProElementFree(&root));ProPattern pat;ProFeature head;CK(ProFeaturePatternGet(&leader,PRO_FEAT_PATTERN,&pat));CK(ProPatternHeaderGet(&pat,&head));ProName name;wcscpy_s(name,wide(op["label"]).c_str());CK(ProModelitemNameSet(&head,name));remember(op,head,{{"leader_id",leader.id}});
}
static J populate_profile(ProSection section,const J& op){
 J entities_spec=op.at("profile");Frame frame={};frame.n={0,0,1};frame.u={1,0,0};ProMatrix loc={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};auto project=[](const J& p,double* out){out[0]=p.at(0).get<double>();out[1]=p.at(1).get<double>();};
 CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));Pro2dCoordSysdef cs={};cs.type=PRO_2D_COORD_SYS;int csid;CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&cs,&csid));std::map<std::string,int> entities;
 auto add_line=[&](const std::string& name,const J& a,const J& b,bool centerline,bool construction){Pro2dLinedef l={};l.type=centerline?PRO_2D_CENTER_LINE:PRO_2D_LINE;project(a,l.end1);project(b,l.end2);log("LINE_%s=%.9f,%.9f -> %.9f,%.9f\n",name.c_str(),l.end1[0],l.end1[1],l.end2[0],l.end2[1]);int id;CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&l,&id));if(!centerline)CK(ProSectionEntityConstructionSet(section,id,construction?PRO_B_TRUE:PRO_B_FALSE));entities[name]=id;};
 for(auto e:entities_spec){
  std::string type=e.at("type"),name=e.at("name");bool construction=e.value("construction",false);int id=-1;
  if(type=="line"||type=="centerline"){add_line(name,e["start"],e["end"],type=="centerline",construction);continue;}
  if(type=="rectangle"||type=="polyline"){
   J points;if(type=="rectangle"){auto a=e["min"],b=e["max"];points=J::array({a,J::array({b[0],a[1]}),b,J::array({a[0],b[1]})});}else points=e["points"];int count=(int)points.size(),segments=count-1+((type=="rectangle"||e.value("closed",false))?1:0);for(int i=0;i<segments;i++)add_line(name+"_"+std::to_string(i),points[i],points[(i+1)%count],false,construction);continue;
  }
  if(type=="circle"){Pro2dCircledef c={};c.type=PRO_2D_CIRCLE;project(e["center"],c.center);c.radius=e["radius"];CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&c,&id));}
  else if(type=="arc"){Pro2dArcdef a={};a.type=PRO_2D_ARC;project(e["center"],a.center);a.radius=e["radius"];double start=e["start_angle"].get<double>()*acos(-1.0)/180,end=e["end_angle"].get<double>()*acos(-1.0)/180;double p[2],q[2];J center=e["center"];project(J::array({center[0].get<double>()+a.radius*cos(start),center[1].get<double>()+a.radius*sin(start)}),p);project(J::array({center[0].get<double>()+a.radius*cos(end),center[1].get<double>()+a.radius*sin(end)}),q);a.start_angle=atan2(p[1]-a.center[1],p[0]-a.center[0]);a.end_angle=atan2(q[1]-a.center[1],q[0]-a.center[0]);if(dot(V{loc[2][0],loc[2][1],loc[2][2]},frame.n)<0)std::swap(a.start_angle,a.end_angle);CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&a,&id));}
  else if(type=="spline"){auto points=e["points"];std::vector<std::array<double,2>> xy(points.size());for(size_t i=0;i<xy.size();i++)project(points[i],xy[i].data());Pro2dSplinedef s={};s.type=PRO_2D_SPLINE;s.tangency_type=e.value("closed",false)?PRO_2D_SPLINE_TAN_PERIODIC:PRO_2D_SPLINE_TAN_NONE;s.n_points=(unsigned)xy.size();s.point_arr=(Pro2dPnt*)xy.data();CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&s,&id));}
  else if(type=="ellipse"){Pro2dEllipsedef ell={};ell.type=PRO_2D_ELLIPSE;project(e["center"],ell.origin);double align=fabs(dot(frame.u,V{loc[0][0],loc[0][1],loc[0][2]}));if(align>0.99999){ell.x_radius=e["x_radius"];ell.y_radius=e["y_radius"];}else if(align<0.00001){ell.x_radius=e["y_radius"];ell.y_radius=e["x_radius"];}else throw std::runtime_error("Ellipse axes must align with the section axes");CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&ell,&id));}
  else throw std::runtime_error("Unknown sketch entity type");CK(ProSectionEntityConstructionSet(section,id,construction?PRO_B_TRUE:PRO_B_FALSE));entities[name]=id;
 }
 if(!op.value("constraints",J::array()).empty()){
  CK(ProSectionIntentManagerModeSet(section,PRO_B_TRUE));std::map<std::string,ProConstraintType> ct={{"coincident",PRO_CONSTRAINT_SAME_POINT},{"horizontal",PRO_CONSTRAINT_HORIZONTAL_ENT},{"vertical",PRO_CONSTRAINT_VERTICAL_ENT},{"point_on",PRO_CONSTRAINT_PNT_ON_ENT},{"tangent",PRO_CONSTRAINT_TANGENT_ENTS},{"perpendicular",PRO_CONSTRAINT_ORTHOG_ENTS},{"equal_radius",PRO_CONSTRAINT_EQUAL_RADII},{"parallel",PRO_CONSTRAINT_PARALLEL_ENTS},{"equal_length",PRO_CONSTRAINT_EQUAL_SEGMENTS},{"collinear",PRO_CONSTRAINT_COLLINEAR_LINES}};
  for(auto c:op["constraints"]){std::vector<ProSelection> refs;for(auto r:c["refs"]){ProSelection s;Pro2dPnt p={0,0};CK(ProSectionEntityGetSelected(section,entities.at(r["entity"].get<std::string>()),point_type(r.value("point","whole")),p,0,&s));refs.push_back(s);}int cid;ProError err=ProSectionConstraintCreate(section,refs.data(),(int)refs.size(),ct.at(c["type"]),&cid);for(auto s:refs)ProSelectionFree(&s);if(err!=PRO_TK_E_FOUND)check(err,"CreateSketchConstraint");}CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));
 }
 std::map<std::string,ProSecdimType> dt={{"length",PRO_TK_DIM_LINE},{"radius",PRO_TK_DIM_RAD},{"diameter",PRO_TK_DIM_DIA},{"distance",PRO_TK_DIM_PNT_PNT},{"horizontal",PRO_TK_DIM_PNT_PNT_HORIZ},{"vertical",PRO_TK_DIM_PNT_PNT_VERT},{"line_distance",PRO_TK_DIM_LINE_LINE},{"angle",PRO_TK_DIM_LINES_ANGLE},{"arc_angle",PRO_TK_DIM_ARC_ANGLE},{"ellipse_x_radius",PRO_TK_DIM_ELLIPSE_X_RADIUS},{"ellipse_y_radius",PRO_TK_DIM_ELLIPSE_Y_RADIUS}};J dims=J::object();
 for(auto d:op.value("dimensions",J::array())){std::vector<int> ids;std::vector<ProSectionPointType> senses;for(auto r:d["refs"]){ids.push_back(entities.at(r["entity"].get<std::string>()));senses.push_back(point_type(r.value("point","whole")));}double place[2];project(d["position"],place);int id;CK(ProSecdimCreate(section,ids.data(),senses.data(),(int)ids.size(),dt.at(d["type"]),place,&id));CK(ProSecdimValueSet(section,id,d["value"]));dims[d["name"].get<std::string>()]=id;}

 CK(ProSectionEpsilonSet(section,0.0001));ProWSecerror err;CK(ProSecerrorAlloc(&err));ProError result=ProSectionAutodim(section,&err);if(result){int count;ProSecerrorCount(&err,&count);for(int i=0;i<count;i++){ProMsg m;ProSecerrorMsgGet(err,i,m);log("PROFILE_ERROR=%ls\n",m);}}check(result,"AutodimensionProfile");CK(ProSectionRegenerate(section,&err));ProSecerrorFree(&err);J ids=J::object();for(auto item:entities)ids[item.first]=item.second;return {{"entity_ids",ids},{"dimension_ids",dims}};
}
#include "advanced.cpp"
static void execute_operation(const J& op){
 std::string kind=op.at("op");log("PHASE=%s%s%s\n",kind.c_str(),op.contains("label")?":":"",op.value("label","").c_str());
 if(kind=="sketch")sketch(op);
 else if(kind=="extrude"||kind=="revolve")extrude_or_revolve(op,kind=="revolve");
 else if(kind=="hole")generic_hole(op);
 else if(kind=="round"||kind=="chamfer")generic_round(op,kind=="chamfer");
 else if(kind=="shell")generic_shell(op);
 else if(kind=="dimension_pattern")generic_pattern(op);
 else if(kind=="mirror")generic_mirror(op);
 else if(kind=="draft")generic_draft(op);
 else if(kind=="sweep")generic_sweep(op);
 else if(kind=="loft")generic_loft(op);
 else if(kind=="sheetmetal_wall")generic_sheetmetal_wall(op);
 else if(kind=="sheetmetal_flange")generic_sheetmetal_flange(op);
 else if(kind=="sheetmetal_unbend"||kind=="sheetmetal_flat_pattern"||kind=="sheetmetal_bend_back")generic_sheetmetal_unbend(op);
 else if(kind=="assemble_component")assemble_component(op);
 else if(kind=="component_placement"||kind=="component_constraints"||kind=="remove_component")modify_component(op);
 else if(kind=="datum_plane"){double angle=op.value("angle",0.0);J axis=op.value("axis",J());auto f=offset_plane(op["reference"],op.value("offset",0.0),wide(op["label"]),op.contains("angle")?&angle:nullptr,op.contains("axis")?&axis:nullptr);remember(op,f);}
 else if(kind=="datum_axis"){ProElement root=node(nullptr,PRO_E_FEATURE_TREE);integer(root,PRO_E_FEATURE_TYPE,PRO_FEAT_DATUM_AXIS);text(root,PRO_E_STD_FEATURE_NAME,wide(op["label"]).c_str());ProElement cs=node(root,PRO_E_DTMAXIS_CONSTRAINTS);for(auto r:op["references"]){ProElement c=node(cs,PRO_E_DTMAXIS_CONSTRAINT);integer(c,PRO_E_DTMAXIS_CONSTR_TYPE,PRO_DTMAXIS_CONSTR_TYPE_THRU);ProSelection s=resolve(r);ref(c,PRO_E_DTMAXIS_CONSTR_REF,s);ProSelectionFree(&s);}ProFeature f=create(root);CK(ProElementFree(&root));remember(op,f);}
 else if(kind=="set_dimensions"){for(auto v:op["values"]){ProDimension d;CK(ProModelitemInit(board,v["id"],PRO_DIMENSION,&d));CK(ProDimensionValueSet(&d,v["value"]));}}
 else if(kind=="set_sketch_dimensions"){
  ProFeature f=feature(op["sketch"]);ProElement root=nullptr;CK(ProFeatureElemtreeExtract(&f,nullptr,PRO_FEAT_EXTRACT_NO_OPTS,&root));J saved_path=op["sketch"].is_string()?aliases[op["sketch"].get<std::string>()].value("section_path",J::array({PRO_E_STD_SECTION,PRO_E_SKETCHER})):J::array({PRO_E_STD_SECTION,PRO_E_SKETCHER});ProElement sk=get_path(root,saved_path);ProSection s=nullptr;CK(ProElementSpecialvalueGet(sk,nullptr,(ProAppData*)&s));J ids=op["sketch"].is_string()?aliases[op["sketch"].get<std::string>()].value("dimension_ids",J::object()):J::object();for(auto it=op["values"].begin();it!=op["values"].end();++it){int id=ids.contains(it.key())?ids[it.key()].get<int>():std::stoi(it.key());CK(ProSecdimValueSet(s,id,it.value()));}ProWSecerror err=nullptr;CK(ProSecerrorAlloc(&err));CK(ProSectionRegenerate(s,&err));ProSecerrorFree(&err);CK(ProElementSpecialvalueSet(sk,(ProAppData)s));redefine(&f,root);CK(ProFeatureElemtreeFree(&f,root));
 }
 else if(kind=="set_parameters")parameters(op);
 else if(kind=="set_relations"){ProModelitem owner;CK(ProMdlToModelitem(board,&owner));ProRelset rel;ProError e=ProModelitemToRelset(&owner,&rel);if(e==PRO_TK_E_NOT_FOUND)CK(ProRelsetCreate(&owner,&rel));else check(e,"GetRelations");std::vector<std::wstring> storage;for(auto line:op["lines"])storage.push_back(wide(line));std::vector<ProWstring> ptrs;for(auto& line:storage)ptrs.push_back(const_cast<wchar_t*>(line.c_str()));CK(ProRelsetRelationsSet(&rel,ptrs.data(),(int)ptrs.size()));CK(ProRelsetRegenerate(&rel));}
 else if(kind=="feature_tree"){ProElement root=tree_from_json(op["tree"]);ProFeature f=create(root);CK(ProElementFree(&root));remember(op,f);}
 else if(kind=="export"){std::string format=op["format"],extension=format=="step"?".stp":format=="stl"?".stl":format=="iges"?".igs":".jpg";ProPath output;path(output,generic_job+L"\\output\\"+model_name+wide(extension));if(format=="jpeg"){CK(ProMdlDisplay(board));CK(ProMdlWindowGet(board,&win));CK(ProWindowRefit(win));CK(ProWindowRepaint(win));CK(ProRasterFileWrite(win,PRORASTERDEPTH_24,8,6,PRORASTERDPI_100,PRORASTERTYPE_JPEG,output));}else if(format=="stl")write_stl(output);else{ProIntf3DExportType t=format=="step"?PRO_INTF_EXPORT_STEP:PRO_INTF_EXPORT_IGES;CK(ProIntf3DFileWriteWithDefaultProfile((ProSolid)board,t,output));}operation_results.push_back({{"op",kind},{"file",utf8(output)}});}
 else if(kind=="dump_tree"){ProFeature f=feature(op["feature"]);ProElement root;CK(ProFeatureElemtreeExtract(&f,nullptr,PRO_FEAT_EXTRACT_NO_OPTS,&root));ProPath output;path(output,generic_job+L"\\output\\feature_"+std::to_wstring(f.id)+L".xml");CK(ProElemtreeWrite(root,PRO_ELEMTREE_XML,output));CK(ProFeatureElemtreeFree(&f,root));operation_results.push_back({{"op",kind},{"file",utf8(output)}});}
 else if(kind!="regenerate"&&kind!="save")throw std::runtime_error("Operation is not implemented: "+kind);
 if(kind!="export"&&kind!="dump_tree")CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));inspection();operation_results.push_back({{"op",kind},{"label",op.value("label","")},{"succeeded",true}});
}
static void verify_assertions(const J& state,const J& a){if(a.contains("volume_mm3")){if(state["volume_mm3"].is_null()||fabs(state["volume_mm3"].get<double>()-a["volume_mm3"].get<double>())>a.value("volume_tolerance",0.01))throw std::runtime_error("Volume assertion failed");}if(a.value("require_solid",false)&&!state["has_solid"].get<bool>())throw std::runtime_error("Solid assertion failed");}
static void verify_saved(const J& before,const J& after){
 if(before["features"].size()!=after["features"].size()||before["bodies"].size()!=after["bodies"].size())throw std::runtime_error("Saved feature/body count changed");
 for(size_t i=0;i<before["features"].size();i++){auto a=before["features"][i],b=after["features"][i];if(a["id"]!=b["id"]||a["type"]!=b["type"]||a["name"]!=b["name"]||a["dimensions"].size()!=b["dimensions"].size())throw std::runtime_error("Saved feature or dimensions changed");for(size_t j=0;j<a["dimensions"].size();j++)if(a["dimensions"][j]["id"]!=b["dimensions"][j]["id"]||fabs(a["dimensions"][j]["value"].get<double>()-b["dimensions"][j]["value"].get<double>())>1e-6)throw std::runtime_error("Saved dimension value changed");}
 if(!before["volume_mm3"].is_null()&&(after["volume_mm3"].is_null()||fabs(before["volume_mm3"].get<double>()-after["volume_mm3"].get<double>())>0.01))throw std::runtime_error("Saved solid volume changed");
 if(before["parameters"].size()!=after["parameters"].size())throw std::runtime_error("Saved parameter count changed");
 for(auto it=before["parameters"].begin();it!=before["parameters"].end();++it){
  if(!after["parameters"].contains(it.key()))throw std::runtime_error("Saved parameter disappeared: "+it.key());
  auto a=it.value(),b=after["parameters"][it.key()];bool equal=a["type"]==b["type"];
  if(equal&&a["type"].get<int>()==PRO_PARAM_DOUBLE){double x=a["value"],y=b["value"];equal=fabs(x-y)<=1e-10*std::max(1.0,std::max(fabs(x),fabs(y)));}
  else equal=equal&&a["value"]==b["value"];
  if(!equal)throw std::runtime_error("Saved parameter value changed: "+it.key());
 }
 if(before.contains("components"))for(size_t i=0;i<before["components"].size();i++){
  if(i>=after["components"].size())throw std::runtime_error("Saved component count changed");
  auto a=before["components"][i],b=after["components"][i];
  if(a.value("packaged",false)!=b.value("packaged",false)||a.value("underconstrained",false)!=b.value("underconstrained",false))throw std::runtime_error("Saved assembly placement state changed");
  if(a.contains("constraints")&&a["constraints"]!=b["constraints"])throw std::runtime_error("Saved assembly constraints changed");
 }
 if(before.value("model_type","part")!=after.value("model_type","part"))throw std::runtime_error("Saved model type changed");if(before.contains("components")){if(before["components"].size()!=after["components"].size())throw std::runtime_error("Saved component count changed");for(size_t i=0;i<before["components"].size();i++){auto a=before["components"][i],b=after["components"][i];if(a["feature_id"]!=b["feature_id"]||a["model_name"]!=b["model_name"])throw std::runtime_error("Saved component changed");for(int r=0;r<4;r++)for(int c=0;c<4;c++)if(fabs(a["transform"][r][c].get<double>()-b["transform"][r][c].get<double>())>1e-7)throw std::runtime_error("Saved component transform changed");}}
}
static std::wstring latest_model_file(){
 std::wstring extension=assembly_model()?L".asm.":L".prt.",mask=folder+L"\\"+model_name+extension+L"*";WIN32_FIND_DATAW info;HANDLE search=FindFirstFileW(mask.c_str(),&info);if(search==INVALID_HANDLE_VALUE)throw std::runtime_error("Saved model not found");int best=-1;std::wstring found;do{std::wstring name=info.cFileName;auto pos=name.rfind(extension);if(pos==std::wstring::npos)continue;try{int version=std::stoi(name.substr(pos+extension.size()));if(version>best){best=version;found=folder+L"\\"+name;}}catch(...){}}while(FindNextFileW(search,&info));FindClose(search);if(found.empty())throw std::runtime_error("Saved native model version not found");return found;
}
static int run_generic(const std::wstring& job){
 generic_job=job;J report={{"success",false},{"saved_file_reloaded_and_verified",false},{"rollback_succeeded",false}};J request;ProProcessHandle process={};bool connected=false,mutated=false;std::wstring checkpoint;board_log=_wfsopen((job+L"\\native.log").c_str(),L"w",_SH_DENYNO);if(!board_log)return 3;
 try{
  std::ifstream input(job+L"\\request.json");input>>request;auto model=request.at("model");model_name=wide(model.at("model_name"));folder=wide(model.at("output_directory"));aliases=model.at("aliases");component_sources=request.value("components",J::object());template_file=wide(request.at("template_file"));if(!model["part_file"].is_null())checkpoint=wide(model["part_file"]);
  char empty[]="";ProBoolean random=PRO_B_FALSE;CK(ProEngineerConnect(empty,empty,empty,empty,PRO_B_FALSE,30,&random,&process));connected=true;report["connected"]=true;ProName name;wcscpy_s(name,model_name.c_str());ProMdlType mdltype=model.value("model_type","part")=="assembly"?PRO_MDL_ASSEMBLY:PRO_MDL_PART;ProError found=ProMdlInit(name,mdltype,&board);
  if(request.at("new").get<bool>()){
   if(found==PRO_TK_NO_ERROR)throw std::runtime_error("New model name already exists in the Creo session");if(found!=PRO_TK_E_NOT_FOUND)check(found,"CheckNewModelName");ProPath original,destination,tfile;CK(ProDirectoryCurrentGet(original));path(destination,folder);path(tfile,template_file);CK(ProDirectoryChange(destination));try{ProMdl templ;CK(ProMdlFiletypeLoad(tfile,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&templ));ProMdlName new_name;wcscpy_s(new_name,model_name.c_str());CK(ProMdlnameCopy(templ,new_name,&board));}catch(...){ProDirectoryChange(original);throw;}CK(ProDirectoryChange(original));mutated=true;
  }else{
   if(found==PRO_TK_E_NOT_FOUND){ProPath file;path(file,checkpoint);CK(ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&board));}else check(found,"FindOwnedModel");ProPath origin;CK(ProMdlOriginGet(board,origin));std::wstring actual=origin,prefix=folder+L"\\";if(_wcsnicmp(actual.c_str(),prefix.c_str(),prefix.size()))throw std::runtime_error("Loaded model origin does not match this MCP model's output directory");if(model.contains("inspection")&&!request.value("readonly",false))verify_saved(model["inspection"],inspection());
  }
  ProUnitsystem us;ProUnititem unit;CK(ProMdlPrincipalunitsystemGet(board,&us));CK(ProUnitsystemUnitGet(&us,PRO_UNITTYPE_LENGTH,&unit));if(wcscmp(unit.name,L"mm"))throw std::runtime_error("Expected millimeter model units");
  for(auto op:request["operations"]){if(!request.value("readonly",false))mutated=true;execute_operation(op);}if(!request.value("readonly",false))CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));J state=inspection();report["inspection"]=state;report["aliases"]=aliases;verify_assertions(state,request.value("assertions",J::object()));std::wstring saved=checkpoint;
  if(!request.value("readonly",false)){
   log("PHASE=save_and_reload\n");ProPath destination;path(destination,folder);CK(ProMdlnameBackup(board,destination));saved=latest_model_file();J before=state;CK(ProMdlErase(board));board=nullptr;ProPath file;path(file,saved);CK(ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&board));CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));state=inspection();verify_saved(before,state);verify_assertions(state,request.value("assertions",J::object()));report["saved_file_reloaded_and_verified"]=true;
  }
  CK(ProMdlDisplay(board));CK(ProMdlWindowGet(board,&win));CK(ProWindowCurrentSet(win));double a=sqrt(.5),b=sqrt(1.0/6),c=sqrt(1.0/3),d=sqrt(2.0/3);ProMatrix view={{a,-b,c,0},{a,b,-c,0},{0,d,c,0},{0,0,0,1}};CK(ProViewMatrixSet(board,nullptr,view));ProWindowRefit(win);ProWindowRepaint(win);ProWindowActivate(win);ProPath preview;path(preview,job+L"\\output\\preview.jpg");int preview_code=ProRasterFileWrite(win,PRORASTERDEPTH_24,8,6,PRORASTERDPI_100,PRORASTERTYPE_JPEG,preview);
  report.update({{"success",true},{"toolkit_code",0},{"inspection",state},{"aliases",aliases},{"part_file",utf8(saved)},{"preview_code",preview_code},{"preview_file",preview_code==0?J(utf8(preview)):J(nullptr)},{"operations",operation_results}});log("BUILD_SUCCESS=1\n");
 }catch(ProError error){report["toolkit_code"]=error;report["message"]="Toolkit operation failed; inspect native.log and its element error list";log("BUILD_FAILED=%d\n",error);}catch(const std::exception& error){report["message"]=error.what();report["toolkit_code"]=PRO_TK_GENERAL_ERROR;log("BUILD_FAILED=%s\n",error.what());}
 if(!report["success"].get<bool>()&&connected&&mutated&&!checkpoint.empty()){
  log("PHASE=rollback_to_saved_checkpoint\n");ProError erased=board?ProMdlErase(board):PRO_TK_NO_ERROR;board=nullptr;ProPath file;path(file,checkpoint);ProError loaded=erased?erased:ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&board);
  if(!loaded){try{CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));verify_saved(request["model"]["inspection"],inspection());ProMdlDisplay(board);report["rollback_succeeded"]=true;}catch(...){report["rollback_message"]="Restored file could not be regenerated and verified against its saved baseline";}}
  else report["rollback_code"]=loaded;
 }
 if(connected){int disconnected=ProEngineerDisconnect(&process,15);report["disconnect_code"]=disconnected;log("DISCONNECT=%d\n",disconnected);}std::ofstream output(job+L"\\native_result.json",std::ios::binary);output<<report.dump(2);output.close();fclose(board_log);board_log=nullptr;return report["success"].get<bool>()?0:30;
}



