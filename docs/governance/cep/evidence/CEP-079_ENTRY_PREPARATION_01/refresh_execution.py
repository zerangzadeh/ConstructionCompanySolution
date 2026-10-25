"""Synchronize existing CEP079 records from retained actual results only."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
now = datetime.now(timezone.utc).isoformat()
matrix_path = OUT / '44_CASE_READINESS_MATRIX.json'
matrix = json.loads(matrix_path.read_text(encoding='utf-8'))
s = matrix['uat_execution_summary']
s.update(defects_discovered=16, defects_fixed=16, product_defects_discovered=10,
    configuration_authority_defects_discovered=6, unresolved_uat_blocking_defects=0,
    unresolved_product_defects=0, environment_blockers=1, blocker="ENV002 recurred at handoff: local Browser disabled;036 unattempted",
    execution_status='PAUSED_AT_HUMAN_SESSION_BOUNDARY', updated_at=now)
matrix_path.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

path = ROOT/'CEP_EXECUTION_REGISTRY.yaml'
source = path.read_text(encoding='utf-8')
def other_ceps(text):
    blocks = re.findall(r'^  (CEP-\d{3}):\n(.*?)(?=^  CEP-\d{3}:\n|^authority_scope:)', text, re.M|re.S)
    return {key:value for key,value in blocks if key!='CEP-079'}
before=other_ceps(source)
start=source.index('  CEP-079:\n'); end=source.index('  CEP-080:\n',start)
section=source[start:end]
for key, value in [('attempted',s['attempted']),('fully_executed',s['fully_executed']),('pass',s['pass']),('fail',s['fail']),('blocked',s['blocked']),('not_executed',s['not_executed']),('defects_discovered',s['defects_discovered']),('defects_fixed',s['defects_fixed']),('product_defects_discovered',10),('configuration_authority_defects_discovered',6),('product_defects_fixed',10),('unresolved_environment_blockers',1)]:
    section=re.sub(r'^      '+key+r': .*$',f'      {key}: {value}',section,flags=re.M)
coverage=f"{s['satisfied_mappings']}_OF_48_SATISFIED_{s['blocked_mappings']}_BLOCKED_{s['unexecuted_mappings']}_NOT_EXECUTED"
section=re.sub(r'^      coverage: .*$',f'      coverage: {coverage}',section,flags=re.M)
x=section.index('    remaining_utv:');y=section.index('    completion_report:',x)
pending=[r['scenario_id'] for r in matrix['rows'] if r['uat_execution_result']!='PASS']
section=section[:x]+'    remaining_utv:\n'+f"    - {', '.join(pending)} runtime assertions remain unverified.\n"+section[y:]
section=re.sub(r'^      entry_history: .*$', '      entry_history: Entry PASS retained; Browser resolved; native exact access/configuration corrections and actual runtime results retained.',section,flags=re.M)
section=re.sub(r'^      focused_validation: .*$', '      focused_validation: PRIOR_BILLING5_PASS_PLUS_PROCUREMENT5_SHARED_WORKFLOW3_RUFF_DJANGO_CHECK_PASS;2_BASELINE_FIXTURE_FAILURES_ATTRIBUTED',section,flags=re.M)
source=source[:start]+section+source[end:]
source=re.sub(r'^  boundary_reason: .*$',f"  boundary_reason: CEP079 paused at explicit Human new-session request;{s['pass']}PASS,{s['blocked']}BLOCKED,{s['not_executed']}NOT_EXECUTED; other CEPs excluded.",source,flags=re.M)
assert len(before)==85 and before==other_ceps(source)
path.write_text(source,encoding='utf-8')

report=ROOT/'docs/governance/cep/reports/CEP-079_COMPLETION_REPORT.md'
content=report.read_text(encoding='utf-8').split('\n<!-- CURRENT_CONTINUATION -->')[0]
content+=f"\n<!-- CURRENT_CONTINUATION -->\n\n## Current Browser-enabled continuation\n\nThis section supersedes the historical stopped-boundary summary above. As of {now}: EXECUTION PARTIAL / PAUSED_AT_HUMAN_SESSION_BOUNDARY; {s['fully_executed']}/44 fully executed; PASS{s['pass']} / FAIL{s['fail']} / BLOCKED{s['blocked']}; {s['not_executed']} NOT_EXECUTED. Mapping coverage {s['satisfied_mappings']}/48; {s['unexecuted_mappings']} unexecuted. ENV002 was resolved for actual cases024..035, then recurred at handoff: tab.markHandoff reports local Browser disabled. No scenario invalidated;036 not attempted. Verify Browser first in next session. Defects16 discovered/16fixed/0unresolved: prior8 plus temporary persona-access correction009, project-scoped PR/shared start guard010, registered independent RFQ policy configuration011, Material form tenant validation012, Partner navigation013 and workbench request/selector contract014, valid Inventory valuation reversal reconciliation015 and Timekeeping scoped site cascade016. No schema/migration. Narrow native audited grants and synthetic workflows only.5focused+3shared+8MaterialsPartner+5Inventory testsPASS; changed-source RuffPASS; latest Timekeeping cascade has browser rerunPASS and RuffPASS, focused regression pending next session; two baseline fixture failures occur before changed runtime code. AC2/4/5/6PASS, AC1NOT_MET,AC3PARTIAL; scopedDoDNOT_MET. Native ordinary UI evidence retained per case; remaining cases stayUTV. Other CEPs/Git writes/Production/HumanSignoff NOT_EXECUTED.\n"
report.write_text(content,encoding='utf-8')

ev=ROOT/'docs/governance/cep/evidence/CEP-079_EVIDENCE_MANIFEST.csv'
with ev.open(encoding='utf-8',newline='') as f:
    reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
known={r['path'] for r in rows}; next_id=max(int(r['evidence_id'].split('-')[-1]) for r in rows)+1
for file in sorted(OUT.glob('UAT_CASE_*')):
    relative=file.relative_to(ROOT).as_posix()
    if relative not in known:
        number=int(file.name.split('_')[2]); result=matrix['rows'][number-1]['uat_execution_result']
        rows.append(dict(evidence_id=f'CEP-079-EV-{next_id:03d}',path=relative,sha256='',kind=f'Actual Case{number:03d} retained runtime/browser/source evidence',result=result));next_id+=1
for row in rows:
    file=ROOT/row['path'];row['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
    if file.name=='44_CASE_READINESS_MATRIX.json': row['result']='PARTIAL_IN_PROGRESS'
    if file.name.startswith('UAT_CASE_'):
        number=int(file.name.split('_')[2]);row['result']=matrix['rows'][number-1]['uat_execution_result']
with ev.open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

accept=ROOT/'docs/governance/cep/evidence/CEP-079_ACCEPTANCE_MAPPING.csv'
with accept.open(encoding='utf-8',newline='') as f:
    reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
for row in rows:
    row['evidence']=f'CEP-079-EV-001..{next_id-1:03d}'
    if row['criterion']=='AC1':row['result']=f"44-scenario execution incomplete:{s['pass']}PASS{s['blocked']}BLOCKED{s['not_executed']}NOT_EXECUTED;{s['satisfied_mappings']}of48 mappings satisfied."
    if row['criterion']=='AC3':row['result']=f"Actual cases001..{s['fully_executed']:03d} executed;remaining assertionsUTV."
    if row['criterion']=='AC5':row['result']='Actual failures and bounded corrections retained; missing assertions remain open gaps.'
    if row['criterion']=='AC6':row['result']='Unexecuted assertions remainUTV; preparation/static evidence never promoted.'
with accept.open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
change=ROOT/'docs/governance/cep/evidence/CEP-079_CHANGE_MANIFEST.csv'
status=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT,text=True)
with change.open('w',encoding='utf-8',newline='') as f:
    writer=csv.writer(f);writer.writerow(['path','change','purpose'])
    for line in status.splitlines():
        writer.writerow([line[3:],'MODIFIED' if line[:2]!='??' else 'ADDED_OR_ADVANCED_EXISTING_UNTRACKED','Bounded CEP079 correction, focused validation or retained execution evidence; existing changes preserved'])
print(f"Synchronized:{s['fully_executed']}/44;{s['satisfied_mappings']}/48;other85CEP records unchanged")
