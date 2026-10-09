"""Integration evidence for the development build; does not replace 0.21 release evidence."""
import asyncio, json, sys, time
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION
REPORT=ROOT/'build/development_integration.json'

async def main():
    report={'version':VERSION,'started_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'jobs':[],'success':False}
    cached=[]
    if '--resume' in sys.argv and REPORT.exists():
        old=json.loads(REPORT.read_text(encoding="utf-8"))
        assert old['version']==VERSION
        for item in old['jobs']:
            if item['status']!='succeeded' and not (item.get('expected_failure') and item['status']=='failed'): break
            cached.append(item)
        (ROOT/'.tmp'/('drawing_test_attempt_'+str(int(time.time()))+'.json')).write_text(json.dumps(old,indent=2),encoding="utf-8")
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT))) as c:
        async def call(name,args):
            r=await c.call_tool(name,args)
            if r.is_error: raise RuntimeError(str(r))
            return r.structured_content
        async def run(name,args,expect_failure=False):
            if len(report['jobs'])<len(cached):
                item=cached[len(report['jobs'])]
                assert item['tool']==name and item.get('expected_failure',False)==expect_failure
                r=await call('creo_get_job',{'job_id':item['job_id']})
                report['jobs'].append(item)
                return r
            created=await call(name,args);jid=created['job_id'];print(json.dumps({'tool':name,'job_id':jid}),flush=True)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                r=await call('creo_get_job',{'job_id':jid})
                if r['status'] in ('succeeded','failed','unknown_outcome'): break
                await asyncio.sleep(.5)
            else: raise TimeoutError('Unknown outcome; inspect current job without resubmission')
            report['jobs'].append({'job_id':jid,'tool':name,'status':r['status'],'model_id':r['model_id'],'revision':r.get('revision'),'expected_failure':expect_failure})
            REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")
            if expect_failure:
                assert r['status']=='failed' and r['result']['rollback_succeeded'],r
            else:
                if r['status']!='succeeded':
                    print(json.dumps({k:r.get(k) for k in ['status','message','native_log_tail']},ensure_ascii=False),flush=True)
                    raise RuntimeError('Native job failed: '+jid)
                if not r.get('readonly'): assert r['result']['saved_file_reloaded_and_verified']
            return r
        def mid(r):return {'model_id':r['model_id'],'expected_revision':r['revision']}
        p=await run('creo_execute_plan',{'operations':[
            {'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[80,60]}]},
            {'op':'extrude','label':'block','sketch':'profile','depth':20}], 'assertions':{'volume_mm3':96000}})
        report['source_model_id']=p['model_id']
        d=await run('creo_new_drawing',{'source_model_id':p['model_id']})
        report['drawing_model_id']=d['model_id']
        d=await run('creo_drawing_view',{**mid(d),'label':'front','position':[75,110],'orientation':'front'})
        d=await run('creo_drawing_projection',{**mid(d),'label':'top','parent':'front','position':[75,165]})
        d=await run('creo_drawing_projection',{**mid(d),'label':'right','parent':'front','position':[190,110]})
        d=await run('creo_drawing_view',{**mid(d),'label':'iso','position':[230,165],'orientation':'isometric','scale':.5})
        d=await run('creo_drawing_note',{**mid(d),'label':'spec','lines':['MCP_CREO_MechDog','80 x 60 x 20 mm'],'position':[20,30]})
        d=await run('creo_drawing_table',{**mid(d),'label':'parts','columns':[30,40],'cells':[['Item','Description'],['1','Test block']],'position':[170,50]})
        block=next(f for f in p['result']['inspection']['features'] if f['id']==p['result']['aliases']['block']['feature_id'])
        dimension=next(dim['id'] for dim in block['dimensions'] if dim['type']>=0 and abs(dim['value']-20)<1e-6)
        d=await run('creo_drawing_dimension',{**mid(d),'label':'height','view':'front','dimension_id':dimension,'position':[125,110]})
        d=await run('creo_execute_plan',{**mid(d),'operations':[
            {'op':'drawing_view_update','view':'iso','move':[0,-5],'scale':.4,'display':'hidden'},
            {'op':'drawing_note_update','note':'spec','lines':['MCP_CREO_MechDog','Verified native drawing'],'position':[20,32]},
            {'op':'drawing_table_cell','table':'parts','row':2,'column':2,'text':'Parametric block'},
            {'op':'drawing_sheet','action':'add','width':297,'height':210,'name':'detail'},
            {'op':'drawing_note','label':'second','sheet':2,'position':[20,180],'lines':['Second sheet - saved and reloaded']}]})
        assert len(d['result']['inspection']['sheets'])==2
        assert len(d['result']['inspection']['views'])==4
        assert d['result']['inspection']['tables'][-1]['cells'][1][1]=='Parametric block'
        baseline=d
        await run('creo_execute_plan',{**mid(d),'operations':[
            {'op':'drawing_note_update','note':'spec','lines':['THIS CHANGE MUST ROLL BACK']},
            {'op':'drawing_table_cell','table':'parts','row':99,'column':1,'text':'invalid'}]},expect_failure=True)
        refreshed=await run('creo_refresh_model',{'model_id':d['model_id']})
        assert refreshed['result']['inspection']==baseline['result']['inspection']
        p=await run('creo_set_dimensions',{**mid(p),'values':[{'id':dimension,'value':30}]})
        d=await run('creo_regenerate',mid(baseline))
        assert d['result']['inspection']['models'][0]['inspection']['volume_mm3']==96000
        d=await run('creo_execute_plan',{**mid(d),'operations':[
            {'op':'drawing_delete','kind':'note','target':'second'},
            {'op':'drawing_delete','kind':'dimension','target':'height'},
            {'op':'drawing_dimension','label':'height_again','view':'front','dimension_id':dimension,'position':[125,110]},
            {'op':'drawing_note','label':'final_note','sheet':2,'position':[20,180],'lines':['Native drawing operations verified']} ]})
        pdf=await run('creo_export_model',{'model_id':d['model_id'],'format':'pdf'})
        paths=[x['file'] for x in pdf['result']['operations'] if 'file' in x]
        assert paths and Path(paths[0]).is_file() and Path(paths[0]).stat().st_size>1000
        report.update(success=True,source_file=p['result']['part_file'],drawing_file=d['result']['part_file'],pdf_file=paths[0],finished_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
        REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps({'success':True,'jobs':len(report['jobs']),'pdf_file':paths[0]}),flush=True)

if __name__=='__main__':asyncio.run(main())
