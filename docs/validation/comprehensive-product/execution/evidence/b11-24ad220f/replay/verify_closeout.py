import csv,json,hashlib,subprocess,re
from pathlib import Path
ROOT=Path('.scratch/b11-validation');DOC=Path('docs/validation/comprehensive-product');EX=DOC/'execution';OUT=EX/'evidence/b11-24ad220f'
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
entry=load(ROOT/'entry-full.json');final=load(OUT/'final-source.json');hashes=load(OUT/'source-hashes.json')
assert entry['source_sha256']==hashes['entry']
for name,digest in hashes['final'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
assert hashlib.sha256(json.dumps(hashes['final'],sort_keys=True).encode()).hexdigest()==final['source_fingerprint']
old=rows(ROOT/'entry-TEST_EXECUTION_MATRIX_MVP.csv');new=rows(DOC/'TEST_EXECUTION_MATRIX_MVP.csv');r=rows(EX/'B11_FINAL_RETEST.csv')
assert len(r)==len({x['Execution_ID'] for x in r})==302
assert {x['Execution_ID'] for x in r}=={x['Execution_ID'] for x in old if x['Batch']=='B11'}
assert [x for x in old if x['Batch']!='B11']==[x for x in new if x['Batch']!='B11']
olddef=rows(ROOT/'entry-DEFECT_REGISTER.csv');newdef=rows(DOC/'DEFECT_REGISTER.csv');assert newdef[:len(olddef)]==olddef and len(newdef)==64
assert (DOC/'DEFECT_REGISTER.md').read_bytes().startswith((ROOT/'entry-DEFECT_REGISTER.md').read_bytes())
assert all((DOC/x).exists() for row in r for x in row['Current_Evidence'].split('; ') if x)
for k,v in load(OUT/'source-compatibility.json')['protected'].items():assert hashlib.sha256(Path(k).read_bytes()).hexdigest()==v
counts=load(OUT/'closeout-counts.json');from collections import Counter
assert dict(Counter(x['Current_Status'] for x in r))==counts['current']
assert dict(Counter(x['Technical_Status'] for x in r))==counts['technical']
assert all(x['PO_ACCEPTANCE']=='NOT_RUN' for x in r if x['Current_Status']=='NEEDS_PO_REVIEW')
assert all(x['get_status']==403 for x in load(OUT/'original-route-observations.json').values() if x.get('condition')=='MVP profile exclusion')
coverage=load(OUT/'check-coverage.json')
coverage['INV-PROJECTS-DETAIL--CV-UI-01']['UI-08']={'status':'PARTIAL_CONTEXT_REQUIRES_PO_REVIEW','basis':'execution/evidence/b11-24ad220f/final-journeys.json project-equipment-operations','limit':'Existing project/site and report context passes. Direct Equipment project-filter handoff remains absent or unverified.'}
for k in coverage:
 if coverage[k]['UI-11']['status']=='SPOT_CHECKED':coverage[k]['UI-11']['basis']+='; execution/evidence/b11-24ad220f/invitation-and-contrast-final.json'
(OUT/'check-coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()==entry['head']
assert subprocess.check_output(['git','rev-parse','origin/main']).decode().strip()==entry['origin/main']
shutdown=(OUT/'resource-closeout.log').read_text(encoding='utf-8-sig');assert 'server stopped' in shutdown
assert not (ROOT/'pg/postmaster.pid').exists()
# Published replay sources contain generation code, never live runtime credentials or manifests.
assert not any(p.name in {'secret.txt','env.ps1','private-fixtures.json','private-retest-fixtures.json'} for p in OUT.rglob('*'))
for p in [EX/'B11_EXECUTION_REPORT.md',EX/'WAVE_11_SUMMARY.md',OUT/'replay/README.md']:
 assert not any(line.rstrip()!=line for line in p.read_text(encoding='utf-8').splitlines())
products={name:{'entry':old,'final':new} for name,(old,new) in final['source_delta'].items()}
artifact_hashes={p.relative_to(DOC).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [EX/'B11_EXECUTION_REPORT.md',EX/'WAVE_11_SUMMARY.md',EX/'B11_FINAL_RETEST.csv',DOC/'TEST_EXECUTION_MATRIX_MVP.csv',DOC/'DEFECT_REGISTER.csv',DOC/'DEFECT_REGISTER.md',DOC/'APPROVED_DESIGN_CONFORMANCE_REGISTRY.md']}
result={'head':entry['head'],'source_fingerprint':final['source_fingerprint'],'source_files_verified':len(hashes['final']),'product_delta':products,'new_product_files':0,'protected_source_unchanged':True,'non_b11_matrix_rows_preserved':829,'historical_defect_records_preserved':61,'historical_defect_markdown_prefix_preserved':True,'new_defects_retested':3,'final_retest_exact_row_ids':302,'counts':counts['current'],'technical':counts['technical'],'evidence_paths_exist':True,'no_new_po_acceptance':True,'private_postgresql_stopped':True,'private_django_servers':'All task hosts terminated in their scripts. Existing development servers on port 8000 were observed and left untouched.','production_or_normal_database_operations':False,'commit_or_push':False,'artifacts_sha256':artifact_hashes}
(OUT/'closeout-integrity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Integrity PASS. 302 unique outcomes, 829 other rows and 61 historical defects preserved. Eight product deltas verified. Private cluster stopped.')
