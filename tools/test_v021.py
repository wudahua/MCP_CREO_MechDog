"""Native 0.21 integration cases. Creates separate owned test models, never user parts."""
import argparse
import asyncio
import json
import math
from pathlib import Path
import sys
import time
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from version import VERSION
REPORT=ROOT/'build/v021_integration_test.json'

async def call(client,name,args):
    result=await client.call_tool(name,args)
    if result.is_error: raise RuntimeError(str(result))
    return result.structured_content

async def job(client,name,args):
    created=await call(client,name,args)
    print(json.dumps({'tool':name,'job_id':created['job_id']},ensure_ascii=False),flush=True)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        result=await call(client,'creo_get_job',{'job_id':created['job_id']})
        if result['status'] in ('succeeded','failed','unknown_outcome'):
            if result['status']!='succeeded':
                print(json.dumps({k:result.get(k) for k in ('job_id','status','message','native_log_tail')},ensure_ascii=False,indent=2),flush=True)
                raise RuntimeError(f"Native job {created['job_id']} {result['status']}")
            if name!='creo_refresh_model':
                assert result['result']['saved_file_reloaded_and_verified']
            return result
        await asyncio.sleep(.5)
    raise TimeoutError('Unknown outcome; inspect existing job, do not resubmit')

def mid(result): return {'model_id':result['model_id'],'expected_revision':result['revision']}
def box(a=20,b=20,c=20,x=0):
    return [{'op':'sketch','label':'profile','plane':'XY','entities':[{'type':'rectangle','name':'box','min':[x,0],'max':[x+a,b]}]},
            {'op':'extrude','label':'solid','sketch':'profile','depth':c}]

