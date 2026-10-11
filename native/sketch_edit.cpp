// In-place geometry replacement; the native sketch and downstream Blend IDs survive.
static J expanded_geometry(const J& input){
 J result=J::array();
 for(auto e:input){std::string type=e["type"],name=e["name"];
  if(type=="rectangle"||type=="polyline"){
   J points;if(type=="rectangle"){auto a=e["min"],b=e["max"];points=J::array({a,J::array({b[0],a[1]}),b,J::array({a[0],b[1]})});}else points=e["points"];
   int n=(int)points.size(),segments=n-1+(type=="rectangle"||e.value("closed",false)?1:0);
   for(int i=0;i<segments;i++)result.push_back({{"type","line"},{"name",name+"_"+std::to_string(i)},{"start",points[i]},{"end",points[(i+1)%n]},{"construction",e.value("construction",false)}});
  }else result.push_back(e);
 }return result;
}

static void generic_sketch_edit(const J& op){
 std::string label=op.at("sketch");if(!aliases.contains(label))throw std::runtime_error("Sketch alias is missing");J& meta=aliases[label];ProFeature f=feature(label);int original_id=f.id;
 J geometry=expanded_geometry(op["entities"]),names=J::object();for(auto e:geometry)names[e["name"].get<std::string>()]=e["type"];
 if(names.size()!=geometry.size()||names.size()!=meta.at("entity_ids").size())throw std::runtime_error("In-place edit must retain every named sketch entity");
 for(auto it=meta["entity_ids"].begin();it!=meta["entity_ids"].end();++it)if(!names.contains(it.key()))throw std::runtime_error("In-place edit cannot rename sketch entities");
 ProElement root=nullptr;CK(ProFeatureElemtreeExtract(&f,nullptr,PRO_FEAT_EXTRACT_NO_OPTS,&root));ProElement sk=get_path(root,meta.value("section_path",J::array({PRO_E_STD_SECTION,PRO_E_SKETCHER})));ProSection section=nullptr;CK(ProElementSpecialvalueGet(sk,nullptr,(ProAppData*)&section));CK(ProSectionIntentManagerModeSet(section,PRO_B_FALSE));
 ProMatrix loc;CK(ProSectionLocationGet(section,loc));
 auto project=[&](const J& p,double* xy){V w=vec(meta["origin"]);for(int j=0;j<3;j++)w[j]+=meta["u_axis"][j].get<double>()*p[0].get<double>()+meta["v_axis"][j].get<double>()*p[1].get<double>();for(int i=0;i<2;i++)xy[i]=(w[0]-loc[3][0])*loc[i][0]+(w[1]-loc[3][1])*loc[i][1]+(w[2]-loc[3][2])*loc[i][2];};
 ProIntlist dimensions=nullptr;int count=0;CK(ProSecdimIdsGet(section,&dimensions,&count));for(int i=0;i<count;i++)CK(ProSecdimDelete(section,dimensions[i]));if(dimensions)ProArrayFree((ProArray*)&dimensions);
 ProIntlist constraints=nullptr;CK(ProSectionConstraintsIdsGet(section,&constraints,&count));for(int i=0;i<count;i++)CK(ProSectionConstraintDelete(section,constraints[i]));if(constraints)ProArrayFree((ProArray*)&constraints);
 for(auto e:geometry){std::string name=e["name"],type=e["type"];int old=meta["entity_ids"][name],replacement=-1;Pro2dEntdef* existing=nullptr;CK(ProSectionEntityGet(section,old,&existing));Pro2dEntType original=existing->type;
  if(type=="line"||type=="centerline"){Pro2dLinedef value={};value.type=type=="line"?PRO_2D_LINE:PRO_2D_CENTER_LINE;if(original!=value.type)throw std::runtime_error("Entity type cannot change during an in-place edit");project(e["start"],value.end1);project(e["end"],value.end2);CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&value,&replacement));}
  else if(type=="spline"){if(original!=PRO_2D_SPLINE)throw std::runtime_error("Entity type cannot change during an in-place edit");auto p=e["points"];std::vector<std::array<double,2>> xy(p.size());for(size_t i=0;i<xy.size();i++)project(p[i],xy[i].data());Pro2dSplinedef value={};value.type=PRO_2D_SPLINE;value.n_points=(unsigned)xy.size();value.point_arr=(Pro2dPnt*)xy.data();value.tangency_type=e.value("closed",false)?PRO_2D_SPLINE_TAN_PERIODIC:PRO_2D_SPLINE_TAN_NONE;CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&value,&replacement));}
  else if(type=="circle"){if(original!=PRO_2D_CIRCLE)throw std::runtime_error("Entity type cannot change during an in-place edit");Pro2dCircledef value={};value.type=PRO_2D_CIRCLE;project(e["center"],value.center);value.radius=e["radius"];CK(ProSectionEntityAdd(section,(Pro2dEntdef*)&value,&replacement));}
  else throw std::runtime_error("In-place geometry editor currently supports lines, polylines, rectangles, circles and splines");
  CK(ProSectionEntityConstructionSet(section,replacement,e.value("construction",false)?PRO_B_TRUE:PRO_B_FALSE));CK(ProSectionEntityReplace(section,old,replacement));
  // Replace retains the original entity identity and consumes the temporary ID.
  Pro2dEntdef* retained=nullptr;CK(ProSectionEntityGet(section,old,&retained));meta["entity_ids"][name]=old;
 }
 ProWSecerror errors=nullptr;CK(ProSecerrorAlloc(&errors));CK(ProSectionAutodim(section,&errors));CK(ProSectionRegenerate(section,&errors));ProSecerrorFree(&errors);CK(ProElementSpecialvalueSet(sk,(ProAppData)section));redefine(&f,root);CK(ProFeatureElemtreeFree(&f,root));
 if(f.id!=original_id)throw std::runtime_error("Sketch ID changed during in-place edit");meta["geometry"]=op["entities"];meta["dimension_ids"]=J::object();if(op.contains("profile"))meta["airfoil"]=op["profile"];else meta.erase("airfoil");
 operation_results.push_back({{"op",op["op"]},{"sketch",label},{"preserved_feature_id",f.id},{"parameters",meta.value("airfoil",J::object())}});
}
