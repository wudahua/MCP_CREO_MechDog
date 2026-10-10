// Ordinary two-section Blend reuse. This does not create Blend element trees.
// The caller supplies a saved native seed; only the new owned copy is modified.
static ProMdl load_isolated_loft_seed(const std::wstring& filename){
 std::filesystem::path source(filename);ProPath previous,directory;CK(ProDirectoryCurrentGet(previous));path(directory,source.parent_path().wstring());CK(ProDirectoryChange(directory));
 ProMdl loaded=nullptr;
 try{
  std::wstring basename=source.filename().wstring();auto extension=basename.find(L".prt");if(extension==std::wstring::npos)throw std::runtime_error("Invalid native loft seed filename");
  ProMdlName from,to;wcscpy_s(from,basename.substr(0,extension).c_str());std::wstring unique=L"ls_"+std::filesystem::path(generic_job).filename().wstring().substr(0,20);wcscpy_s(to,unique.c_str());
  ProMdl existing=nullptr;ProError found=ProMdlInit(to,PRO_MDL_PART,&existing);if(found!=PRO_TK_E_NOT_FOUND)throw std::runtime_error("Isolated loft seed name already exists; inspect the previous job");
  CK(ProMdlfileMdlnameCopy(PRO_MDLFILE_PART,from,to));ProPath file;path(file,(source.parent_path()/(unique+L".prt")).wstring());CK(ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&loaded));
 }catch(...){ProDirectoryChange(previous);throw;}
 CK(ProDirectoryChange(previous));return loaded;
}

static J validate_loft_seed(const J& binding){
 ProFeature blend;CK(ProFeatureInit((ProSolid)board,binding.at("feature_id"),&blend));ProFeattype type;CK(ProFeatureTypeGet(&blend,&type));ProLine subtype=L"";CK(ProFeatureSubtypeGet(&blend,subtype));
 if(type!=PRO_FEAT_PROTRUSION||(wcscmp(subtype,L"\u6df7\u5408")&&_wcsicmp(subtype,L"Blend")))throw std::runtime_error("Seed feature must be an ordinary native Blend (Chinese/English Creo supported)");
 int sections=0;CK(ProFeatureNumSectionsGet(&blend,&sections));if(sections!=2)throw std::runtime_error("Seed Blend must contain exactly two sections");
 J setting=read_blend_setting(blend.id,L"seed");if(setting["interpolation"]!=binding.value("interpolation","straight"))throw std::runtime_error("Seed Blend interpolation does not match requested interpolation; supply a matching native seed");
 J state=inspection();int solids=0;for(auto b:state["bodies"])if(b["state"].get<int>()==PRO_BODY_STATE_ACTIVE)solids++;
 if(solids!=1)throw std::runtime_error("Seed must contain exactly one active solid body");
 for(auto f:state["features"]){int t=f["type"],id=f["id"];if(id!=blend.id&&t!=PRO_FEAT_DATUM&&t!=PRO_FEAT_CSYS&&t!=PRO_FEAT_DATUM_AXIS&&t!=PRO_FEAT_CURVE)throw std::runtime_error("Seed contains unsupported additional features; use a dedicated Blend reference part");}
 ProReference* refs=nullptr;CK(ProFeatureReferenceEditRefsGet((ProSolid)board,&blend,PRO_EDITREF_REF_TYPE_ALL,&refs));J profiles=J::array();
 try{int n=0;CK(ProArraySizeGet((ProArray)refs,&n));for(int i=0;i<n;i++){ProType rt;int id;ProMdl owner;CK(ProReferenceTypeGet(refs[i],&rt));CK(ProReferenceIdGet(refs[i],&id));CK(ProReferenceOwnerGet(refs[i],&owner));if(owner!=board)throw std::runtime_error("External-model references are not supported in a loft seed");
   if(rt==PRO_FEATURE){ProFeature f;CK(ProFeatureInit((ProSolid)board,id,&f));ProFeattype ft;CK(ProFeatureTypeGet(&f,&ft));if(ft!=PRO_FEAT_CURVE)throw std::runtime_error("Seed sections must reference independent sketches");profiles.push_back(id);}
   else if(rt!=PRO_BODY)throw std::runtime_error("Unsupported reference in Blend seed");
  }
 }catch(...){ProReferencearrayFree(refs);throw;}ProReferencearrayFree(refs);
 if(profiles.size()!=2||profiles[0]==profiles[1])throw std::runtime_error("Seed must reference two distinct external sketch features");
 // Sort by feature order, matching the documented seed convention: bottom first.
 ProFeature a,b;CK(ProFeatureInit((ProSolid)board,profiles[0],&a));CK(ProFeatureInit((ProSolid)board,profiles[1],&b));int an,bn;CK(ProFeatureNumberGet(&a,&an));CK(ProFeatureNumberGet(&b,&bn));if(an>bn)std::swap(profiles[0],profiles[1]);
 return profiles;
}

