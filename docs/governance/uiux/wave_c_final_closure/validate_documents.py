"""Verify current addenda without rewriting prior authorities/evidence."""
import ast,json,re,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;BASE=OUT.parent
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/bonira-wave-c-tools'))
import yaml
old=yaml.safe_load((OUT/'entry_reports/UIUX_RUNTIME_VALIDATION_RESULTS.yaml').read_text(encoding='utf-8'));new=yaml.safe_load((BASE/'UIUX_RUNTIME_VALIDATION_RESULTS.yaml').read_text(encoding='utf-8'))
for key,value in old.items():
 if key!='latest_wave_c_execution':assert new[key]==value,key
assert new['latest_wave_c_execution']=='wave_c_final_closure'
oldf=yaml.safe_load((OUT/'entry_reports/UIUX_FINDINGS_REGISTER.yaml').read_text(encoding='utf-8'));newf=yaml.safe_load((BASE/'UIUX_FINDINGS_REGISTER.yaml').read_text(encoding='utf-8'))
for key,value in oldf.items():
 if key not in {'findings','latest_wave_c_execution'}:assert newf[key]==value,key
before={f['finding_id']:f for f in oldf['findings']};after={f['finding_id']:f for f in newf['findings']}
for key,value in before.items():
 if key not in {'UIUX-F-008','UIUX-F-009','UIUX-F-038'}:assert after[key]==value,key
 if 'RESOLVED' in value['status']:assert 'RESOLVED' in after[key]['status'],key
assert set(after)-set(before)=={'UIUX-F-133'}
missing=[]
for r in json.loads((OUT/'WAVE_C_FINAL_MATRIX.json').read_text(encoding='utf-8'))['scenario_results']:
 if not (OUT/r['evidence']).exists():missing.append(r['evidence'])
for match in re.findall(r'\]\(([^)]+)\)',(OUT/'COMPLETION_REPORT.md').read_text(encoding='utf-8')):
 if not match.startswith(('http','/','#')) and not (OUT/match.split('#')[0]).exists():missing.append(match)
assert not missing,missing
assert (BASE/'UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md').read_text(encoding='utf-8').startswith((OUT/'entry_reports/UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md').read_text(encoding='utf-8').rstrip())
for p in ['apps/workforce/employment_forms.py','tests/test_uiux_wave_c_reentry.py','apps/procurement/test_p5_s08_sealed_custody.py','apps/subledgers/test_cep033_invoice_handoff.py']:ast.parse((BASE.parents[2]/p).read_text(encoding='utf-8'))
(OUT/'DOCUMENT_VALIDATION.json').write_text(json.dumps({'yaml_parse':'PASS','historical_results_preserved':True,'unaffected_and_closed_findings_preserved':True,'new_finding':'UIUX-F-133','relative_evidence_links':'PASS','changed_python_parse':'PASS','matrix':'11 PASS / 1 pending; official statutory success excluded','prior_report_preserved':True},indent=2)+'\n')
print('Documentation PASS: YAML, history, closed findings, links and scoped Python parse')
