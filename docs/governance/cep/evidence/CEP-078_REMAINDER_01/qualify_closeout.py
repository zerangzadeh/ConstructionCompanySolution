"""Correct initial requested-size claims using measured CSS runtime evidence."""
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'.pytest_cache/cep_tools'))
import yaml
path=ROOT/'CEP_EXECUTION_REGISTRY.yaml'
original=path.read_text(encoding='utf8')
registry=yaml.safe_load(original)
entry=json.loads((OUT/'ENTRY.json').read_text(encoding='utf8'))
digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
assert all(digest(registry['ceps'][k])==v for k,v in entry['all_other_cep_hashes'].items())
assert registry['gates']==entry['gate_state']
qualified=json.loads((OUT/'RUNTIME_QUALIFIED.json').read_text(encoding='utf8'))
assert len(qualified['canonicalPass'])==5
assert {(c['browser'],c['viewport']['width']) for c in qualified['canonicalPass']}=={('Chrome',1440),('Chrome',1024),('Chrome',390),('Edge',1440),('Edge',1024)}
for c in qualified['canonicalPass']:
    assert c['observedViewport']['width']==c['viewport']['width'] and c['observedViewport']['height']==c['viewport']['height']
cep=registry['ceps']['CEP-078']
cep['completion_report']['evidence_presence']='SC033_5_QUALIFIED_CANONICAL_PASS_CELLS_EDGE390_UTV_7_TESTS8SUBTESTS_STATUTORY_RESOLVER_CLAIM_SERVER_PASS'
cep['verification_review']['finding032']='PRODUCT_DECISION_RESOLVED_ALL26_CATALOGUE_IMPLEMENTED;5_CANONICAL_CSS_CELLS_PASS;EXACT_EDGE390_UTV_ZOOM_CONTROL'
cep['verification_review']['remainder_runtime_qualification']='RUNTIME_QUALIFIED.json supersedes initial Edge requested-size claims; measured actual CSS dimensions authoritative; original captures retained'
cep['blockers'].append('BLOCKER-EXTERNAL / SC033 exact Edge390x844 UTV:75% page zoom, integer viewport API yields389/391; calibrated Edge1440/1024 PASS; Ctrl+0 input unresponsive. No Product decision remains.')
cep['remaining_utv'].append('SC033 exact Edge390x844 after restoring normal browser zoom/input; initial Edge requested-size captures are unqualified dimension observations, not canonical size PASS')
cep['history'].append({'date':'2026-10-26','status':'VIEWPORT_MEASUREMENT_QUALIFICATION_CORRECTION','reason':'Final measuredCSS check found Edge page zoom75%; initial6-cell requested-size PASS description superseded by5canonical CSS PASS cells. Chrome3 retained; Edge1440/1024 calibrated and rerun only because actual dimension concern found. Exact Edge390 remains UTV (integer API389/391, fractional292.5 rejected, Ctrl0 unresponsive); nearest391 is not exact390 PASS. Initial capture timeouts each recovered after fresh observation and one retry. Source Product decision remains resolved; no otherCEP/Gate changed.'})
frontier=registry['execution_frontier']
frontier['unblock_conditions']['CEP-078'] += ' SC033 exact Edge390x844 also needs normal browser zoom/input recovery; five canonical CSS cells PASS.'
fragment='  CEP-078:\n'+'\n'.join('    '+line if line else '' for line in yaml.safe_dump(cep,sort_keys=False,allow_unicode=True,width=140).rstrip().splitlines())+'\n'
updated,n=re.subn(r'^  CEP-078:\n.*?(?=^  CEP-079:)',lambda m:fragment,original,flags=re.M|re.S); assert n==1
updated,n=re.subn(r'^execution_frontier:\n.*\Z',lambda m:yaml.safe_dump({'execution_frontier':frontier},sort_keys=False,allow_unicode=True,width=140),updated,flags=re.M|re.S); assert n==1
path.write_text(updated,encoding='utf8')
base=ROOT/'docs/governance/cep/evidence'
mapping=base/'CEP-078_ACCEPTANCE_MAPPING.csv'
with mapping.open(encoding='utf8',newline='') as handle:
    reader=csv.DictReader(handle); rows=list(reader);fields=reader.fieldnames
for row in rows:
    row['reuse_disposition']=row['reuse_disposition'].replace('SC0336final PASS cells','SC0335qualified canonical CSS PASS cells;Edge390UTV;initial Edge requested-size descriptions superseded')
    if row['criterion'] in {'AC-1','AC-3'}:row['remaining_gap'] += '; SC033 exact Edge390x844 after zoom/input recovery'
with mapping.open('w',encoding='utf8',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
manifest=base/'CEP-078_EVIDENCE_MANIFEST.csv'
with manifest.open(encoding='utf8',newline='') as handle:
    reader=csv.DictReader(handle);rows=list(reader);fields=reader.fieldnames
for row in rows:
    if row['evidence_id']=='CEP-078-EV-017':
        row['path']=str((OUT/'RUNTIME_QUALIFIED.json').relative_to(ROOT)).replace('\\','/')
        row['sha256']=hashlib.sha256((OUT/'RUNTIME_QUALIFIED.json').read_bytes()).hexdigest()
        row['evidence_kind']='Measured actual CSS5canonical PASS; exact Edge390UTV; initial Edge size claims superseded'
with manifest.open('w',encoding='utf8',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)
report=ROOT/'docs/governance/cep/reports/CEP-078_COMPLETION_REPORT.md'
with report.open('a',encoding='utf8') as handle:
    handle.write('\n\n### Final CSS viewport qualification correction\n\nMeasured CSS dimensions supersede the initial requested-size description above: **5canonical catalogue cells PASS** (Chrome1440/1024/390, Edge1440/1024). Edge75% page zoom required calibrated physical viewport settings. Exact Edge390x844 remains UTV: integer API produces389/391 CSS pixels, fractional292.5 rejected, Ctrl+0 unresponsive. Nearest391 renders all26 without overflow but is not an exact390 PASS. Original captures retained; only affected Edge dimensions reverified. See `CEP-078_REMAINDER_01/RUNTIME_QUALIFIED.json`. Product decision/source qualification remain resolved; AC/DoD and Gate states unchanged.\n')
print('Final qualified result:5 canonical CSS PASS;Edge390 UTV; all85 other CEPs and Gates unchanged.')