static void bind_loft_seed(const J& binding,const J& original_profiles){
 int bottom=feature_id(binding["sections"][0]),top=feature_id(binding["sections"][1]);ProFeature last;CK(ProFeatureInit((ProSolid)board,top,&last));int position=0;CK(ProFeatureNumberGet(&last,&position));
 int* ids=nullptr;CK(ProArrayAlloc(1,sizeof(int),1,(ProArray*)&ids));ids[0]=binding["feature_id"];ProError moved=ProFeatureWithoptionsReorder((ProSolid)board,ids,position,PRO_REGEN_NO_FLAGS);ProArrayFree((ProArray*)&ids);check(moved,"ReorderSeedBlend");
 ProFeature blend;CK(ProFeatureInit((ProSolid)board,binding["feature_id"],&blend));ProReference* old_refs=nullptr;ProReference* new_refs=nullptr;CK(ProFeatureReferenceEditRefsGet((ProSolid)board,&blend,PRO_EDITREF_REF_TYPE_ALL,&old_refs));int count=0;CK(ProArraySizeGet((ProArray)old_refs,&count));CK(ProArrayAlloc(0,sizeof(ProReference),1,(ProArray*)&new_refs));int replaced=0;
 try{
  for(int i=0;i<count;i++){int id;ProType type;CK(ProReferenceIdGet(old_refs[i],&id));CK(ProReferenceTypeGet(old_refs[i],&type));ProSelection s=nullptr;
   if(type==PRO_FEATURE&&(id==original_profiles[0].get<int>()||id==original_profiles[1].get<int>())){ProFeature replacement;CK(ProFeatureInit((ProSolid)board,id==original_profiles[0].get<int>()?bottom:top,&replacement));CK(ProSelectionAlloc(nullptr,&replacement,&s));replaced++;}
   else CK(ProReferenceToSelection(old_refs[i],&s));
   ProReference r=nullptr;ProError converted=ProSelectionToReference(s,&r);ProSelectionFree(&s);check(converted,"CopyBlendReference");CK(ProArrayObjectAdd((ProArray*)&new_refs,-1,1,&r));
  }
  if(replaced!=2)throw std::runtime_error("Seed reference identity changed during sketch creation");
  // Creo 10 requires the complete reference array, including unchanged body refs.
  CK(ProFeatureReferenceEdit((ProSolid)board,&blend,old_refs,new_refs,PRO_REGEN_NO_FLAGS));
 }catch(...){if(new_refs)ProReferencearrayFree(new_refs);ProReferencearrayFree(old_refs);throw;}
 ProReferencearrayFree(new_refs);ProReferencearrayFree(old_refs);
 CK(ProArrayAlloc(2,sizeof(int),1,(ProArray*)&ids));ids[0]=original_profiles[0];ids[1]=original_profiles[1];ProFeatureDeleteOptions* opts=nullptr;CK(ProArrayAlloc(1,sizeof(ProFeatureDeleteOptions),1,(ProArray*)&opts));opts[0]=PRO_FEAT_DELETE_NO_OPTS;
 ProError removed=ProFeatureWithoptionsDelete((ProSolid)board,ids,opts,PRO_REGEN_NO_FLAGS);ProArrayFree((ProArray*)&ids);ProArrayFree((ProArray*)&opts);check(removed,"RemoveUnusedSeedSketches");
 ProName name;wcscpy_s(name,wide(binding["label"]).c_str());CK(ProModelitemNameSet(&blend,name));CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));
 ProFeatStatus status;CK(ProFeatureStatusGet(&blend,&status));if(status!=PRO_FEAT_ACTIVE)throw std::runtime_error("Rebound Blend is not active");
 J meta={{"feature_id",blend.id},{"op","loft_seed"},{"sections",binding["sections"]},{"interpolation",binding.value("interpolation","straight")},{"construction","native_two_section_blend_seed_rebinding"},{"seed_sha256",binding["snapshot_sha256"]}};aliases[binding["label"].get<std::string>()]=meta;
 operation_results.push_back({{"op","loft_seed"},{"label",binding["label"]},{"feature_id",blend.id},{"succeeded",true}});
}
