"""Real MCP/Creo checks of 3/5-section native Blend seed rebinding.

Supply a dedicated local seed with exactly --sections external sketches,
created and selected in increasing Z order. Never resubmit uncertain jobs.
"""
import argparse
import asyncio
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def airfoil(chord,angle):
    # Finite trailing-edge NACA 0012; NASA CR-145194, equation 39b.
    up=[];a=math.radians(angle)
    def rotate(x,y):return [x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a)]
    raw=[]
    for i in range(41):
        x=(1-math.cos(math.pi*i/40))/2
        y=.6*(.2969*math.sqrt(x)-.126*x-.3516*x*x+.2843*x**3-.1015*x**4)
        raw.append(((x-.25)*chord,y*chord))
    up=[rotate(x,y) for x,y in raw];low=[rotate(x,-y) for x,y in reversed(raw)]
    return [{'type':'spline','name':'upper','points':up},
            {'type':'line','name':'trailing','start':up[-1],'end':low[0]},
            {'type':'spline','name':'lower','points':low}]

def profiles(count,foil=False):
    if count==3:zs=[0,30,60];sizes=[20,30,10];angles=[30,15,5]
    else:zs=[0,20,50,80,100];sizes=[12,26,34,22,8];angles=[35,28,18,10,5]
    result=[]
    for i,(z,size,angle) in enumerate(zip(zs,sizes,angles)):
        entities=airfoil(size,angle) if foil else [{'type':'rectangle','name':'profile','min':[-size/2,-size/2],'max':[size/2,size/2]}]
        dims=[] if foil else [{'name':name,'type':'length','refs':[{'entity':f'profile_{j}'}],
                               'value':size,'position':[size,size]} for j,name in enumerate(['width','height'])]
        result.append({'op':'sketch','label':f'section_{i}','plane':'XY','offset':z,'entities':entities,'dimensions':dims})
    return result,zs,sizes,angles

def verify_native(p,count,mode,blend=None):
    r=p['result'];assert r['saved_file_reloaded_and_verified'];s=r['inspection']
    assert s['healthy'] and s['has_solid'] and s['units']=='mm'
    assert len([b for b in s['bodies'] if b['state']==4])==1
    fid=r['aliases']['blend']['feature_id'];assert blend is None or fid==blend
    f=next(f for f in s['features'] if f['id']==fid)
    assert f['type']==917 and f['status']==0 and not f['incomplete']
    assert len(r['aliases']['blend']['sections'])==count
    for phase in ['before_save','after_reload']:
        setting=r['loft_checks'][phase]['blend']
        assert setting['section_count']==count and setting['interpolation']==mode
    sketches=[r['aliases'][f'section_{i}']['feature_id'] for i in range(count)]
    assert len(set(sketches))==count
    assert all(any(f['id']==id and f['type']==949 and f['status']==0 for f in s['features']) for id in sketches)
    return {'model_id':p['model_id'],'revision':p['revision'],'blend_feature_id':fid,
            'section_sketch_ids':sketches,'volume_mm3':s['volume_mm3'],'part_file':r['part_file'],
            'preview_file':r.get('preview_file'),'saved_file_reloaded_and_verified':True,
            'native_checks':r['loft_checks']}

def stl_vertices(path):
    pts=[]
    for line in Path(path).read_text().splitlines():
        fields=line.split()
        if fields and fields[0]=='vertex':pts.append(tuple(float(x) for x in fields[1:]))
    assert pts and len(pts)%3==0
    return [pts[i:i+3] for i in range(0,len(pts),3)]