async def run_case(client,name):
    jobs=[]
    async def run(tool,args):
        result=await job(client,tool,args);jobs.append(result);return result
    if name=='mirror':
        r=await run('creo_execute_plan',{'operations':box(10,10,5,5)})
        r=await run('creo_mirror',{**mid(r),'label':'reflected','plane':{'kind':'datum_plane','axis':'x'}})
        assert abs(r['result']['inspection']['volume_mm3']-1000)<.01
    elif name=='draft':
        r=await run('creo_execute_plan',{'operations':box()})
        r=await run('creo_draft',{**mid(r),'label':'taper','surfaces':[{'kind':'plane','axis':'x','offset':20}],
                                 'neutral_plane':{'kind':'datum_plane','axis':'z'},'angle':3})
        assert any(f['type']==921 for f in r['result']['inspection']['features']) or 'taper' in r['result']['aliases']
    elif name=='sweep':
        r=await run('creo_execute_plan',{'operations':[{'op':'sketch','label':'path','plane':'XY','entities':[{'type':'line','name':'axis','start':[0,0],'end':[40,0]}]}]})
        r=await run('creo_sweep',{**mid(r),'label':'pipe','trajectory':'path','profile':[{'type':'circle','name':'section','center':[0,0],'radius':2}],
                                  'dimensions':[{'name':'diameter','type':'diameter','refs':[{'entity':'section'}],'value':4,'position':[3,0]}]})
        assert abs(r['result']['inspection']['volume_mm3']-math.pi*4*40)<.01
        r=await run('creo_set_sketch_dimensions',{**mid(r),'sketch':'pipe','values':{'diameter':6}})
        assert abs(r['result']['inspection']['volume_mm3']-math.pi*9*40)<.01
    elif name=='sheetmetal':
        r=await run('creo_execute_plan',{'model_type':'sheetmetal','operations':[
            {'op':'sketch','label':'wall_profile','plane':'XY','entities':[{'type':'line','name':'l','start':[0,0],'end':[40,0]}]},
            {'op':'sheetmetal_wall','label':'wall','sketch':'wall_profile','depth':30,'thickness':1}],
            'assertions':{'require_solid':True}})
        surfaces=r['result']['inspection']['surfaces']
        candidates=[s for s in surfaces if s.get('sheetmetal_type')==2 and 'normal' in s]
        assert candidates, 'Native green planar sheetmetal surface not found'
        face=candidates[0]
        edges=r['result']['inspection']['edges']
        edge=next(e for e in edges if e.get('start') and e.get('end') and abs(e['start'][1]-face['origin'][1])<1e-7 and abs(e['end'][1]-face['origin'][1])<1e-7 and abs(e['start'][2])<1e-7 and abs(e['end'][2])<1e-7 and abs(e['start'][0]-e['end'][0])>39)
        r=await run('creo_sheetmetal_flange',{**mid(r),'label':'flange','edge':{'kind':'edge','id':edge['id']},'height':15,'radius':2})
        curved=[s for s in r['result']['inspection']['surfaces'] if 'radius' in s]
        assert {round(s['radius'],6) for s in curved}=={2,3}, curved
        assert any(s.get('normal') and abs(s['normal'][2])>.99 and s.get('sheetmetal_type')==2 for s in r['result']['inspection']['surfaces'])
        initial_volume=r['result']['inspection']['volume_mm3']
        r=await run('creo_set_sketch_dimensions',{**mid(r),'sketch':'flange','values':{'height':20}})
        assert abs(r['result']['inspection']['volume_mm3']-initial_volume-200)<.01
        bent_volume=r['result']['inspection']['volume_mm3']
        candidates=[s for s in r['result']['inspection']['surfaces'] if s.get('sheetmetal_type')==2 and s.get('normal') and abs(s['normal'][1])>.99]
        fixed={'kind':'surface','id':candidates[0]['id']}
        r=await run('creo_sheetmetal_unbend',{**mid(r),'label':'unbent','fixed_surface':fixed})
        assert not any('radius' in s for s in r['result']['inspection']['surfaces'])
        r=await run('creo_sheetmetal_bend_back',{**mid(r),'label':'bent_back','fixed_surface':fixed})
        assert abs(r['result']['inspection']['volume_mm3']-bent_volume)<.01
        r=await run('creo_sheetmetal_flat_pattern',{**mid(r),'label':'flat','fixed_surface':fixed})
        assert not any('radius' in s for s in r['result']['inspection']['surfaces'])
    elif name=='assembly':
        source=await run('creo_execute_plan',{'operations':box(10,8,6)+[{'op':'datum_plane','label':'component_x','reference':{'kind':'datum_plane','axis':'x'},'offset':0}]})
        r=await run('creo_new_assembly',{})
        r=await run('creo_assemble_component',{**mid(r),'label':'first','source_model_id':source['model_id']})
        r=await run('creo_assemble_component',{**mid(r),'label':'second','source_model_id':source['model_id'],'translation':[25,0,0],'rotation':[0,0,90]})
        assert len(r['result']['inspection']['components'])==2
        r=await run('creo_component_placement',{**mid(r),'component':'second','translation':[30,15,0],'rotation':[0,0,45]})
        r=await run('creo_remove_component',{**mid(r),'component':'second'})
        assert len(r['result']['inspection']['components'])==1
        constraints=[{'type':'align','assembly_reference':{'kind':'datum_plane','axis':a},'component_reference':{'kind':'datum_plane','axis':a}} for a in 'xyz']
        constraints[0]['component_reference']={'kind':'datum_feature','label':'component_x'}
        r=await run('creo_assemble_component',{**mid(r),'label':'constrained','source_model_id':source['model_id'],'placement':'constraints','constraints':constraints})
        comp=r['result']['inspection']['components'][-1]
        assert len(comp['constraints'])==3 and not comp['underconstrained'] and not comp['packaged']
        constraints[0]={**constraints[0],'type':'align_offset','offset':20}
        r=await run('creo_component_constraints',{**mid(r),'component':'constrained','constraints':constraints})
        assert abs(r['result']['inspection']['components'][-1]['transform'][3][0])>19.9
        source_query=await run('creo_refresh_model',{'model_id':source['model_id']})
        assert source_query['result']['inspection']['volume_mm3']==source['result']['inspection']['volume_mm3']
        assert source_query['result']['sha256']==source['result']['sha256']
        solid_id=source['result']['aliases']['solid']['feature_id']
        solid=next(f for f in source['result']['inspection']['features'] if f['id']==solid_id)
        depth=next(d for d in solid['dimensions'] if abs(d['value']-6)<1e-8)
        edited=await run('creo_set_dimensions',{**mid(source),'values':[{'id':depth['id'],'value':8}]})
        assert abs(edited['result']['inspection']['volume_mm3']-640)<.01
        assembly_query=await run('creo_refresh_model',{'model_id':r['model_id']})
        assert abs(assembly_query['result']['inspection']['volume_mm3']-960)<.01
    elif name=='sheetmetal_wall':
        r=await run('creo_execute_plan',{'model_type':'sheetmetal','operations':[
            {'op':'sketch','label':'wall_profile','plane':'XY','entities':[{'type':'line','name':'l','start':[0,0],'end':[40,0]}]},
            {'op':'sheetmetal_wall','label':'wall','sketch':'wall_profile','depth':30,'thickness':1}],
            'assertions':{'require_solid':True,'volume_mm3':1200}})
        assert any(s.get('sheetmetal_type')==2 for s in r['result']['inspection']['surfaces'])
    elif name=='disabled_tools':
        base={'model_id':'a'*32,'expected_revision':1,'label':'unavailable'}
        specs={
            'creo_loft':{'sections':['first','second']},
        }
        for tool,args in specs.items():
            result=await client.call_tool(tool,{**base,**args})
            assert result.is_error and 'no native job was queued' in str(result), str(result)
    elif name=='loft':
        r=await run('creo_execute_plan',{'operations':[
            {'op':'sketch','label':'bottom','plane':'XY','entities':[{'type':'rectangle','name':'a','min':[-10,-10],'max':[10,10]}]},
            {'op':'sketch','label':'top','plane':'XY','offset':30,'entities':[{'type':'rectangle','name':'b','min':[-5,-5],'max':[5,5]}]}]})
        r=await run('creo_loft',{**mid(r),'label':'transition','sections':['bottom','top']})
        assert abs(r['result']['inspection']['volume_mm3']-7000)<.01
    else: raise ValueError(name)
    return jobs

async def main(selected):
    report=json.loads(REPORT.read_text(encoding='utf-8')) if REPORT.is_file() else {'version':VERSION,'cases':{}}
    if report.get('version')!=VERSION: report={'version':VERSION,'cases':{}}
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=ROOT)
    async with Client(params,mode='legacy',read_timeout_seconds=90) as client:
        tools=await client.list_tools();report['tools']=[t.name for t in tools.tools]
        cap=await call(client,'creo_capabilities',{});assert cap['version']==VERSION;report['tool_count']=len(tools.tools)
        for name in selected:
            try:
                results=await run_case(client,name)
                report['cases'][name]={'success':True,'jobs':results}
                print('CASE_SUCCEEDED='+name,flush=True)
            except Exception as exc:
                report['cases'][name]={'success':False,'error':str(exc)}
                print('CASE_FAILED='+name+': '+str(exc),flush=True)
            report['selected_cases']=selected
            report['success']=all(report['cases'].get(n,{}).get('success',False) for n in selected)
            report['all_requested_families_verified']=False
            REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(report['cases'][name]['success'] for name in selected): raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only',default='mirror,draft,sweep,sheetmetal_wall,sheetmetal,assembly,disabled_tools')
    args=parser.parse_args();asyncio.run(main(args.only.split(',')))
