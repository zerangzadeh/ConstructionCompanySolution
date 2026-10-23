"""Check final canonical appends, historical preservation, and local links."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
UI=OUT.parent
sys.path.insert(0,str(Path(os.environ['TEMP'])/'bonira-wave-c-tools'))
import yaml

def normalized(obj):return json.loads(json.dumps(obj,default=str))

def main():
    register=yaml.safe_load((UI/'UIUX_FINDINGS_REGISTER.yaml').read_text(encoding='utf-8'))
    entry=json.loads((OUT/'FINDINGS_ENTRY_OBJECTS.json').read_text(encoding='utf-8'))
    findings=register['findings']
    assert len(findings)==len({f['finding_id'] for f in findings})==130
    expected=json.loads((OUT/'DOCUMENTS_WRITTEN.json').read_text())['resolved_existing']
    for prior,current in zip(entry,findings[:128],strict=True):
        now=normalized(current)
        if current['finding_id'] in expected:
            assert now.pop('wave_c_retest')['status']=='RUNTIME_VERIFIED_RESOLVED'
        assert prior==now,current['finding_id']
    assert all(f['runtime_status']=='RUNTIME_VERIFIED_RESOLVED' for f in findings[128:])
    results=yaml.safe_load((UI/'UIUX_RUNTIME_VALIDATION_RESULTS.yaml').read_text(encoding='utf-8'))
    wave=results['wave_c']
    assert wave['decision']=='WAVE_C_BLOCKED' and not wave['wave_closed']
    matrix=yaml.safe_load((UI/'UIUX_RUNTIME_VALIDATION_MATRIX.yaml').read_text(encoding='utf-8'))
    assert len(wave['scenario_results'])==12
    assert len({r['scenario_id'] for r in wave['scenario_results']})==12
    assert len({r['evidence_id'] for r in wave['scenario_results']})==12
    for record in wave['scenario_results']:
        canonical=next(s for s in matrix['scenarios'] if s['scenario_id']==record['scenario_id'])
        assert record['surfaces']==canonical['surfaces']
        assert record['expected_result']==canonical['validate']
        assert record['persona']['persona_ids']==canonical['persona_ids']
        assert record['result'] and record['actual_result']
    yaml.safe_load((UI/'UIUX_ROOT_PATTERN_IMPACT_MAP.yaml').read_text(encoding='utf-8'))
    report=UI/'UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md'
    broken=[]
    for link in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
        if '://' in link:continue
        if not (report.parent/unquote(link.split('#')[0])).exists():broken.append(link)
    assert not broken,broken
    before=json.loads((OUT/'FILES_BEFORE.json').read_text())
    for protected in ('CEP_EXECUTION_REGISTRY.yaml','ROADMAP.md','Agents.md'):
        assert hashlib.sha256((ROOT/protected).read_bytes()).hexdigest()==before[protected]
    baseline=json.loads((OUT/'ENTRY.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    upstream=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=ROOT,text=True).strip()
    index=hashlib.sha256((ROOT/'.git/index').read_bytes()).hexdigest()
    assert head==baseline['head'] and upstream==baseline['upstream'] and index==baseline['index_sha256']
    data=dict(assertions='PASS',findings=130,unique_scenarios=12,prior_128_preserved_except_explicit_10_retests=True,accepted_F111_F128_unchanged=True,all_canonical_targets_copied_exactly=True,local_report_links='PASS',head=head,upstream=upstream,index_sha256=index,cep_registry_roadmap_agents_unchanged=True,decision=wave['decision'],full_wave_execution_complete=False,session_closed=True)
    (OUT/'FINAL_DOCUMENT_VALIDATION.json').write_text(json.dumps(data,indent=2)+'\n')
    print('Final documents PASS: 130 findings; all 12 canonical scenarios accounted; prior closures and Git/CEP boundaries preserved')

if __name__=='__main__':main()
