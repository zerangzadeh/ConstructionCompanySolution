"""B07 final boundary, acceptance evidence and prior-work preservation checks."""
import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]

def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8-sig'))

def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def outside(source,name):
    tree=ast.parse(source)
    target='RecurringExpenseTemplateForm' if name=='forms' else 'recurrence_list'
    tree.body=[n for n in tree.body if not isinstance(n,(ast.ClassDef,ast.FunctionDef)) or n.name!=target]
    if name=='views':
        for n in tree.body:
            if isinstance(n,ast.ImportFrom) and n.module=='apps.organizations.authorization':
                n.names=[a for a in n.names if a.name!='scope_queryset']
    return ast.dump(tree,include_attributes=False)

def results(file):
    rows=[]
    for c in ET.parse(OUT/file).findall('.//testcase'):
        failure=c.find('failure');assert c.find('error') is None
        rows.append((c.get('classname'),c.get('name'),None if failure is None else failure.get('message')))
    return rows

def main():
    entry=read('ENTRY_BASELINE.json')
    changes=[p for p,h in entry['hashes'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert set(changes)=={'apps/expenses/forms.py','apps/expenses/views.py','docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml'},changes
    for name in ('forms','views'):
        assert outside((ROOT/f'apps/expenses/{name}.py').read_text(encoding='utf-8'),name)==outside((OUT/f'{name}_entry.txt').read_text(encoding='utf-8'),name)
    register=(ROOT/'docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml').read_bytes()
    original=(OUT/'register_entry.txt').read_bytes()
    pattern=rb'- finding_id: UIUX-F-120\r?\n.*?(?=- finding_id: UIUX-F-121\r?\n)'
    assert re.sub(pattern,b'',register,flags=re.S)==re.sub(pattern,b'',original,flags=re.S)
    block=re.search(pattern,register,re.S).group()
    for t in (b'finding_status: RESOLVED',b'status: RUNTIME_VERIFIED_RESOLVED',b'decision: BATCH_07_RUNTIME_VERIFIED_RESOLVED'):
        assert t in block
    try:
        import yaml
        parsed=yaml.safe_load(register)
        save('YAML_VALIDATION.json',{'passed':bool(parsed),'parser':'PyYAML'})
    except ImportError:
        assert read('YAML_VALIDATION.json')['passed']
    focused=ET.parse(OUT/'focused.xml')
    assert not focused.findall('.//failure') and not focused.findall('.//error')
    assert '13 passed, 44 subtests passed' in (OUT/'focused.txt').read_text()
    assert results('baseline_regression.xml')==results('regression.xml')
    attribution=read('REGRESSION_ATTRIBUTION.json')
    assert attribution['baseline_identical_to_current'] and len(attribution['failures'])==15 and not attribution['new_failures']
    assert '15 failed, 59 passed, 106 subtests passed' in (OUT/'regression.txt').read_text()
    for file,token in (('django_check.txt','no issues'),('migration_check.txt','No changes detected'),('ruff.txt','All checks passed'),('ruff_format.txt','3 files already formatted')):
        assert token in (OUT/file).read_text(encoding='utf-8'),file
    http=read('RUNTIME_HTTP.json')
    assert len(http)==33 and read('HTTP_SUMMARY.json')['all_pass']
    assert all(r['business_and_success_audit_unchanged'] and r['real_authentication_csrf'] and not r['forbidden_metadata'] for r in http)
    direct=read('DIRECT_SERVICE.json')
    assert len(direct)==16 and all(r['denied'] and r['mutations']==0 for r in direct)
    fixtures=read('FIXTURES.json')['templates']
    assert len(fixtures)==5 and all(f['qualifying'] and f['created'] for f in fixtures)
    browser=read('RUNTIME_BROWSER.json')
    assert len(browser)==5
    comparisons=[]
    for r in browser:
        allowed='ABCD' if r['label']=='organization GET' else '' if r['label']=='site-only GET' else 'AB'
        actual={v['value'] for v in r['options'] if v['value']}
        assert actual=={f['project'] for f in fixtures if f['key'] in allowed}
        for f in fixtures:
            action='/expenses/recurrences/'+f['id']+'/propose/'
            assert (action in r['actions'])==(f['key'] in allowed)
            assert (f['description'] in r['bodyText'])==(f['key'] in allowed)
        control=next(t for t in http if t['case']=='GET' and t['actor']==('uiux.persona.tenant-admin' if allowed=='ABCD' else 'uiux.reference.batch03.site-only' if not allowed else 'uiux.persona.project-manager'))
        assert [{k:o[k] for k in ('value','label')} for o in r['options']]==control['options']
        comparisons.append(r['label'])
    invalid=next(r for r in browser if r['label']=='limited invalid date POST')
    assert 'End date cannot precede start date.' in invalid['errors']
    assert next(o for o in invalid['options'] if o['selected'])['value']==next(f['project'] for f in fixtures if f['key']=='B')
    for name in ('browser_limited_get.png','browser_invalid_post.png','browser_query_get.png','browser_organization.png','browser_site_only.png'):
        assert (OUT/name).stat().st_size>1000
    integrity=read('RUNTIME_INTEGRITY.json')
    assert integrity['tables']==519 and integrity['preexisting_business_rows_changed']==[]
    assert set(integrity['runtime_deltas'])<={'sessions.Session'}
    assert not integrity['unauthorized_mutations'] and not integrity['runtime_success_audits']
    assert integrity['authority_unchanged'] and integrity['authority_fingerprint_before']==integrity['authority_fingerprint_after']
    assert integrity['preparation_additions']=={'expenses.RecurringExpenseTemplate':5}
    assert all(r['predates_server'] for r in read('SERVER_IDENTITY.json')['source_files'])
    cleanup=read('SERVER_CLEANUP.json')
    assert cleanup['identity_verified'] and cleanup['stopped'] and not cleanup['listener_remaining']
    check=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    (OUT/'whitespace.txt').write_text(check.stdout+check.stderr,encoding='utf-8')
    assert check.returncode==0
    report=OUT.parent/'UIUX_F111_BATCH_07_REMEDIATION_REPORT.md'
    for link in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):
        target=report.parent/link.split('#')[0]
        assert target.exists() or target==OUT/'VERIFICATION.json',link
    for p in (report,ROOT/'tests/test_uiux_f111_pattern_recurrence_scope.py',*OUT.glob('*.py')):
        assert all(line==line.rstrip() for line in p.read_text(encoding='utf-8-sig').splitlines()),p
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==entry['head']
    save('VERIFICATION.json',{'decision':'BATCH_07_RUNTIME_VERIFIED_RESOLVED','finding':'UIUX-F-120','status':'RUNTIME_VERIFIED_RESOLVED','baseline_files_compared':len(entry['hashes']),'changed_existing_files':changes,'non_target_source_AST_preserved':True,'all_other_finding_blocks_byte_preserved':True,'prior_batches_01_through_06_preserved':True,'batch_08_09_unchanged_not_executed':True,'wave_c':'NOT_STARTED','focused':'13 tests +44 subtests PASS','regression':'59 tests +106 subtests PASS;15 exact baseline setup failures;zero new failures','http_observations':33,'direct_denials':16,'browser_comparisons':comparisons,'tables_integrity':519,'authority_unchanged':True,'migration':'NO','git_add_commit_push':'NOT_EXECUTED','production_actions':'NONE','cep_078_079':'NOT_EXECUTED'})
    save('INDEX.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in {'INDEX.json','verification.txt'}})
    print('PASS: B07 closed; 5,249 entry hashes and prior batches preserved; 33 HTTP/16 direct/5 browser controls; bounded source and F-120 only')

if __name__=='__main__':main()
