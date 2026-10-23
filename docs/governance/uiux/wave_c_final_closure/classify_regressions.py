"""Classify each recorded failure by cause; never equate any prior failure with baseline attribution."""
import json,xml.etree.ElementTree as ET
from pathlib import Path
OUT=Path(__file__).resolve().parent
original=json.loads((OUT.parent/'wave_c_domain_resolution/BASELINE_DEBT.json').read_text())['failures']
def suite(name):
 cases={}
 for c in ET.parse(OUT/(name+'.xml')).iter('testcase'):
  f=c.find('failure');cases[c.attrib['classname']+'.'+c.attrib['name']]={'result':'FAIL' if f is not None else 'PASS','message':f.attrib.get('message','') if f is not None else ''}
 return cases
frozen,current,fixed=suite('frozen'),suite('entry_before' if (OUT/'entry_before.xml').exists() else 'current'),suite('fixed_final')
assert len(frozen)==len(current)==len(fixed)==10 and sum(v['result']=='FAIL' for v in current.values())==10
rows=[]
for old in original:
 name=old['test'];fn=name.rsplit('.',1)[1];baseline_name=name.replace('test_payroll_registry_is_complete_and_owner_admin_are_denied','test_payroll_registry_is_complete_and_default_roles_are_denied');final_name=name.replace('test_reversal_permission_has_no_implicit_system_role_grants','test_reversal_permission_has_only_reviewed_system_role_grants')
 row={'test':name,'recorded_message':old['message'],'frozen_head':frozen[baseline_name],'entry_replay':current[name],'final':fixed[final_name],'final_test':final_name}
 if 'payroll_registry' in fn:
  row.update(classification='BASELINE_PREEXISTING',proof='Same registry omission at HEAD; StatutorySourcePackage exists in unchanged models and is omitted from registry. Frozen original predecessor and current test both fail the model-subset assertion.',disposition='RETAINED_UNCHANGED')
 elif 'P5S26S27MatchReviewTests' in name:
  row.update(classification='BASELINE_PREEXISTING',proof='HEAD full test has an earlier legacy-authority fixture failure. The exact additional approver is unchanged and has no explicit role/scope. FROZEN_APPROVER_PROBE.json reproduces denial of INVOICE_MATCH_POLICIES_APPROVE using the exact fixture input and immutable HEAD authorization code; no role/scope existed before the current changes. Owner/Admin defaults and authorization functions are unchanged.',disposition='RETAINED_UNCHANGED; temporary fixture repair restored byte-for-byte to entry')
 elif 'permission_is_intersected_with_project_scope' in fn:
  row.update(classification='ATTRIBUTABLE_REGRESSION',proof='Accepted authorization fixture now creates the migrated role assignment. The unchanged scenario then creates the same unrevoked role a second time. HEAD fails earlier on its older legacy fixture, which is a distinct cause; the duplicate is introduced specifically by the accepted shared bootstrap.',fix='Reuse the already explicit assignment and revoke fixture organization scope before asserting the unrelated-project denial.',disposition='RESOLVED')
 elif 'only_reviewed' in final_name:
  row.update(classification='ATTRIBUTABLE_REGRESSION',proof='This assertion passes at HEAD but rejects the explicitly approved accountant default grant added by Authorization reconciliation.',fix='Assert the exact reviewed system-role set is accountant; Owner/Admin remain excluded. No product permission/default changes.',disposition='RESOLVED')
 else:
  row.update(classification='ATTRIBUTABLE_REGRESSION',proof='The accepted shared Procurement fixture adds active role assignments and marks memberships migrated. Merely replacing role_definition in InvoiceAPFixture no longer replaces effective authority. HEAD custom-role fixtures pass the AP guard; current entry is denied. SOURCE_ATTRIBUTION.json records unchanged domain/authorization functions and the changed shared bootstrap.',fix='Add the explicitly intended isolated custom test role as an active membership role; preserve business authorization and all existing role defaults.',disposition='RESOLVED')
  if 'InvoiceAPMigrationTests' in name:
   assert 'corrects_id' in row['frozen_head']['message'] and 'corrects_id' in row['final']['message']
   row['disposition']='ATTRIBUTABLE_AP_PERMISSION_FAILURE_RESOLVED; UNDERLYING_BASELINE_SCHEMA_DEBT_RETAINED'
   row['underlying_baseline']='HEAD and final both query WriteOffProposal.corrects_id through current reversal services after the test migrates only to subledgers.0005. The column is introduced by unchanged HEAD migration 0007. No schema/service/test-target repair is authorized here.'
 if row['classification']=='ATTRIBUTABLE_REGRESSION' and 'InvoiceAPMigrationTests' not in name:assert row['final']['result']=='PASS'
 rows.append(row)
counts={c:sum(r['classification']==c for r in rows) for c in ['BASELINE_PREEXISTING','ATTRIBUTABLE_REGRESSION','INDETERMINATE']}
assert counts=={'BASELINE_PREEXISTING':3,'ATTRIBUTABLE_REGRESSION':7,'INDETERMINATE':0}
result={'original_failure_count':10,'counts':counts,'unresolved_attributable_regressions':0,'frozen_head':'5 PASS / 5 FAIL (includes earlier legacy fixture failures distinct from the recorded entry causes)','entry':'0 PASS / 10 FAIL; exact accepted entry failure conditions reproduced','final_focused':'6 PASS / 4 FAIL; three original baseline cases plus one unmasked HEAD schema mismatch','additional_attributable_ui_regression':'Raw Person object (UUID) relationship labels introduced by the new Wave C management form/template: RESOLVED with business names and employee number; no identity/authorization change','additional_retained_baseline':'Old-schema migration test/current model mismatch (WriteOffProposal.corrects_id), reproduced at immutable HEAD and final','superseded_validation':'fixed_10.xml and affected.xml temporarily included an approver-fixture repair. That baseline-only repair was restored to entry; fixed_final.xml and affected_final.xml alone describe final source.','rows':rows,'source_evidence':['FROZEN_SOURCE.json','SOURCE_ATTRIBUTION.json','FROZEN_APPROVER_PROBE.json','frozen.xml','current.xml','entry_before.xml','fixed_final.xml','affected_final.xml']}
(OUT/'REGRESSION_ATTRIBUTION.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(counts),'Unresolved attributable: 0')
