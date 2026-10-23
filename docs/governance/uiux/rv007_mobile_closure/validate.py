import json, hashlib, re, subprocess, sys
from pathlib import Path
sys.path.append(str(Path("C:/Users/azera/AppData/Local/Programs/Python/Python311/Lib/site-packages")))
import yaml
root=Path.cwd()
out=root/'docs/governance/uiux/rv007_mobile_closure'
prior=out.parent/'rv007_controlled_time'
results=out.parent/'UIUX_RUNTIME_VALIDATION_RESULTS.yaml'
text=results.read_text(encoding='utf-8')
old='Wave A. Current results are under targeted_revalidation. Wave C partial execution is appended under wave_c; Waves D-E not executed.'
new='Wave A. Current targeted results are under targeted_revalidation. Current Wave C closure is wave_c_final_browser_closure with explicit baseline debt; earlier Wave C sections are historical. Waves D-E not executed.'
assert old in text
results.write_text(text.replace(old,new,1),encoding='utf-8')
class UniqueLoader(yaml.SafeLoader):
    pass
def unique_map(loader,node,deep=False):
    result={}
    for key,value in node.value:
        name=loader.construct_object(key,deep=deep)
        if name in result:
            raise AssertionError('Duplicate YAML key: '+str(name))
        result[name]=loader.construct_object(value,deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,unique_map)
for name in ('UIUX_RUNTIME_VALIDATION_RESULTS.yaml','UIUX_FINDINGS_REGISTER.yaml'):
    loaded=yaml.load((out.parent/name).read_text(encoding='utf-8'),Loader=UniqueLoader)
    key='wave_c_final_browser_closure' if 'RESULTS' in name else 'wave_c_final_browser_reconciliation'
    assert loaded[key]['decision']=='WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT'
    assert loaded[key]['RV-007']=='PASS'
missing=[]
for file in (out/'COMPLETION_REPORT.md',out.parent/'UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md'):
    for target in re.findall(r'\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
        if not re.match(r'^[a-z]+:',target) and not target.startswith('#'):
            if not (file.parent/target.split('#')[0]).exists(): missing.append((str(file),target))
assert not missing,missing
matrix=json.loads((out/'WAVE_C_MATRIX.json').read_text())
assert matrix['pass_count']==12 and matrix['wave_closed']
for row in matrix['scenario_results']:
    assert (out/row['evidence']).exists(),row
entry=json.loads((out/'ENTRY.json').read_text())
allowed={f'docs/governance/uiux/{name}' for name in ('UIUX_RUNTIME_VALIDATION_RESULTS.yaml','UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md','UIUX_FINDINGS_REGISTER.yaml')}
changed=[p for p,sha in entry['hashes'].items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=sha]
assert set(changed)==allowed,changed
assert hashlib.sha256((root/'.git/index').read_bytes()).hexdigest()==entry['index_sha256']
for path,sha in json.loads((prior/'ARTIFACTS.json').read_text()).items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
sys.path.insert(0,str(prior))
from support import guard,snapshot
from django.db import connection,transaction
guard()
with transaction.atomic():
    with connection.cursor() as cursor: cursor.execute('SET TRANSACTION READ ONLY')
    assert snapshot()==json.loads((out/'DATA_BEFORE.json').read_text())
validation={'yaml_unique_keys':'PASS','report_links':'PASS','matrix_evidence_links':'PASS','12_scenario_dispositions':'PASS','only_three_canonical_documents_changed':'PASS','prior_artifact_hashes':'PASS','source_and_index_preserved':'PASS','business_snapshot_unchanged':'PASS','changed_entry_files':changed,'product_files_modified':[],'migration_commands_run':[],'test_rerun':'NOT_REQUIRED; browser-only evidence/document closure with no material drift','next_action':'STOP'}
(out/'DOCUMENT_VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
artifacts={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='ARTIFACTS.json'}
(out/'ARTIFACTS.json').write_text(json.dumps(artifacts,indent=2)+'\n',encoding='utf-8')
print('Evidence/document validation PASS; prior artifacts/source/business data preserved; 12/12 scenarios PASS; 18 baseline failures retained; STOP')

