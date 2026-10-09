"""Native datum, surface and multibody integration tests for the development build."""
import argparse, asyncio, json, sys, time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION
REPORT=ROOT/'build/surface_integration.json'

def box(label='base',x=0,width=10,depth=10,height=10,new=False):
    return [{'op':'sketch','label':label+'_profile','entities':[{'type':'rectangle','name':'box','min':[x,0],'max':[x+width,depth]}]},
            {'op':'extrude','label':label,'sketch':label+'_profile','depth':height,'new_body':new}]

async def main(only):
    report=json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    if report.get('version')!=VERSION: report={'version':VERSION,'cases':{}}
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT))) as c:
        for name in only:
            case={'success':False,'jobs':[]};report['cases'][name]=case
            async def job(tool,args):
                r=await c.call_tool(tool,args)
                if r.is_error: raise RuntimeError(str(r))
                jid=r.structured_content['job_id'];case['jobs'].append(jid)
                print(json.dumps({'case':name,'tool':tool,'job_id':jid}),flush=True)
                deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    r=(await c.call_tool('creo_get_job',{'job_id':jid})).structured_content
                    if r['status'] in ('succeeded','failed','unknown_outcome'): break
                    await asyncio.sleep(.5)
                else: raise TimeoutError('Inspect current job; never blindly resubmit')
                REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")
                if r['status']!='succeeded': raise RuntimeError(json.dumps({'job_id':jid,'status':r['status'],'message':r.get('message')}))
                assert r['result']['saved_file_reloaded_and_verified']
                return r
            def mid(r):return {'model_id':r['model_id'],'expected_revision':r['revision']}
            if name=='datums':
                r=await job('creo_execute_plan',{'operations':[
                    {'op':'datum_csys','label':'offset','translation':[10,20,30],'rotation':[0,0,45]},
                    {'op':'datum_points','label':'points','reference':{'kind':'datum_csys_feature','label':'offset'},'points':[{'name':'a','position':[1,2,3]},{'name':'b','position':[10,5,0]}]}]})
                f=next(f for f in r['result']['inspection']['features'] if f['id']==r['result']['aliases']['offset']['feature_id'])
                frame=next(o for o in r['result']['operations'] if 'origin' in o)
                assert all(abs(a-b)<1e-6 for a,b in zip(frame['origin'],[10,20,30])),frame
                assert len(f['dimensions'])==6
                r=await job('creo_set_dimensions',{**mid(r),'values':[{'id':next(d['id'] for d in f['dimensions'] if abs(d['value']-10)<1e-6),'value':15}]})
            elif name=='thicken':
                r=await job('creo_execute_plan',{'operations':[
                    {'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'rect','min':[0,0],'max':[20,10]}]},
                    {'op':'surface_fill','label':'patch','sketch':'profile'},
                    {'op':'thicken','label':'plate','reference':{'kind':'quilt_feature','label':'patch'},'thickness':2}],
                    'assertions':{'volume_mm3':400,'require_solid':True}})
                f=next(f for f in r['result']['inspection']['features'] if f['id']==r['result']['aliases']['plate']['feature_id'])
                dim=next(d for d in f['dimensions'] if abs(d['value']-2)<1e-6)
                r=await job('creo_execute_plan',{**mid(r),'operations':[{'op':'set_dimensions','values':[{'id':dim['id'],'value':3}]}],'assertions':{'volume_mm3':600}})
            elif name in ('union','subtract','intersect'):
                r=await job('creo_execute_plan',{'operations':box()+box('tool',x=5,new=True)})
                bodies=[b['id'] for b in r['result']['inspection']['bodies'] if b['state']==4]
                assert len(bodies)==2
                expected={'union':1500,'subtract':500,'intersect':500}[name]
                r=await job('creo_execute_plan',{**mid(r),'operations':[{'op':'boolean_bodies','label':'combined','method':name,
                    'targets':[{'kind':'body','id':bodies[0]}],'tools':[{'kind':'body','id':bodies[1]}]}],'assertions':{'volume_mm3':expected}})
            elif name=='solidify':
                r=await job('creo_execute_plan',{'operations':box()+[
                    {'op':'datum_plane','label':'midplane','reference':{'kind':'datum_plane','axis':'x'},'offset':5},
                    {'op':'solidify','label':'trim','reference':{'kind':'datum_feature','label':'midplane'},'mode':'cut'}],
                    'assertions':{'volume_mm3':500}})
            elif name=='rib':
                r=await job('creo_execute_plan',{'operations':box(width=40,depth=30,height=5)+box('wall',width=5,depth=30,height=30)+[
                    {'op':'sketch','label':'rib_profile','plane':'XZ','offset':15,'entities':[{'type':'line','name':'slope','start':[5,25],'end':[35,5]}]},
                    {'op':'rib','label':'gusset','sketch':'rib_profile','thickness':3,'flip':True}],'assertions':{'require_solid':True}})
                before=r['result']['inspection']['volume_mm3'];assert abs(before-10650)<.01
                f=next(f for f in r['result']['inspection']['features'] if f['id']==r['result']['aliases']['gusset']['feature_id'])
                dim=next(d for d in f['dimensions'] if abs(d['value']-3)<1e-6)
                r=await job('creo_execute_plan',{**mid(r),'operations':[{'op':'set_dimensions','values':[{'id':dim['id'],'value':4}]}],'assertions':{'volume_mm3':9750+(before-9750)*4/3}})
            else: raise ValueError(name)
            case.update(success=True,model_id=r['model_id'],part_file=r['result']['part_file'],volume_mm3=r['result']['inspection']['volume_mm3'])
            REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps({'case':name,'success':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--only',default='datums,thicken,union,subtract,intersect,solidify,rib');a=p.parse_args();asyncio.run(main(a.only.split(',')))
