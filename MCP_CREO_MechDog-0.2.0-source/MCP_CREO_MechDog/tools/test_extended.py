"""Real MCP tests of operations beyond the general core. Each case is resumable."""
import asyncio,json,math,sys,time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'build/extended_integration_test.json'
report=json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.exists() else {'cases':[], 'started_at':time.time()}

async def call(c,name,args):
    r=await c.call_tool(name,args)
    if r.is_error: raise RuntimeError(str(r.content))
    return r.structured_content

async def job(c,name,args):
    submit=await call(c,name,args)
    for _ in range(720):
        r=await call(c,'creo_get_job',{'job_id':submit['job_id']})
        if r['status'] not in ('queued','running'): break
        await asyncio.sleep(1)
    report['cases'].append({'tool':name,'args':args,'job':r})
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,r['job_id'],r['status'],r.get('message'),flush=True)
    assert r['status']=='succeeded',str((r['job_id'],r.get('message')))
    return r

def box(x=40,y=30,z=12):
    return [{'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[x,y]}]},
            {'op':'extrude','label':'solid','sketch':'profile','depth':z}]

def state(r): return r['result']['inspection']
def mid(r): return {'model_id':r['model_id'],'expected_revision':r['revision']}

async def case(c,which):
    if which=='shell':
        r=await job(c,'creo_execute_plan',{'operations':box(20,30,10)+[
            {'op':'shell','label':'shell','thickness':2,'remove_surfaces':[{'kind':'plane','axis':'z','offset':10}]}],
            'assertions':{'volume_mm3':2672,'require_solid':True}})
    elif which=='edges':
        r=await job(c,'creo_execute_plan',{'operations':box()})
        vertical=next(e for e in state(r)['edges'] if 'start' in e and abs(e['start'][0]-e['end'][0])<1e-6 and abs(e['start'][1]-e['end'][1])<1e-6)
        r=await job(c,'creo_round',{**mid(r),'label':'corner','radius':2,'references':[{'edge':{'kind':'edge','id':vertical['id']}}]})
        top=next(e for e in state(r)['edges'] if 'start' in e and abs(e['start'][2]-12)<1e-6 and abs(e['end'][2]-12)<1e-6)
        r=await job(c,'creo_chamfer',{**mid(r),'label':'bevel','distance':1,'references':[{'edge':{'kind':'edge','id':top['id']}}]})
        assert any(f['type_name']=='round' for f in state(r)['features'])
        assert any(f['type_name']=='chamfer' for f in state(r)['features'])
    elif which=='pattern':
        r=await job(c,'creo_execute_plan',{'operations':box(100,60,10)+[
            {'op':'hole','label':'seed','diameter':4,'placement':{'kind':'plane','axis':'z','offset':10},
             'reference1':{'kind':'datum_plane','axis':'x'},'reference2':{'kind':'datum_plane','axis':'y'},'offset1':10,'offset2':10}]})
        f=next(f for f in state(r)['features'] if f['id']==r['result']['aliases']['seed']['feature_id'])
        d=next(d for d in f['dimensions'] if abs(d['value']-10)<1e-6)
        r=await job(c,'creo_dimension_pattern',{**mid(r),'label':'holes','feature':'seed','dimension_id':d['id'],'count':3,'increment':20})
        assert abs(state(r)['volume_mm3']-(60000-120*math.pi))<0.01
    elif which=='curves':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'semicircle','entities':[{'type':'line','name':'base','start':[-10,0],'end':[10,0]},
             {'type':'arc','name':'arc','center':[0,0],'radius':10,'start_angle':0,'end_angle':180}]},
            {'op':'extrude','label':'half_disk','sketch':'semicircle','depth':3},
            {'op':'sketch','label':'elliptic','entities':[{'type':'ellipse','name':'oval','center':[40,0],'x_radius':8,'y_radius':5}]},
            {'op':'extrude','label':'ellipse_solid','sketch':'elliptic','depth':2,'new_body':True}],
            'assertions':{'volume_mm3':230*math.pi,'require_solid':True}})
        assert sum(b['state']==4 for b in state(r)['bodies'])==2
    elif which=='spline':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'spline_profile','entities':[{'type':'spline','name':'path','points':[[0,0],[10,5],[20,0]]}]},
            {'op':'extrude','label':'spline_surface','sketch':'spline_profile','depth':5,'mode':'surface'}]})
    elif which=='thin':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'line_profile','entities':[{'type':'line','name':'line','start':[0,0],'end':[20,0]}]},
            {'op':'extrude','label':'wall','sketch':'line_profile','depth':10,'thin':2,'direction':'symmetric'}],
            'assertions':{'volume_mm3':400,'require_solid':True}})
        b=next(b for b in state(r)['bodies'] if b['state']==4)['bbox']
        assert abs(b[0][2]+5)<1e-6 and abs(b[1][2]-5)<1e-6,b
    elif which=='cut':
        r=await job(c,'creo_execute_plan',{'operations':box(40,30,12)+[
            {'op':'sketch','label':'pocket_profile','plane':'XY','offset':12,'entities':[{'type':'circle','name':'disk','center':[20,15],'radius':3}]},
            {'op':'extrude','label':'through_cut','sketch':'pocket_profile','mode':'cut','depth_type':'through_all','direction':'negative'}],
            'assertions':{'volume_mm3':14400-108*math.pi,'require_solid':True}})
    elif which=='pocket':
        r=await job(c,'creo_execute_plan',{'operations':box(40,30,12)+[
            {'op':'sketch','label':'pocket_profile','plane':'XY','offset':12,'entities':[{'type':'circle','name':'disk','center':[20,15],'radius':3}]},
            {'op':'extrude','label':'pocket','sketch':'pocket_profile','mode':'cut','depth':5,'direction':'negative'}],
            'assertions':{'volume_mm3':14400-45*math.pi,'require_solid':True}})
        r=await job(c,'creo_regenerate',mid(r))
        r=await job(c,'creo_save_model',mid(r))
    elif which=='outward_shell':
        await job(c,'creo_execute_plan',{'operations':box(20,30,10)+[
            {'op':'shell','label':'shell','thickness':2,'outward':True,'remove_surfaces':[{'kind':'plane','axis':'z','offset':10}]}],
            'assertions':{'volume_mm3':3792,'require_solid':True}})
    elif which=='relations':
        core=json.loads((ROOT/'build/general_integration_test.json').read_text(encoding='utf-8'))
        model=await call(c,'creo_inspect_model',{'model_id':core['main_models']['disk']})
        f=next(f for f in model['inspection']['features'] if f['id']==model['aliases']['disk_solid']['feature_id'])
        d=next(d for d in f['dimensions'] if abs(d['value']-10)<1e-6)
        r=await job(c,'creo_execute_plan',{'model_id':model['model_id'],'expected_revision':model['revision'],'operations':[
            {'op':'set_parameters','values':{'SIZE':14.0,'DESCRIPTION':'native relation test','VALID':True}},
            {'op':'set_relations','lines':[d['symbol']+' = SIZE']}],
            'assertions':{'volume_mm3':1400*math.pi}})
        r=await job(c,'creo_execute_plan',{**mid(r),'operations':[{'op':'set_parameters','values':{'SIZE':16.0}}],
            'assertions':{'volume_mm3':1600*math.pi}})
    elif which=='datum':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'datum_plane','label':'offset','reference':{'kind':'datum_plane','axis':'z'},'offset':5},
            {'op':'datum_axis','label':'axis','references':[{'kind':'datum_plane','axis':'x'},{'kind':'datum_plane','axis':'y'}]}]})
        # Advanced element tree creates another offset plane without a recipe.
        r=await job(c,'creo_create_feature_tree',{**mid(r),'label':'advanced_plane','tree':{'id':'PRO_E_FEATURE_TREE','children':[
            {'id':'PRO_E_FEATURE_TYPE','integer':923},
            {'id':'PRO_E_STD_FEATURE_NAME','string':'advanced_plane'},
            {'id':'PRO_E_DTMPLN_CONSTRAINTS','children':[{'id':'PRO_E_DTMPLN_CONSTRAINT','children':[
                {'id':'PRO_E_DTMPLN_CONSTR_TYPE','integer':'PRO_DTMPLN_OFFS'},
                {'id':'PRO_E_DTMPLN_CONSTR_REF','reference':{'kind':'datum_plane','axis':'z'}},
                {'id':'PRO_E_DTMPLN_CONSTR_REF_OFFSET','double':7}]}]}]}})
        r=await job(c,'creo_dump_feature_tree',{'model_id':r['model_id'],'feature':'advanced_plane'})
    elif which=='constraints':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[20,15]}],
             'constraints':[{'type':'horizontal','refs':[{'entity':'box_0'}]},{'type':'vertical','refs':[{'entity':'box_1'}]}],
             'dimensions':[{'name':'width','type':'length','refs':[{'entity':'box_0'}],'value':20,'position':[10,-5]}]},
            {'op':'extrude','label':'solid','sketch':'profile','depth':5}],
            'assertions':{'volume_mm3':1500}})
    elif which=='oblique':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'datum_axis','label':'axis','references':[{'kind':'datum_plane','axis':'y'},{'kind':'datum_plane','axis':'z'}]},
            {'op':'datum_plane','label':'angled','reference':{'kind':'datum_plane','axis':'z'},'angle':30,'axis':{'kind':'datum_axis_feature','label':'axis'}},
            {'op':'sketch','label':'profile','plane':{'reference':{'kind':'datum_feature','label':'angled'},'origin':[0,0,0],'u_axis':[1,0,0]},
             'entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[20,10]}]},
            {'op':'extrude','label':'solid','sketch':'profile','depth':4}],
            'assertions':{'volume_mm3':800,'require_solid':True}})
    elif which=='partial':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'datum_axis','label':'axis','references':[{'kind':'datum_plane','axis':'x'},{'kind':'datum_plane','axis':'y'}]},
            {'op':'sketch','label':'profile','plane':'XZ','entities':[{'type':'rectangle','name':'section','min':[0,0],'max':[10,20]}]},
            {'op':'revolve','label':'half','sketch':'profile','angle':180,'axis':{'kind':'datum_axis_feature','label':'axis'}}],
            'assertions':{'volume_mm3':1000*math.pi,'require_solid':True}})
    elif which=='dimensions':
        r=await job(c,'creo_execute_plan',{'operations':box(22,14,6)})
        f=next(f for f in state(r)['features'] if f['id']==r['result']['aliases']['solid']['feature_id'])
        d=next(d for d in f['dimensions'] if abs(d['value']-6)<1e-6)
        r=await job(c,'creo_set_dimensions',{**mid(r),'values':[{'id':d['id'],'value':9}]})
        assert abs(state(r)['volume_mm3']-2772)<0.01
    elif which=='directions':
        r=await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','entities':[{'type':'circle','name':'circle','center':[0,0],'radius':3}]},
            {'op':'extrude','label':'negative','sketch':'profile','depth':6,'direction':'negative'},
            {'op':'sketch','label':'yz_profile','plane':'YZ','offset':20,'entities':[{'type':'circle','name':'circle','center':[0,0],'radius':4}]},
            {'op':'extrude','label':'yz_solid','sketch':'yz_profile','depth':5,'new_body':True}],
            'assertions':{'volume_mm3':134*math.pi,'require_solid':True}})
        bodies=[b['bbox'] for b in state(r)['bodies'] if b['state']==4]
        assert any(abs(b[0][2]+6)<1e-6 and abs(b[1][2])<1e-6 for b in bodies),bodies
        assert any(abs(b[0][0]-20)<1e-6 and abs(b[1][0]-25)<1e-6 for b in bodies),bodies
    elif which=='revolve_modes':
        entities=[{'type':'line','name':'wall','start':[10,0],'end':[10,20]},
                  {'type':'centerline','name':'axis','start':[0,-5],'end':[0,25]}]
        await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','plane':'XZ','entities':entities},
            {'op':'revolve','label':'surface','sketch':'profile','mode':'surface','angle':180}]})
        await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','plane':'XZ','entities':entities},
            {'op':'revolve','label':'thin','sketch':'profile','thin':2}],
            'assertions':{'volume_mm3':800*math.pi,'require_solid':True}})
        await job(c,'creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','plane':'XZ','entities':[{'type':'rectangle','name':'section','min':[0,0],'max':[10,20]},entities[1]]},
            {'op':'revolve','label':'symmetric','sketch':'profile','angle':90,'direction':'symmetric'}],
            'assertions':{'volume_mm3':500*math.pi,'require_solid':True}})
    elif which=='export':
        core=json.loads((ROOT/'build/general_integration_test.json').read_text(encoding='utf-8'))
        for fmt in ('step','stl','iges','jpeg'):
            r=await job(c,'creo_export_model',{'model_id':core['main_models']['turned'],'format':fmt})
            files=[o['file'] for o in r['result']['operations'] if 'file' in o]
            assert files and all(Path(p).exists() and Path(p).stat().st_size>100 for p in files)
    else: raise ValueError(which)

async def main():
    names=sys.argv[1:] or ['shell','outward_shell','edges','pattern','curves','spline','thin','cut','pocket','relations','datum','constraints','oblique','partial','dimensions','directions','revolve_modes','export']
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=ROOT),read_timeout_seconds=60) as c:
        for name in names:
            try:
                report.setdefault('failures',{}).pop(name,None)
                await case(c,name)
                print('CASE_PASS='+name,flush=True)
            except Exception as e:
                print('CASE_FAIL='+name+' '+str(e),flush=True)
                report.setdefault('failures',{})[name]=str(e)
    report['success']=not report.get('failures')
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('EXTENDED_SUCCESS='+str(int(report['success'])),flush=True)
if __name__=='__main__': asyncio.run(main())