def plane_boundary(triangles,z):
    # Cap triangles can contain interior vertices. Select cap boundary edges;
    # at intermediate planes, collect intersections of actual solid facets.
    from collections import Counter
    eps=1e-7;caps=[];cuts=[]
    for t in triangles:
        if all(abs(v[2]-z)<eps for v in t):caps.append(t);continue
        if z<min(v[2] for v in t)-eps or z>max(v[2] for v in t)+eps:continue
        for i in range(3):
            a,b=t[i],t[(i+1)%3]
            if abs(a[2]-z)<eps:cuts.append(a[:2])
            if (a[2]-z)*(b[2]-z)<0:
                ratio=(z-a[2])/(b[2]-a[2]);cuts.append((a[0]+ratio*(b[0]-a[0]),a[1]+ratio*(b[1]-a[1])))
    if caps:
        edges=Counter()
        for t in caps:
            for i in range(3):edges[tuple(sorted(tuple(round(v,8) for v in t[j][:2]) for j in (i,(i+1)%3)))]+=1
        cuts.extend(p for edge,n in edges.items() if n==1 for p in edge)
    pts=set(tuple(round(v,8) for v in p) for p in cuts)
    assert len(pts)>=4,f'No boundary at Z={z}'
    return pts

def verify_stl(path,zs,sizes,angles=None):
    triangles=stl_vertices(path);checks=[]
    for i,(z,size) in enumerate(zip(zs,sizes)):
        pts=plane_boundary(triangles,z)
        if angles is None:
            sx=max(p[0] for p in pts)-min(p[0] for p in pts);sy=max(p[1] for p in pts)-min(p[1] for p in pts)
            assert abs(sx-size)<.15 and abs(sy-size)<.15,(z,sx,sy,size)
            checks.append({'z_mm':z,'width_mm':sx,'height_mm':sy,'requested_size_mm':size})
        else:
            a=math.radians(angles[i]);local=[(x*math.cos(a)+y*math.sin(a),-x*math.sin(a)+y*math.cos(a)) for x,y in pts]
            xmin=min(p[0] for p in local);xmax=max(p[0] for p in local)
            assert abs(xmin+.25*size)<.15 and abs(xmax-.75*size)<.15,(z,xmin,xmax,size)
            deviation=[]
            for x,y in local:
                xn=min(1,max(0,x/size+.25))
                expected=.6*size*(.2969*math.sqrt(xn)-.126*xn-.3516*xn*xn+.2843*xn**3-.1015*xn**4)
                if xn<.99999:deviation.append(abs(abs(y)-expected))
            # Vertical error magnifies a small tessellation X error at the
            # near-vertical leading edge. Validate geometric nearest distance.
            upper=[]
            for k in range(401):
                xn=(1-math.cos(math.pi*k/400))/2
                y=.6*size*(.2969*math.sqrt(xn)-.126*xn-.3516*xn*xn+.2843*xn**3-.1015*xn**4)
                upper.append(((xn-.25)*size,y))
            outline=upper+[(x,-y) for x,y in reversed(upper)]
            segments=list(zip(outline,outline[1:]+outline[:1]))
            def distance(p):
                best=math.inf
                for u,v in segments:
                    dx,dy=v[0]-u[0],v[1]-u[1];n=dx*dx+dy*dy
                    if not n:continue
                    t=max(0,min(1,((p[0]-u[0])*dx+(p[1]-u[1])*dy)/n))
                    best=min(best,(p[0]-u[0]-t*dx)**2+(p[1]-u[1]-t*dy)**2)
                return math.sqrt(best)
            nearest=max(distance(p) for p in local)
            assert nearest<.15,(z,nearest)
            checks.append({'z_mm':z,'chord_mm':xmax-xmin,'requested_chord_mm':size,'requested_angle_deg':angles[i],
                           'max_vertical_formula_deviation_mm':max(deviation),
                           'max_nearest_profile_distance_mm':nearest,'boundary_points':len(pts)})
    return {'success':True,'facets':len(triangles),'sections':checks,'tolerance_mm':.15}

