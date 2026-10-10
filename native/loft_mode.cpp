// Ordinary Blend settings are not exposed through the FET in Creo 10.
// Read the numbered Blended surfaces row in Creo's own UTF-8 feature report.
static void activate_blend_context(){
 // Creo 10 can reject edit-reference queries on a valid but undisplayed model.
 // Feature-info output also needs the target current, including after reload.
 log("PHASE=activate_blend_context\n");
 // Reuse the current/base window. ObjectwindowCreate would accumulate windows
 // during repeated jobs; PTC recommends Display for a single target model.
 CK(ProMdlDisplay(board));CK(ProMdlWindowGet(board,&win));CK(ProWindowCurrentSet(win));
 // CurrentSet only changes Toolkit's graphics context, not the active model.
 // Activate is supported by this asynchronous worker and must precede queries.
 CK(ProWindowActivate(win));
 ProMdl current=nullptr;CK(ProMdlCurrentGet(&current));
 if(current!=board)throw std::runtime_error("Cannot activate the target Blend model; finish any modal Creo command before retrying");
}

static J parse_blend_setting(const std::wstring& filename){
 std::ifstream input(filename,std::ios::binary);if(!input)throw std::runtime_error("Missing native Blend feature information");
 std::string line,mode="unknown",matched;const std::string chinese=utf8(L"\u6df7\u5408\u66f2\u9762");
 while(std::getline(input,line)){
  std::string folded=line;for(auto& c:folded)if(c>='A'&&c<='Z')c+=(char)('a'-'A');
  size_t pos=line.find(chinese),length=chinese.size();if(pos==std::string::npos){pos=folded.find("blended surfaces");length=16;}if(pos==std::string::npos)continue;
  bool table=true,number=false;for(size_t i=0;i<pos;i++){char c=line[i];if(c>='0'&&c<='9')number=true;else if(c!=' '&&c!='\t'&&c!='.')table=false;}if(!table||!number)continue;
  std::string value=line.substr(pos+length);size_t first=value.find_first_not_of(" \t\r\n"),last=value.find_last_not_of(" \t\r\n");value=first==std::string::npos?"":value.substr(first,last-first+1);
  std::string lower=value;for(auto& c:lower)if(c>='A'&&c<='Z')c+=(char)('a'-'A');std::string found="unknown";
  if(value==utf8(L"\u5e73\u6ed1")||value==utf8(L"\u5149\u6ed1")||lower=="smooth")found="smooth";
  if(value==utf8(L"\u76f4")||value==utf8(L"\u76f4\u7ebf")||lower=="straight")found="straight";
  if(!matched.empty())throw std::runtime_error("Ambiguous Blend connection setting in native feature information");mode=found;matched=line;
 }
 if(mode=="unknown")throw std::runtime_error("Cannot verify native Blend connection setting; supported report languages are Chinese and English");
 return {{"interpolation",mode},{"source","Creo native PRO_FEAT_INFO"},{"row",matched}};
}

static J read_blend_setting(int feature_id,const std::wstring& phase){
 activate_blend_context();
 ProPath previous,target;CK(ProDirectoryCurrentGet(previous));path(target,generic_job);CK(ProDirectoryChange(target));
 std::wstring filename=L"blend_"+std::to_wstring(feature_id)+L"_"+phase+L".txt";ProMdlFileName name;wcscpy_s(name,filename.c_str());
 ProError exported=ProOutputFileMdlnameWrite(board,name,PRO_FEAT_INFO,nullptr,&feature_id,nullptr,nullptr);ProError restored=ProDirectoryChange(previous);check(exported,"ExportBlendFeatureInfo");check(restored,"RestoreFeatureInfoDirectory");
 J setting=parse_blend_setting(generic_job+L"\\"+filename);setting["feature_info_file"]=utf8(generic_job+L"\\"+filename);return setting;
}

static J verify_loft_settings(const std::wstring& phase){
 J result=J::object();
 for(auto it=aliases.begin();it!=aliases.end();++it){const J& meta=it.value();if(meta.value("op","")!="loft_seed"||!meta.contains("interpolation"))continue;
  int id=meta["feature_id"];ProFeature f;CK(ProFeatureInit((ProSolid)board,id,&f));ProFeattype type;CK(ProFeatureTypeGet(&f,&type));ProLine subtype=L"";CK(ProFeatureSubtypeGet(&f,subtype));
  if(type!=PRO_FEAT_PROTRUSION||(wcscmp(subtype,L"\u6df7\u5408")&&_wcsicmp(subtype,L"Blend")))throw std::runtime_error("Native Blend feature identity changed");
  int count=0;CK(ProFeatureNumSectionsGet(&f,&count));if(count!=(int)meta["sections"].size())throw std::runtime_error("Native Blend section count changed");
  J setting=read_blend_setting(id,phase);if(setting["interpolation"]!=meta["interpolation"])throw std::runtime_error("Native Blend connection setting changed");
  setting.update({{"feature_id",id},{"native_subtype",utf8(subtype)},{"section_count",count}});result[it.key()]=setting;
 }
 return result;
}
