#define NOMINMAX
#include "geometry.cpp"

static std::string utf8(const std::wstring& s){
 int n=WideCharToMultiByte(CP_UTF8,0,s.data(),(int)s.size(),nullptr,0,nullptr,nullptr);
 std::string r(n,'\0');WideCharToMultiByte(CP_UTF8,0,s.data(),(int)s.size(),&r[0],n,nullptr,nullptr);return r;
}
static std::wstring wide(const std::string& s){
 int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),(int)s.size(),nullptr,0);
 if(!n && !s.empty())throw PRO_TK_BAD_INPUTS;
 std::wstring r(n,L'\0');if(n)MultiByteToWideChar(CP_UTF8,0,s.data(),(int)s.size(),&r[0],n);return r;
}
static std::string json_string(const std::wstring& s){
 std::string r="\"";for(unsigned char c:utf8(s)){if(c=='"'||c=='\\'){r+='\\';r+=c;}else if(c<32){char b[7];sprintf_s(b,"\\u%04x",c);r+=b;}else r+=c;}return r+'"';
}
static void path(ProPath dest,const std::wstring& value){if(value.size()>=PRO_PATH_SIZE)throw PRO_TK_BAD_INPUTS;wcscpy_s(dest,PRO_PATH_SIZE,value.c_str());}
static double expected_volume(){
 double area=length_mm*width_mm-(4-acos(-1.0))*radius_mm*radius_mm;
 for(auto& h:holes)area-=acos(-1.0)*h.diameter*h.diameter/4;
 return area*thickness_mm;
}
static void read_spec(const std::wstring& job){
 std::ifstream in(job+L"\\native_spec.txt");if(!in)throw PRO_TK_E_NOT_FOUND;
 std::string line;getline(in,line);model_name=wide(line);getline(in,line);folder=wide(line);getline(in,line);template_file=wide(line);
 if(model_name.empty()||model_name.size()>31)throw PRO_TK_BAD_INPUTS;
 for(wchar_t c:model_name)if(!(c>='a'&&c<='z') && !(c>='0'&&c<='9') && c!='_')throw PRO_TK_BAD_INPUTS;
 int n=0;if(!(in>>length_mm>>width_mm>>thickness_mm>>radius_mm>>n))throw PRO_TK_BAD_INPUTS;
 if(!std::isfinite(length_mm)||!std::isfinite(width_mm)||!std::isfinite(thickness_mm)||!std::isfinite(radius_mm)||length_mm<1||width_mm<1||thickness_mm<0.1||radius_mm<0||radius_mm>=std::min(length_mm,width_mm)/2||n<0||n>50)throw PRO_TK_BAD_INPUTS;
 holes.clear();for(int i=0;i<n;i++){Hole h;if(!(in>>h.x>>h.y>>h.diameter)||!std::isfinite(h.x)||!std::isfinite(h.y)||!std::isfinite(h.diameter)||h.diameter<=0)throw PRO_TK_BAD_INPUTS;holes.push_back(h);}
}
static std::wstring latest_part(){
 WIN32_FIND_DATAW entry;std::wstring base=folder+L"\\"+model_name+L".prt";
 HANDLE find=FindFirstFileW((base+L".*").c_str(),&entry);if(find==INVALID_HANDLE_VALUE)throw PRO_TK_E_NOT_FOUND;
 int newest=-1;std::wstring result;do{std::wstring f=entry.cFileName;size_t pos=f.rfind(L'.');if(pos==std::wstring::npos)continue;wchar_t* end=nullptr;long version=wcstol(f.c_str()+pos+1,&end,10);if(end&&!*end&&version>newest){newest=version;result=folder+L"\\"+f;}}while(FindNextFileW(find,&entry));FindClose(find);if(result.empty())throw PRO_TK_E_NOT_FOUND;return result;
}
static std::vector<bool> found_holes;
static bool found_rounds[4]={};
static ProError verify_surface(ProSurface s,ProError status,ProAppData){
 if(status)throw status;ProGeomitemdata* data=nullptr;CK(ProSurfaceDataGet(s,&data));auto p=data->data.p_surface_data;
 if(p && p->type==PRO_SRF_CYL){auto c=p->srf_shape.cylinder;
  if(fabs(fabs(c.e3[2])-1)<1e-6){
   for(size_t i=0;i<holes.size();i++){auto h=holes[i];if(fabs(c.radius-h.diameter/2)<1e-6&&fabs(c.origin[0]-h.x)<1e-6&&fabs(c.origin[1]-h.y)<1e-6){if(fabs(p->xyz_min[2])>0.001||fabs(p->xyz_max[2]-thickness_mm)>0.001)throw PRO_TK_GENERAL_ERROR;found_holes[i]=true;}}
   if(radius_mm>0&&fabs(c.radius-radius_mm)<1e-6&&fabs(fabs(c.origin[0])-(length_mm/2-radius_mm))<1e-6&&fabs(fabs(c.origin[1])-(width_mm/2-radius_mm))<1e-6){int i=(c.origin[0]>0?2:0)+(c.origin[1]>0?1:0);found_rounds[i]=true;}
  }
 }ProGeomitemdataFree(&data);return PRO_TK_NO_ERROR;
}
static int hole_definitions=0;
static ProError verify_feature(ProFeature* f,ProError status,ProAppData){
 if(status)throw status;ProFeattype t;ProBoolean incomplete;ProFeatStatus fs;CK(ProFeatureTypeGet(f,&t));CK(ProFeatureIsIncomplete(f,&incomplete));CK(ProFeatureStatusGet(f,&fs));if(incomplete||fs!=PRO_FEAT_ACTIVE)throw PRO_TK_GENERAL_ERROR;
 if(t==PRO_FEAT_HOLE){ProElement tree=nullptr;CK(ProFeatureElemtreeExtract(f,nullptr,PRO_FEAT_EXTRACT_NO_OPTS,&tree));int to,from;double dia;CK(ProElementDoubleGet(get(tree,{PRO_E_HLE_COM,PRO_E_DIAMETER}),nullptr,&dia));CK(ProElementIntegerGet(get(tree,{PRO_E_HLE_COM,PRO_E_HOLE_STD_DEPTH,PRO_E_HOLE_DEPTH_TO,PRO_E_HOLE_DEPTH_TO_TYPE}),nullptr,&to));CK(ProElementIntegerGet(get(tree,{PRO_E_HLE_COM,PRO_E_HOLE_STD_DEPTH,PRO_E_HOLE_DEPTH_FROM,PRO_E_HOLE_DEPTH_FROM_TYPE}),nullptr,&from));if(to!=PRO_HLE_STRGHT_THRU_ALL_DEPTH||from!=PRO_HLE_STRGHT_NONE_DEPTH)throw PRO_TK_GENERAL_ERROR;bool match=false;for(auto h:holes)if(fabs(h.diameter-dia)<1e-6)match=true;if(!match)throw PRO_TK_GENERAL_ERROR;hole_definitions++;CK(ProFeatureElemtreeFree(f,tree));}
 if(t==PRO_FEAT_PROTRUSION||t==PRO_FEAT_FIRST_FEAT){ProSection s=nullptr;CK(ProFeatureSectionCopy(f,0,&s));ProIntlist ids=nullptr;int n=0;CK(ProSecdimIdsGet(s,&ids,&n));bool a=false,b=false;for(int i=0;i<n;i++){double value;CK(ProSecdimValueGet(s,ids[i],&value));log("SKETCH_DIM=%g\n",value);if(fabs(value-length_mm)<1e-6)a=true;if(fabs(value-width_mm)<1e-6)b=true;}ProArrayFree((ProArray*)&ids);ProSectionFree(&s);if(!a||!b)throw PRO_TK_GENERAL_ERROR;}
 return PRO_TK_NO_ERROR;
}
static double verify(){
 CK(ProSolidRegenerate((ProSolid)board,PRO_REGEN_NO_FLAGS));ProUnitsystem system;ProUnititem unit;CK(ProMdlPrincipalunitsystemGet(board,&system));CK(ProUnitsystemUnitGet(&system,PRO_UNITTYPE_LENGTH,&unit));if(wcscmp(unit.name,L"mm"))throw PRO_TK_BAD_INPUTS;
 expect_volume(expected_volume());Pro3dPnt box[2];CK(outline(box));double lo[3]={-length_mm/2,-width_mm/2,0},hi[3]={length_mm/2,width_mm/2,thickness_mm};for(int i=0;i<3;i++)if(fabs(box[0][i]-lo[i])>1e-5||fabs(box[1][i]-hi[i])>1e-5)throw PRO_TK_GENERAL_ERROR;
 memset(counts,0,sizeof(counts));CK(ProSolidFeatVisit((ProSolid)board,audit_cb,nullptr,nullptr));if(counts[0]!=1||counts[1]!=(radius_mm>0?1:0)||counts[2]!=(int)holes.size())throw PRO_TK_GENERAL_ERROR;
 hole_definitions=0;CK(ProSolidFeatVisit((ProSolid)board,verify_feature,nullptr,nullptr));if(hole_definitions!=(int)holes.size())throw PRO_TK_GENERAL_ERROR;
 found_holes.assign(holes.size(),false);memset(found_rounds,0,sizeof(found_rounds));auto body=active_body();CK(ProSolidBodySurfaceVisit(&body,verify_surface,nullptr));for(bool h:found_holes)if(!h)throw PRO_TK_GENERAL_ERROR;if(radius_mm>0)for(bool r:found_rounds)if(!r)throw PRO_TK_GENERAL_ERROR;
 return volume();
}
static std::wstring create_plate(){
 ProName name;wcscpy_s(name,model_name.c_str());ProMdl existing=nullptr;ProError exists=ProMdlInit(name,PRO_MDL_PART,&existing);if(exists==PRO_TK_NO_ERROR){log("REFUSED_EXISTING_MODEL=1\n");throw PRO_TK_BAD_INPUTS;}if(exists!=PRO_TK_E_NOT_FOUND)check(exists,"CheckName");
 ProPath original;CK(ProDirectoryCurrentGet(original));ProPath destination;path(destination,folder);CK(ProDirectoryChange(destination));
 try{ProPath file;path(file,template_file);ProMdl templ=nullptr;CK(ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&templ));ProMdlName new_name;wcscpy_s(new_name,model_name.c_str());CK(ProMdlnameCopy(templ,new_name,&board));CK(ProObjectwindowMdlnameCreate(new_name,PRO_PART,&win));CK(ProWindowCurrentSet(win));CK(ProMdlDisplay(board));
  log("PHASE=extrude\n");extrude();remove_empty_body();if(radius_mm>0){log("PHASE=round\n");rounds();}for(size_t i=0;i<holes.size();i++){log("PHASE=hole_%zu\n",i+1);hole((int)i+1,holes[i].x,holes[i].y,holes[i].diameter);}log("PHASE=verify_memory\n");verify();CK(ProMdlnameBackup(board,destination));
 }catch(...){ProDirectoryChange(original);throw;}CK(ProDirectoryChange(original));
 std::wstring saved=latest_part();log("PHASE=verify_saved_file\n");CK(ProMdlErase(board));board=nullptr;ProPath file;path(file,saved);CK(ProMdlFiletypeLoad(file,PRO_MDLFILE_UNUSED,PRO_B_FALSE,&board));verify();CK(ProMdlDisplay(board));CK(ProMdlWindowGet(board,&win));CK(ProWindowCurrentSet(win));
 double a=sqrt(0.5),b=sqrt(1.0/6),c=sqrt(1.0/3),d=sqrt(2.0/3);ProMatrix matrix={{a,-b,c,0},{a,b,-c,0},{0,d,c,0},{0,0,0,1}};CK(ProViewMatrixSet(board,nullptr,matrix));CK(ProWindowRefit(win));CK(ProWindowRepaint(win));CK(ProWindowActivate(win));return saved;
}
#include "generic.cpp"
int wmain(int argc,wchar_t* argv[]){
 if(argc==3&&!wcscmp(argv[1],L"generic"))return run_generic(argv[2]);
 if(argc==2&&!wcscmp(argv[1],L"constants")){J result=J::object();for(auto p:tk_constants)result[p.first]=p.second;printf("%s\n",result.dump().c_str());return 0;}
 bool probe=argc==2&&wcscmp(argv[1],L"status")==0;if(!probe&&(argc!=3||wcscmp(argv[1],L"create")))return 2;
 std::wstring job=probe?L"":argv[2];ProError result=PRO_TK_NO_ERROR;ProProcessHandle process={};bool connected=false;std::wstring saved;int preview_code=-1;double measured=0;ProError disconnect_code=PRO_TK_NO_ERROR;
 if(!probe){board_log=_wfsopen((job+L"\\native.log").c_str(),L"w",_SH_DENYNO);if(!board_log)return 3;try{read_spec(job);}catch(ProError e){result=e;}}
 if(!result){char empty[]="";ProBoolean random=PRO_B_FALSE;result=ProEngineerConnect(empty,empty,empty,empty,PRO_B_FALSE,30,&random,&process);connected=result==PRO_TK_NO_ERROR;log("CONNECT=%d\n",result);}
 if(probe){std::wstring name;int type=-1,current_code=-8,release=0;if(connected){ProMdl current=nullptr;current_code=ProMdlCurrentGet(&current);if(!current_code){ProName value;ProMdlNameGet(current,value);name=value;ProMdlType t;ProMdlTypeGet(current,&t);type=t;}ProEngineerReleaseNumericversionGet(&release);disconnect_code=ProEngineerDisconnect(&process,15);}printf("{\"connected\":%s,\"toolkit_code\":%d,\"current_model\":%s,\"current_model_code\":%d,\"model_type\":%d,\"release_numeric\":%d,\"disconnect_code\":%d,\"feature_creation_license\":\"requires_actual_modeling_test\"}\n",connected?"true":"false",result,json_string(name).c_str(),current_code,type,release,disconnect_code);return result?20:0;}
 if(connected){try{saved=create_plate();measured=volume();ProPath image;path(image,folder+L"\\preview.jpg");preview_code=ProRasterFileWrite(win,PRORASTERDEPTH_24,8,6,PRORASTERDPI_100,PRORASTERTYPE_JPEG,image);log("BUILD_SUCCESS=1\n");}catch(ProError e){result=e;log("BUILD_FAILED=%d\n",e);}catch(...){result=PRO_TK_GENERAL_ERROR;log("BUILD_FAILED=unexpected\n");}disconnect_code=ProEngineerDisconnect(&process,15);log("DISCONNECT=%d\n",disconnect_code);}
 std::ostringstream out;out.precision(15);out<<"{\"success\":"<<(result?"false":"true")<<",\"toolkit_code\":"<<result<<",\"connected\":"<<(connected?"true":"false")<<",\"part_file\":"<<json_string(saved)<<",\"volume_mm3\":"<<measured<<",\"expected_volume_mm3\":"<<expected_volume()<<",\"extrude_count\":"<<counts[0]<<",\"round_count\":"<<counts[1]<<",\"hole_count\":"<<counts[2]<<",\"preview_code\":"<<preview_code<<",\"disconnect_code\":"<<disconnect_code<<",\"saved_file_reloaded_and_verified\":"<<(result?"false":"true")<<"}";
 std::ofstream report(job+L"\\native_result.json",std::ios::binary);report<<out.str();report.close();if(board_log)fclose(board_log);return result?30:0;
}
