"""Test native UDF placement using the user's locally installed PTC example (not distributed)."""
import asyncio,json,sys,time,math
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bridge
from version import VERSION

async def main():
    library=Path(bridge.config()['creo_root'])/'Common Files/otk_java_free/otk_java_appls/jlinkexamples/models/node.gph'
    if not library.is_file(): raise SystemExit('Install the local PTC node.gph example to run this fixture')
    report={'version':VERSION,'success':False,'jobs':[]}
    output=ROOT/'build/udf_integration.json'
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT))) as c:
        async def job(tool,args,fail=False):
            r=await c.call_tool(tool,args)
            if r.is_error: raise RuntimeError(str(r))
            jid=r.structured_content['job_id'];print(json.dumps({'tool':tool,'job_id':jid}),flush=True)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                r=(await c.call_tool('creo_get_job',{'job_id':jid})).structured_content
                if r['status'] in ('succeeded','failed','unknown_outcome'):break
                await asyncio.sleep(.5)
            else:raise TimeoutError('Inspect current job; do not resubmit')
            report['jobs'].append({'job_id':jid,'status':r['status'],'expected_failure':fail})
            output.write_text(json.dumps(report,indent=2),encoding='utf-8')
            if fail: assert r['status']=='failed' and r['result']['rollback_succeeded'],r.get('message')
            else:
                assert r['status']=='succeeded',r.get('message')
                if not r['readonly']:assert r['result']['saved_file_reloaded_and_verified']
            return r
        p=await job('creo_execute_plan',{'operations':[{'op':'sketch','label':'stock_profile','offset':-20,'entities':[{'type':'rectangle','name':'rect','min':[-20,-20],'max':[20,20]}]},{'op':'extrude','label':'stock','sketch':'stock_profile','depth':40}],'assertions':{'volume_mm3':64000}})
        m=await job('creo_inspect_udf',{'model_id':p['model_id'],'file_path':str(library)})
        metadata=next(op['metadata'] for op in m['result']['operations'] if 'metadata' in op)
        assert metadata['references'][0]['prompt']=='REF_CSYS'
        key=metadata['dimensions'][0]['name']
        args={'model_id':p['model_id'],'expected_revision':p['revision'],'label':'node','file_path':str(library),'dimensions':{key:10}}
        await job('creo_create_udf',{**args,'references':{}},fail=True)
        p=await job('creo_create_udf',{**args,'references':{'REF_CSYS':{'kind':'default_csys'}}})
        alias=p['result']['aliases']['node'];assert alias['member_feature_ids']
        features=p['result']['inspection']['features'];members=set(alias['member_feature_ids'])
        dims=[d for f in features if f['id'] in members for d in f['dimensions'] if abs(d['value']-10)<1e-6 and d['type']>=0]
        assert dims,'The requested UDF diameter must be an editable native dimension'
        before=p['result']['inspection']['volume_mm3'];assert abs(before-(64000-math.pi/4*10**2*40))<.01
        p=await job('creo_set_dimensions',{'model_id':p['model_id'],'expected_revision':p['revision'],'values':[{'id':dims[0]['id'],'value':20}]})
        after=p['result']['inspection']['volume_mm3'];assert abs((64000-after)/(64000-before)-4)<1e-5,(before,after)
        report.update(success=True,model_id=p['model_id'],part_file=p['result']['part_file'],volume_before=before,volume_after=after,metadata=metadata)
        output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'success':True,'volume_before':before,'volume_after':after}),flush=True)

if __name__=='__main__':asyncio.run(main())