async def main(seed_file,feature_id,count,mode,resume=False):
    source=Path(seed_file).resolve();output=ROOT/f'build/multisection_{count}_{mode}_integration.json'
    report={'version':VERSION,'success':False,'section_count':count,'interpolation':mode,
            'construction':'native_multisection_blend_seed_rebinding','source_sha256':sha(source),'jobs':[],'cases':{}}
    if resume:
        report=json.loads(output.read_text(encoding='utf-8'));assert not report['success']
        assert report['version']==VERSION and report['source_sha256']==sha(source)
        report.pop('error',None)
    def persist():output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT))) as client:
        async def job(tool,args,stage,expected_failure=False,rollback=False):
            previous=next((j for j in report['jobs'] if j['stage']==stage),None)
            if previous:
                p=json.loads((ROOT/'jobs'/previous['job_id']/'job.json').read_text(encoding='utf-8'))
            else:
                response=await client.call_tool(tool,args)
                if response.is_error:raise RuntimeError(str(response))
                jid=response.structured_content['job_id'];entry={'stage':stage,'tool':tool,'job_id':jid,
                                       'status':'queued','expected_failure':expected_failure};report['jobs'].append(entry);persist()
                print(json.dumps({'stage':stage,'job_id':jid}),flush=True)
                deadline=time.monotonic()+600
                while time.monotonic()<deadline:
                    p=(await client.call_tool('creo_get_job',{'job_id':jid})).structured_content
                    if p['status'] in ('succeeded','failed','unknown_outcome'):break
                    await asyncio.sleep(.5)
                else:raise TimeoutError('Inspect pending job; do not resubmit')
                entry['status']=p['status'];entry['message']=p.get('message');persist()
            build={'source_fingerprint':(ROOT/'build/source.sha256').read_text().strip(),'worker_sha256':sha(ROOT/'build/creo_worker.exe')}
            assert report.get('native_build',build)==build,'Native runtime changed during test';report['native_build']=build
            assert p['status']==('failed' if expected_failure else 'succeeded'),p.get('message')
            if rollback:
                assert p['result']['rollback_succeeded'];assert p['result']['loft_checks']['rollback']['blend']['section_count']==count
                assert p['result']['loft_checks']['rollback']['blend']['interpolation']==mode
            return p
        try:
            ops,zs,sizes,angles=profiles(count)
            assertions={'require_solid':True}
            if mode=='straight':assertions['volume_mm3']=sum((b-a)*(x*x+x*y+y*y)/3 for a,b,x,y in zip(zs,zs[1:],sizes,sizes[1:]))
            p=await job('creo_new_loft_part',{'seed_file':str(source),'seed_feature_id':feature_id,'sections':ops,
                                            'label':'blend','interpolation':mode,'assertions':assertions},'rect_create')
            case={'initial':verify_native(p,count,mode)};report['cases']['rectangle']=case;persist()
            middle=count//2;new_size=sizes[middle]+6;edited_sizes=sizes[:];edited_sizes[middle]=new_size
            assertions={'require_solid':True}
            if mode=='straight':assertions['volume_mm3']=sum((b-a)*(x*x+x*y+y*y)/3 for a,b,x,y in zip(zs,zs[1:],edited_sizes,edited_sizes[1:]))
            p=await job('creo_execute_plan',{'model_id':p['model_id'],'expected_revision':p['revision'],
                     'operations':[{'op':'set_sketch_dimensions','sketch':f'section_{middle}','values':{'width':new_size,'height':new_size}}],
                     'assertions':assertions},'rect_edit_middle')
            case['edited']=verify_native(p,count,mode,case['initial']['blend_feature_id'])
            assert abs(case['edited']['volume_mm3']-case['initial']['volume_mm3'])>1
            case['middle_size_mm']=[sizes[middle],new_size];persist()
            exported=await job('creo_export_model',{'model_id':p['model_id'],'format':'stl'},'rect_export_stl')
            stl=next(o['file'] for o in exported['result']['operations'] if o['op']=='export')
            case['stl_file']=stl;case['all_section_geometry']=verify_stl(stl,zs,edited_sizes);persist()
            failure=await job('creo_execute_plan',{'model_id':p['model_id'],'expected_revision':p['revision'],
                       'operations':[{'op':'set_sketch_dimensions','sketch':f'section_{middle}','values':{'width':new_size+2}}],
                       'assertions':{'volume_mm3':1}},'failed_edit_rollback',True,True)
            # A failed job's inspection describes the rejected edit. Query the
            # restored native model separately to verify rollback geometry.
            refreshed=await job('creo_refresh_model',{'model_id':p['model_id']},'rollback_refresh')
            assert abs(refreshed['result']['inspection']['volume_mm3']-case['edited']['volume_mm3'])<.01
            assert refreshed['result']['loft_checks']['loaded']['blend']['section_count']==count
            case['rollback_verified']=True;case['success']=True;persist()
            mismatch=await job('creo_new_loft_part',{'seed_file':str(source),'seed_feature_id':feature_id,
                         'sections':ops[:-1],'label':'blend','interpolation':mode},'seed_count_mismatch',True)
            assert 'section count does not match' in mismatch.get('message','');report['count_mismatch_rejected']=True
            mismatch=await job('creo_new_loft_part',{'seed_file':str(source),'seed_feature_id':feature_id,
                         'sections':ops,'label':'blend','interpolation':'straight' if mode=='smooth' else 'smooth'},'seed_mode_mismatch',True)
            assert 'interpolation does not match' in mismatch.get('message','');report['mode_mismatch_rejected']=True;persist()
            if count==5:
                ops,zs,sizes,angles=profiles(count,True)
                p=await job('creo_new_loft_part',{'seed_file':str(source),'seed_feature_id':feature_id,'sections':ops,
                                                'label':'blend','interpolation':mode,'assertions':{'require_solid':True}},'foil_create')
                case={'initial':verify_native(p,count,mode),'profile':'NACA 0012 splines, finite trailing edge'}
                report['cases']['airfoil']=case;persist()
                plane=next(f for f in p['result']['inspection']['features'] if f['name']=='SECTION_2_PLANE')
                dim=next(d for d in plane['dimensions'] if abs(d['value']-zs[2])<1e-7);before=zs[2];zs[2]+=5
                p=await job('creo_set_dimensions',{'model_id':p['model_id'],'expected_revision':p['revision'],
                                    'values':[{'id':dim['id'],'value':zs[2]}]},'foil_edit_middle_plane')
                case['edited']=verify_native(p,count,mode,case['initial']['blend_feature_id'])
                assert abs(case['edited']['volume_mm3']-case['initial']['volume_mm3'])>.01
                case['middle_plane_edit']={'dimension_id':dim['id'],'symbol':dim['symbol'],'before_mm':before,'after_mm':zs[2]}
                assert any(abs(d['origin'][2]-zs[2])<1e-7 for d in p['result']['inspection']['datum_planes']);persist()
                for fmt in ['stl','step']:
                    exported=await job('creo_export_model',{'model_id':p['model_id'],'format':fmt},'foil_export_'+fmt)
                    file=next(o['file'] for o in exported['result']['operations'] if o['op']=='export');case[fmt+'_file']=file
                    if fmt=='stl':case['all_section_geometry']=verify_stl(file,zs,sizes,angles)
                    persist()
                case['success']=True
            report['source_file_unchanged']=sha(source)==report['source_sha256'];assert report['source_file_unchanged']
            report['success']=True
        except Exception as e:report['error']=str(e);raise
        finally:persist()
    print(json.dumps({'success':True,'sections':count,'interpolation':mode,'report':str(output)}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-file',required=True);parser.add_argument('--feature-id',required=True,type=int)
    parser.add_argument('--sections',choices=[3,5],required=True,type=int)
    parser.add_argument('--interpolation',choices=['straight','smooth'],required=True)
    parser.add_argument('--resume',action='store_true');a=parser.parse_args()
    asyncio.run(main(a.seed_file,a.feature_id,a.sections,a.interpolation,a.resume))
