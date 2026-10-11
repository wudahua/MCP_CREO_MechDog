"""Real MCP/Creo acceptance: auto seeds, airfoil edits, group patterns and rigid placement. Creates separate owned parts; requires an idle licensed Creo session."""
import argparse
import uuid
import asyncio
import json
import math
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mcp import Client
from mcp.client.stdio import StdioServerParameters
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',type=Path)
parser.add_argument('--resume',action='store_true')
parser.add_argument('--stage',choices=['airfoil','export','pattern','body','quilt','all'],default='all')
args=parser.parse_args()
OUT=(args.output_dir or ROOT/'build'/('portable_'+uuid.uuid4().hex[:8])).resolve()
OUT.mkdir(parents=True,exist_ok=True)
STATE=OUT/'state.json'
if STATE.exists() and not args.resume:raise SystemExit('Existing report: use --resume to query previous jobs; never recreate unknown outcomes')

async def main(stage):
    state=json.loads(STATE.read_text()) if STATE.exists() else {'jobs':[],'run_id':uuid.uuid4().hex[:8]}
    def persist():STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT))) as client:
        async def call(name,args):
            result=await client.call_tool(name,args)
            if result.is_error:raise RuntimeError(str(result))
            return result.structured_content
        async def job(name,tool,args):
            previous=next((j for j in state['jobs'] if j['name']==name),None)
            if previous is None:
                result=await call(tool,args)
                previous={'name':name,'job_id':result['job_id'],'tool':tool}
                state['jobs'].append(previous);persist()
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                result=await call('creo_get_job',{'job_id':previous['job_id']})
                if result['status'] in ('succeeded','failed','unknown_outcome'):break
                await asyncio.sleep(.5)
            previous['status']=result['status'];previous['result']=result;persist()
            if result['status']!='succeeded':
                raise RuntimeError(json.dumps({'name':name,'status':result['status'],'message':result.get('message'),
                                   'rollback_succeeded':result.get('rollback_succeeded')},ensure_ascii=False))
            assert result['result']['saved_file_reloaded_and_verified']
            state.update(model_id=result['model_id'],revision=result['revision'],last_result=result['result']);persist()
            print(json.dumps({'name':name,'status':result['status'],'revision':result['revision'],
                              'volume':result['result']['inspection'].get('volume_mm3')},ensure_ascii=False),flush=True)
            return result
        if stage=='airfoil':
            choices=await call('creo_list_seeds',{})
            assert choices['available_count']==3
            for seed in choices['seeds']:
                assert (await call('creo_validate_seed',{'seed_name':seed['name']}))['available']
            assert (await call('creo_install_seed_library',{}))['available_count']==3
            state['seeds']=[{k:seed[k] for k in ('name','section_count','interpolation','sha256','available')} for seed in choices['seeds']];persist()
            stations=[dict(offset=z,chord=c,twist_deg=a) for z,c,a in [(5,8,30),(24,23,25),(55,28,18),(90,20,12),(120,9,7)]]
            first=await job('create_airfoil','creo_new_airfoil_blade',{'model_name':'mcp_air_'+state['run_id'],'stations':stations})
            state['initial_ids']={k:v['feature_id'] for k,v in first['result']['aliases'].items()};persist()
            edited=await job('edit_airfoil','creo_set_airfoil_parameters',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'sketch':'blade_section_3',
                'values':{'chord':32,'thickness_ratio':.15,'twist_deg':12}})
            assert all(edited['result']['aliases'][k]['feature_id']==v for k,v in state['initial_ids'].items())
            assert abs(first['result']['inspection']['volume_mm3']-edited['result']['inspection']['volume_mm3'])>1
            again=await job('edit_airfoil_again','creo_set_airfoil_parameters',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'sketch':'blade_section_3','values':{'twist_deg':16,'origin':[1,0]}})
            assert all(again['result']['aliases'][k]['feature_id']==v for k,v in state['initial_ids'].items())
            state['airfoil_passed']=True;persist()
        elif stage=='export':
            result=await job('export_airfoil','creo_execute_plan',{'model_id':state['model_id'],'expected_revision':state['revision'],
                             'operations':[{'op':'export','format':'stl'}]})
            from tools.test_multisection_blend import stl_vertices,plane_boundary
            import airfoil
            path=next(row['file'] for row in result['result']['operations'] if row.get('file','').endswith('.stl'))
            triangles=stl_vertices(path);points=plane_boundary(triangles,55)
            profile=dict(chord=32,thickness_ratio=.15,twist_deg=16,origin=[1,0])
            curves=airfoil.entities(profile)
            boundary=curves[0]['points']+curves[2]['points']
            def distance(point,a,b):
                dx,dy=b[0]-a[0],b[1]-a[1];length=dx*dx+dy*dy
                t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length)) if length else 0
                return math.hypot(point[0]-a[0]-t*dx,point[1]-a[1]-t*dy)
            maximum=max(min(distance(p,boundary[i],boundary[(i+1)%len(boundary)]) for i in range(len(boundary))) for p in points)
            assert maximum<.15,maximum
            state['actual_section_deviation_mm']=maximum;state['actual_section_points']=len(points);persist()
            print(json.dumps({'actual_section_deviation_mm':maximum,'points':len(points)}),flush=True)
        elif stage=='pattern':
            result=await job('create_hub_and_axis_v2','creo_execute_plan',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'operations':[
                  {'op':'sketch','label':'hub_profile','plane':'XZ','entities':[{'type':'circle','name':'hub','center':[0,0],'radius':8}]},
                  {'op':'extrude','label':'hub_extrude','sketch':'hub_profile','depth':8,'direction':'symmetric'},
                  {'op':'datum_axis','label':'propeller_axis','references':[{'kind':'datum_plane','axis':'x'},{'kind':'datum_plane','axis':'z'}]}],
                'assertions':{'require_solid':True}})
            first=next(f['id'] for f in result['result']['inspection']['features'] if f['name']=='BLADE_SECTION_1_PLANE')
            await job('reorder_axis','creo_reorder_features',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'features':['propeller_axis'],'before':first})
            await job('group_blade','creo_group_features',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'label':'blade_group','features':[f'blade_section_{i}' for i in range(1,6)]+['blade_blend'],'include_between':True})
            result=await job('pattern_blade','creo_axis_pattern',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'label':'two_blades','leader':'blade_group','axis':{'kind':'datum_axis_feature','label':'propeller_axis'},'count':2,'increment_deg':180})
            assert len([b for b in result['result']['inspection']['bodies'] if b['state']==4])==1
            original=state['initial_ids']['blade_blend']
            assert result['result']['aliases']['blade_blend']['feature_id']==original
            edited=await job('edit_patterned_airfoil','creo_set_airfoil_parameters',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'sketch':'blade_section_3','values':{'chord':34,'twist_deg':17}})
            assert edited['result']['aliases']['blade_blend']['feature_id']==original
            assert abs(result['result']['inspection']['volume_mm3']-edited['result']['inspection']['volume_mm3'])>1
            state['pattern_passed']=True;persist()
        elif stage=='body':
            result=await job('create_transform_cube_v3','creo_execute_plan',{'model_name':'mcp_body_'+state['run_id'],
                'operations':[{'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[10,6]}]},
                              {'op':'extrude','label':'block','sketch':'profile','depth':2}],
                'assertions':{'require_solid':True,'volume_mm3':120}})
            body=next(b['id'] for b in result['result']['inspection']['bodies'] if b['state']==4)
            result=await job('move_rotate_body_v3','creo_transform_geometry',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'label':'position','references':[{'kind':'body','id':body}],
                'translation':[10,20,30],'rotation':[0,0,90]})
            bounds=next(b['bbox'] for b in result['result']['inspection']['bodies'] if b['state']==4)
            assert max(abs(bounds[i][j]-[[4,20,30],[10,30,32]][i][j]) for i in range(2) for j in range(3))<1e-5,bounds
            fid=result['result']['aliases']['position']['feature_id']
            result=await job('edit_body_placement_v3','creo_set_geometry_transform',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'feature':'position','translation':[12,20,30],'rotation':[0,0,0]})
            assert result['result']['aliases']['position']['feature_id']==fid
            bounds=next(b['bbox'] for b in result['result']['inspection']['bodies'] if b['state']==4)
            assert max(abs(bounds[i][j]-[[12,20,30],[22,26,32]][i][j]) for i in range(2) for j in range(3))<1e-5,bounds
            state['body_transform_passed']=True;persist()
        elif stage=='quilt':
            await job('create_quilt','creo_execute_plan',{'model_name':'mcp_quilt_'+state['run_id'],'operations':[
                {'op':'sketch','label':'profile','entities':[{'type':'rectangle','name':'box','min':[0,0],'max':[20,10]}]},
                {'op':'surface_fill','label':'fill','sketch':'profile'}]})
            await job('move_rotate_quilt_v2','creo_transform_geometry',{'model_id':state['model_id'],
                'expected_revision':state['revision'],'label':'position','references':[{'kind':'quilt_feature','label':'fill'}],
                'translation':[0,3,8],'rotation':[90,0,0]})
            result=await job('thicken_moved_quilt','creo_thicken',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'label':'thickness','reference':{'kind':'quilt_feature','label':'position'},'thickness':2,'side':'symmetric'})
            bounds=next(b['bbox'] for b in result['result']['inspection']['bodies'] if b['state']==4)
            assert max(abs(bounds[i][j]-[[0,2,8],[20,4,18]][i][j]) for i in range(2) for j in range(3))<1e-5,bounds
            result=await job('edit_quilt_placement','creo_set_geometry_transform',{'model_id':state['model_id'],'expected_revision':state['revision'],
                'feature':'position','translation':[5,3,8],'rotation':[90,0,0]})
            bounds=next(b['bbox'] for b in result['result']['inspection']['bodies'] if b['state']==4)
            assert max(abs(bounds[i][j]-[[5,2,8],[25,4,18]][i][j]) for i in range(2) for j in range(3))<1e-5,bounds
            state['quilt_transform_passed']=True;persist()
    print('PASS:',stage,flush=True)
if __name__=='__main__':
    for stage in (['airfoil','export','pattern','body','quilt'] if args.stage=='all' else [args.stage]):
        asyncio.run(main(stage))
    print('Private full report:',STATE)



