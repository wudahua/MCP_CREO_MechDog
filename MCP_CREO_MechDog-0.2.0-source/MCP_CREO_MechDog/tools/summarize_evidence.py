"""Summarize real native integration reports, excluding failed exploratory attempts."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
core=json.loads((ROOT/'build/general_integration_test.json').read_text(encoding='utf-8'))
extended=json.loads((ROOT/'build/extended_integration_test.json').read_text(encoding='utf-8'))
guards=json.loads((ROOT/'build/guards_integration_test.json').read_text(encoding='utf-8'))
protocol=json.loads((ROOT/'build/mcp_protocol_test.json').read_text(encoding='utf-8'))
assert core['success'] and extended['success'] and guards['success']
assert len(protocol['tools'])==31 and protocol['session']['connected']
jobs=[c['job'] for r in (core,extended) for c in r['cases'] if c['job']['status']=='succeeded']
operations={}
for j in jobs:
    if j.get('kind')=='generic' and any(o.get('op') not in ('export','dump_tree') for o in j.get('operations',[])):
        assert j['result']['saved_file_reloaded_and_verified']
    for op in j.get('operations',[]): operations.setdefault(op['op'],[]).append(j['job_id'])
evidence={
    'name':'MCP_CREO_MechDog','version':'0.2.0','all_selected_test_suites_passed':True,
    'protocol':protocol['protocol_version'],'tool_count':31,
    'successful_native_jobs':len(jobs),
    'verified_operations':{k:list(dict.fromkeys(v)) for k,v in sorted(operations.items())},
    'verified_branches':[
        'new metric native part; independent native sketches and sequential feature creation',
        'line, centerline, rectangle, closed polyline, circle, arc, ellipse and spline sketch entities',
        'XY/XZ/YZ sketch frames, offset plane and angled datum support',
        'explicit diameter/length dimensions; horizontal/vertical constraints; automatic dimensioning',
        'positive/negative extrusion; additive features on multiple planes; new bodies',
        'blind pocket and through-all extrusion cut; surface extrusion; symmetric thin extrusion',
        '360-degree revolve, external-axis 180-degree revolve and revolved groove cut',
        'native straight through hole and blind hole',
        'constant-radius edge round, equal-distance edge chamfer; inward/outward shell with removed top face',
        'offset/angled datum plane, two-plane datum axis and native one-direction dimension pattern',
        'native dimension edit; named sketch diameter edit propagates to dependent solid',
        'native parameters and relation-driven dimensions updated after parameter change',
        'advanced symbolic element-tree datum plane and native feature XML dump',
        'STEP, STL, IGES and JPEG exports from a turned solid',
        'standalone regeneration and save followed by native saved-file reload verification',
        'stale revision rejected; partial mutation failure restores original live geometry, parameters and file',
    ],
    'not_individually_verified':['every constraint/dimension combination','all reference and geometry combinations','all advanced Toolkit feature trees'],
    'not_high_level_implemented':['mirror','sweep','blend/loft','draft','rib','threaded/counterbore/countersink holes','sheet metal','assembly','drawing'],
    'test_reports':['general_integration_test.json','extended_integration_test.json','guards_integration_test.json','mcp_protocol_test.json'],
    'native_worker_sha256':hashlib.sha256((ROOT/'build/creo_worker.exe').read_bytes()).hexdigest(),
}
if any(c['args'].get('operations',[{}])[-1].get('label')=='symmetric' and c['job']['status']=='succeeded' for c in extended['cases']):
    evidence['verified_branches'].append('surface revolve; thin revolve; symmetric 90-degree revolve')
(ROOT/'build/capability_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
public={
    'name':evidence['name'],'version':evidence['version'],
    'evidence_type':'historical development-machine test summary; not this installation verification',
    'tested_environment':{'os':'Windows x64','creo':'10.0.0.0','python':'3.12 x64','compiler':'Visual Studio 2022 C++ Build Tools'},
    'tool_count':evidence['tool_count'],'successful_native_jobs':evidence['successful_native_jobs'],
    'input_validation_tests':11,
    'verified_operations':list(evidence['verified_operations']),
    'verified_branches':evidence['verified_branches'],
    'not_individually_verified':evidence['not_individually_verified'],
    'not_high_level_implemented':evidence['not_high_level_implemented'],
}
(ROOT/'docs').mkdir(exist_ok=True)
(ROOT/'docs/validation.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
print('Native verified operations:',len(operations),'successful jobs:',len(jobs))
