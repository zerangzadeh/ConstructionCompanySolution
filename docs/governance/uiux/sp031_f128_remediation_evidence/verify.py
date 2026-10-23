"""Exact F128 boundary, evidence gates, YAML preservation and bounded closure."""

import ast
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
REGISTER=ROOT/'docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml'


def read(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
def save(name,data): (OUT/name).write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def imports(source):
    return {(n.module,a.name,a.asname) for n in ast.parse(source).body if isinstance(n,ast.ImportFrom) for a in n.names}


def outside(source,kind):
    tree=ast.parse(source)
    if kind=='forms':
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='EmployeeTrainingRecordForm')
        cls.body=[n for n in cls.body if not isinstance(n,ast.FunctionDef) or n.name!='__init__']
    else:
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='workforce_training_record_create')
        assert isinstance(fn.body[0],ast.Assign) and fn.body[0].targets[0].id=='form'
        fn.body[0]=ast.Pass()
    tree.body=[n for n in tree.body if not isinstance(n,(ast.ImportFrom,ast.Import))]
    return ast.dump(tree,include_attributes=False)


def source():
    entry=read('ENTRY_BASELINE.json')
    permitted={'apps/workforce/forms.py','apps/workforce/views.py','docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml'}
    changes=[p for p,h in entry['hashes'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert set(changes)<=permitted,changes
    for kind in ('forms','views'):
        original=(OUT/f'workforce_{kind}_entry.txt').read_text(encoding='utf-8')
        current=(ROOT/f'apps/workforce/{kind}.py').read_text(encoding='utf-8')
        assert outside(original,kind)==outside(current,kind),kind
        added=imports(current)-imports(original)
        removed=imports(original)-imports(current)
        assert not removed
        assert added==({('django.db.models','Q',None),('apps.organizations.authorization','has_business_permission',None),('apps.organizations.models','BusinessPermissionCode',None)} if kind=='forms' else set()),added
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==entry['git']['rev-parse HEAD']
    if not (OUT/'UIUX_FINDINGS_REGISTER_entry.yaml').exists():
        assert hashlib.sha256(REGISTER.read_bytes()).hexdigest()==entry['hashes']['docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml']
        (OUT/'UIUX_FINDINGS_REGISTER_entry.yaml').write_bytes(REGISTER.read_bytes())
    save('SOURCE_BOUNDARY.json',dict(status='PASS',existing_files_compared=len(entry['hashes']),changed_existing_files=changes,allowed_product_seams=['EmployeeTrainingRecordForm.__init__ + three imports','workforce_training_record_create first form assignment'],all_other_product_sources_and_historical_evidence='BYTE_PRESERVED',f111_family='F111_PATTERN_FAMILY_CLOSED_UNCHANGED',migration='NO',git_writes='NONE'))
    print('Source boundary PASS:',len(entry['hashes']),'existing fingerprints; only permitted form constructor/view assignment/imports')


def outcomes(name):
    root=ET.parse(OUT/name).getroot()
    result={}
    for case in root.iter('testcase'):
        failure=case.find('failure')
        error=case.find('error')
        skipped=case.find('skipped')
        result[(case.get('classname'),case.get('name'))]=dict(status='failure' if failure is not None else 'error' if error is not None else 'skipped' if skipped is not None else 'pass',message=(failure if failure is not None else error).get('message') if failure is not None or error is not None else None)
    return result


def regression():
    current=outcomes('regression.xml'); baseline=outcomes('baseline_regression.xml')
    assert current==baseline,[(k,current.get(k),baseline.get(k)) for k in current.keys()|baseline.keys() if current.get(k)!=baseline.get(k)]
    failed={str(k):v for k,v in current.items() if v['status'] in ('failure','error')}
    save('REGRESSION_ATTRIBUTION.json',dict(status='PASS_ZERO_NEW_REGRESSIONS',tests=len(current),passed=sum(v['status']=='pass' for v in current.values()),baseline_failures=failed,new_failures=[],exact_dirty_entry_replay=True,scope='Workforce tests.py, P7 foundation, existing TrainingRequirement project selector matrix',product_sources_swapped=False))
    print('Regression attribution PASS:',len(current),'identical current/entry outcomes;',len(failed),'unchanged baseline failures')


def close():
    source()
    focused=outcomes('focused.xml')
    assert len(focused)==19 and all(o['status']=='pass' for o in focused.values())
    attribution=read('REGRESSION_ATTRIBUTION.json')
    assert attribution['status']=='PASS_ZERO_NEW_REGRESSIONS' and not attribution['new_failures']
    http=read('HTTP_SUMMARY.json'); direct=read('DIRECT_SERVICE.json'); browser=read('BROWSER.json'); integrity=read('INTEGRITY.json')
    assert http['all_pass'] and http['observations']==40 and http['unauthorized_writes']==http['protected_metadata_leaks']==0
    assert len(direct)==18 and all(o['persisted_delta']==0 for o in direct)
    assert len(browser)==7 and sum(bool(o.get('serverPost')) for o in browser)==3
    assert browser[-1]['success'] and browser[-1]['successText']
    values=read('BROWSER_INPUT.json')['requirements']
    for o in browser:
        if 'options' not in o: continue
        expected=set(read('BROWSER_INPUT.json')['allowed'][o['actor']])
        observed={v['value'] for v in o['options'] if v['value']}
        assert observed=={values[k] for k in expected},o
    assert integrity['unauthorized_training_records']==integrity['unauthorized_success_audits']==0
    assert not integrity['preexisting_rows_changed']
    assert integrity['authority_before']==integrity['authority_after']
    assert len(integrity['authorized_training_records'])==len(integrity['authorized_success_audits'])==3
    checks=read('CHECKS.json')
    assert all(v['exit_code']==0 for v in checks.values())
    report=ROOT/'docs/governance/uiux/UIUX_SP031_F128_REMEDIATION_REPORT.md'
    assert report.exists()
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
        if target=='sp031_f128_remediation_evidence/VERIFICATION.json': continue
        assert (report.parent/target).exists(),target
    original=(OUT/'UIUX_FINDINGS_REGISTER_entry.yaml').read_bytes()
    before=yaml.safe_load(original)
    current=REGISTER.read_bytes()
    if current==original:
        text=current.decode('utf-8')
        start=text.index('- finding_id: UIUX-F-128\n'); end=text.index('\nruntime_wave_a:',start)
        block=text[start:end]
        block=block.replace('  finding_status: OPEN','  finding_status: RESOLVED',1).replace('  status: RUNTIME_CONFIRMED','  status: RUNTIME_VERIFIED_RESOLVED',1).replace('  runtime_status: RUNTIME_CONFIRMED','  runtime_status: RUNTIME_VERIFIED_RESOLVED',1).replace('  runtime_classification: FAIL_SECURITY_SCOPE','  runtime_classification: PASS_REQUIRED_CONTROLS',1).replace('  remediation_status: NOT_STARTED','  remediation_status: RUNTIME_VERIFIED_RESOLVED',1)
        block+='''
  sp031_bounded_remediation:
    date: '2026-10-22'
    status: RUNTIME_VERIFIED_RESOLVED
    report: UIUX_SP031_F128_REMEDIATION_REPORT.md
    evidence: sp031_f128_remediation_evidence/
    focused: 19 tests PASS
    regression: Exact current and dirty-entry outcomes; no new regressions; see REGRESSION_ATTRIBUTION.json
    runtime_http: 40 observations PASS; two authorized valid submissions
    runtime_browser: Seven observations; three real server POSTs including one authorized success
    runtime_integrity: 519 tables; exactly three authorized records and audits plus sessions; no unauthorized mutation
    semantics: Existing projectless catalogue visibility and stricter write gate preserved
    migration: NO
    temporary_authority: NONE
    f111_family: F111_PATTERN_FAMILY_CLOSED_UNCHANGED
    wave_c: NOT_STARTED
    git_writes: NONE
'''
        text=text[:start]+block+text[end:]
        # Historical SP031 diagnosis remains intact; append current remediation state.
        text+='''
sp031_finding_remediation:
  finding_id: UIUX-F-128
  status: RUNTIME_VERIFIED_RESOLVED
  historical_diagnosis: AFFECTED_CONFIRMED
  report: UIUX_SP031_F128_REMEDIATION_REPORT.md
  evidence: sp031_f128_remediation_evidence/
  f111_family: F111_PATTERN_FAMILY_CLOSED_UNCHANGED
  wave_c: NOT_STARTED
  production: NO_ACTION
  cep_078_079: NOT_EXECUTED
  git_add_commit_push: NOT_EXECUTED
'''
        REGISTER.write_bytes(text.encode('utf-8'))
    after=yaml.safe_load(REGISTER.read_bytes())
    assert before['findings'][:-1]==after['findings'][:-1]
    assert after['findings'][-1]['finding_id']=='UIUX-F-128' and after['findings'][-1]['status']=='RUNTIME_VERIFIED_RESOLVED'
    for key in before:
        if key!='findings': assert after[key]==before[key],key
    assert len(after['findings'])==128
    assert after['findings'][-1]['sweep_classification']=='AFFECTED_CONFIRMED'
    save('VERIFICATION.json',dict(status='PASS',finding='UIUX-F-128',finding_status='RUNTIME_VERIFIED_RESOLVED',focused_tests=19,regression=attribution['status'],historical_finding_objects_preserved=127,f111_pattern_family='F111_PATTERN_FAMILY_CLOSED',http_observations=40,direct_service_outcomes=18,browser_observations=7,browser_server_posts=3,integrity_tables=integrity['tables'],authorized_runtime_records_and_audits=3,unauthorized_writes=0,temporary_authority='NONE',migration='NO',wave_c='NOT_STARTED',cep_078_079='NOT_EXECUTED',production='NO_ACTION',git_writes='NONE'))
    print('UIUX-F-128 closure PASS: RUNTIME_VERIFIED_RESOLVED; F111 family and prior findings preserved')


if __name__=='__main__':
    {'source':source,'regression':regression,'close':close}[sys.argv[1]]()
