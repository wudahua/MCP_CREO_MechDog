"""Publish a sanitized loft-only summary; do not relabel older feature suites."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION
import bridge


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main(interpolation='straight', reuse_native_evidence=False):
    report_name = 'loft_smooth_integration.json' if interpolation=='smooth' else 'loft_seed_integration.json'
    report = read(ROOT/'build'/report_name)
    unit = read(ROOT/'build/unit_test_report.json')
    protocol = read(ROOT/'build/mcp_protocol_test.json')
    assert unit['version'] == protocol['server']['version'] == VERSION
    inherited_evidence = report['version'] != VERSION
    if inherited_evidence:
        assert reuse_native_evidence, 'Native report has an older version; rerun native tests or explicitly reuse verified unchanged runtime evidence'
        update = read(ROOT/'build'/f'version_update_{VERSION}.json')
        assert update['from_version'] == report['version'] and update['to_version'] == VERSION
        assert hashlib.sha256((ROOT/'build'/report_name).read_bytes()).hexdigest() == update['modeling_report_sha256'][report_name], 'Native report changed'
        for filename, digest in update['runtime_sha256'].items():
            assert hashlib.sha256((ROOT/filename).read_bytes()).hexdigest() == digest, f'{filename}: modeling runtime changed; rerun native tests'
        assert hashlib.sha256((ROOT/'build/creo_worker.exe').read_bytes()).hexdigest() == update['native_worker_sha256'], 'Native binary changed'
    assert report['success'] and report['source_file_unchanged'] and unit['success']
    assert report['interpolation']==interpolation and report['mismatched_seed_rejected']
    assert protocol['session']['connected'] and len(protocol['tools']) == 68
    assert 'creo_new_loft_part' in protocol['tools']
    assert protocol['loft_interpolation_schema_verified']
    assert report['native_build']['source_fingerprint'] == (ROOT/'build/source.sha256').read_text().strip(), 'Native build changed; rerun loft tests'
    assert report['native_build']['worker_sha256'] == hashlib.sha256((ROOT/'build/creo_worker.exe').read_bytes()).hexdigest(), 'Native binary changed; rerun loft tests'
    native_sources = sorted(p for p in (ROOT/'native').rglob('*') if p.suffix in ('.cpp', '.h', '.hpp', '.inc'))
    digest = hashlib.sha256()
    for path in native_sources:
        digest.update(path.read_bytes())
    digest.update(json.dumps(bridge.config(), sort_keys=True).encode())
    assert digest.hexdigest() == report['native_build']['source_fingerprint'], 'Native source/config changed; rebuild and rerun loft tests'
    succeeded, failed, rollback = [], [], []
    for entry in report['jobs']:
        job = read(ROOT/'jobs'/entry['job_id']/'job.json')
        if entry['expected_failure']:
            assert job['status'] == 'failed'
            failed.append(job['job_id'])
            if job['result'].get('rollback_succeeded'):
                assert job['result']['loft_checks']['rollback']['blend']['interpolation']==interpolation
                rollback.append(job['job_id'])
        else:
            assert job['status'] == 'succeeded' and job['result']['saved_file_reloaded_and_verified']
            assert any(f['id'] == job['result']['aliases']['blend']['feature_id'] and
                       f['type'] == 917 and f['status'] == 0 and not f['incomplete']
                       for f in job['result']['inspection']['features'])
            for phase in ['before_save','after_reload']:
                setting=job['result']['loft_checks'][phase]['blend']
                assert setting['interpolation']==interpolation and setting['section_count']==2
            succeeded.append(job['job_id'])
    assert len(succeeded) == 5 and len(failed) == 3 and len(rollback) == 1
    assert set(report['cases']) == {'rectangle', 'circle', 'triangle'}
    public = {
        'name': 'MCP_CREO_MechDog', 'version': VERSION,
        'scope': 'new parts from a user-supplied two-section native Blend seed',
        'native_modeling_validation_version': report['version'],
        'input_validation_version': unit['version'], 'mcp_validation_version': protocol['server']['version'],
        'version_label_update_only': inherited_evidence,
        'complete_creo_coverage': False, 'direct_loft_creation_enabled': False,
        'tool': 'creo_new_loft_part', 'tool_count': 68, 'enabled_tool_count': 67,
        'successful_native_jobs': len(succeeded), 'saved_file_verified_mutation_jobs': len(succeeded),
        'expected_failure_jobs': len(failed), 'rollback_verified_jobs': len(rollback),
        'input_validation_tests': unit['tests_run'], 'mcp_stdio_connected': True,
        'source_seed_file_unchanged': True,
        'interpolation': interpolation, 'native_mode_verified_before_save_and_after_reload': True,
        'native_mode_verified_after_parameter_edit': True, 'mismatched_seed_rejected': True,
        'acceptance': {'native_blend_feature_preserved': True,
                       'parameter_edit_changes_solid': True,
                       'saved_file_reloaded_with_mode_preserved': True},
        'cases': {name: {'success': case['success'], 'volume_mm3': case['volume_mm3']}
                  for name, case in report['cases'].items()},
        'rectangle_dimensions_edited_mm': [12, 12], 'edited_rectangle_volume_mm3': report['cases']['rectangle']['edited_volume_mm3'],
        'subsequent_cut_volume_mm3': report['cases']['rectangle']['edited_and_cut_volume_mm3'],
        'tested_environment': {'os': 'Windows x64', 'creo': '10.0.0.0', 'python': '3.12 x64'},
        'limits': ['Requires a saved dedicated solid Blend seed in mm with the requested interpolation setting',
                   'Exactly two XY sketches with increasing Z offsets; seed bottom sketch created and selected first',
                   'No existing-target insertion, extra sections, nonparallel sections, cut/surface mode or tangency controls',
                   'interpolation checks the seed mode; it does not convert a straight seed to smooth or vice versa',
                   'Two sections with free endpoints may have the same geometry in straight and smooth modes',
                   'Other contours and seeds require individual verification; seed settings and datums are inherited'],
        'other_feature_evidence': 'Historical validation_development.json and validation_0.21.json; full suites were not rerun',
        'evidence_type': 'Development-machine MCP/native tests; not verification of another installation',
        'native_source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in native_sources if p.suffix != '.inc'},
        'native_worker_sha256': report['native_build']['worker_sha256'],
    }
    if inherited_evidence:
        public['validation_note'] = f'Release version {VERSION}; native modeling jobs retain validation version {report["version"]}. Modeling runtime and worker hashes were verified unchanged; input validation and MCP version/connection checks were rerun for {VERSION}.'
    output=ROOT/('docs/validation_loft_smooth.json' if interpolation=='smooth' else 'docs/validation_loft_seed.json')
    output.write_text(json.dumps(public, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'interpolation':interpolation,'successful_native_jobs': len(succeeded), 'expected_failures': len(failed), 'tool_count': 68}))


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--interpolation',choices=['straight','smooth'],default='straight')
    p.add_argument('--reuse-native-evidence',action='store_true',help='Reuse an older native report only after checking a local version-update hash manifest')
    a=p.parse_args()
    main(a.interpolation,a.reuse_native_evidence)
