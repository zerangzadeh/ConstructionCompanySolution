"""Append bounded Wave C results; preserve historical and accepted closures."""
import copy
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
UI=OUT.parent
sys.path.insert(0,str(Path(os.environ['TEMP'])/'bonira-wave-c-tools'))
import yaml

def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
def append(path,key,value):
    text=path.read_text(encoding='utf-8')
    assert key not in yaml.safe_load(text)
    path.write_text(text.rstrip()+'\n'+yaml.safe_dump({key:value},allow_unicode=True,sort_keys=False,width=100),encoding='utf-8',newline='\n')

def main():
    assert not (OUT/'DOCUMENTS_WRITTEN.json').exists()
    stamp=datetime.now(ZoneInfo('Asia/Tehran')).isoformat()
    matrix=yaml.safe_load((UI/'UIUX_RUNTIME_VALIDATION_MATRIX.yaml').read_text(encoding='utf-8'))
    ids=['RV-007','RV-009','RV-011','RV-013','RV-015','RV-017','RV-018','RV-028','RV-029','RV-030','RV-031','RV-032']
    decisions={
      'RV-007':('NEEDS_PRODUCT_REVIEW','P-03 bounded Buyer absent. P-17 A workspace and empty comparison/award forms observed; C/X/site denied. Stage/priority F008 remains open; valid specialist comparison/award lifecycle requires approved role and source/grant/policy decisions, not invented next-action semantics.'),
      'RV-009':('PASS','Dedicated persistent P-22 existing Viewer/organization scope prepared canonically. Quantity list, own warehouse drilldown, custody and valuation reads observed; project-scoped P-01 and C/X controls remain denied. Viewer cannot invoke valuation reconciliation. Operational posting/valuation production is outside this navigation scenario.'),
      'RV-011':('BLOCKED_TEST_DATA','P-05 organization Accountant read/empty preview and retained immutable report observed; same-tenant unauthorized and cross-tenant run denied. Populated synthetic 1-IRR manual journal preparation reached missing active Tenant policy; transaction rolled back. Numeric/account-type populated runtime is not PASS; all 15 enum presentation combinations and posted-line reporting have isolated tests.'),
      'RV-013':('NEEDS_DOMAIN_REVIEW','P-05 workbench empty state observed; P-07 bounded specialist absent. Zero obligations and no eligible posted Treasury source. Current source recognition is unactivated. No fake obligation, cash movement, settlement or policy activation created.'),
      'RV-015':('BLOCKED_AUTHORIZATION_FIXTURE','No bounded P-08/P-21 HR administration role. P-01 project identity denied organization structure/foundation and create; manipulated employee POST rejected. Existing broad managerial roles are not HR-only specialist authority.'),
      'RV-017':('BLOCKED_AUTHORIZATION_FIXTURE','P-10 retained attendance-read subset observed; calendar GET/POST denied. Calendar administration/daily-write specialist bundle unavailable. No broad HR/manager authority substituted; F040 setup/daily-work structure remains open.'),
      'RV-018':('BLOCKED_AUTHORIZATION_FIXTURE','P-20 unprovisioned. Built-in sensitive Payroll permissions excluded by default. Existing p7_demo_payroll_assurance is explicitly designated to the demo Owner and includes sensitive Workforce permissions; no reuse as a Payroll-only specialist or statutory activation. Viewer negatives only; run/statutory/handoff positive lifecycle unexecuted.'),
      'RV-028':('BLOCKED_AUTHORIZATION_FIXTURE','P-19 retained document read/detail/version history observed; C/X metadata and write routes denied. Upload/version/link specialist bundle absent. Both accessible versions unavailable for safe download; direct download lookup denies. No fabricated CLEAN scanner assessment or Platform Operations bypass.'),
      'RV-029':('NEEDS_PRODUCT_REVIEW','No governed internal employment-record management UI. employment_records.manage and view_own absent from every actual role. Unlinked ESS denied; cross-tenant Employee denied. No identity inferred from Employee/usernames and no management route invented.'),
      'RV-030':('NEEDS_DOMAIN_REVIEW','P-23 contract read/commercial-review and empty tender list observed. C/X contract access denied. Canonical create_tender_bid preparation denied missing active tender policy and rolled back. Specialist preparation bundle and policy activation cannot be invented.'),
      'RV-031':('BLOCKED_AUTHORIZATION_FIXTURE','P-17 and P-24 retained Viewer comparison: A controls/WBS/activities and estimates read observed; P-17 estimate form observed. C/X/site controls and advanced comparison/exceptions/cost reconciliation denied. Bounded P-24 role and approved comparison authority absent; no Project Cost source invented.'),
      'RV-032':('BLOCKED_AUTHORIZATION_FIXTURE','All actual roles lack supplier_portal.invitations_manage by explicit default exclusion. Canonical invitation creation denied Owner; complete initial fixture transaction rolled back. Three direct internal actors denied. Acceptance anonymous-to-tenant-boundary page and invalid token controls observed; no P-26 external grant/submission/receipt/isolation positive claim.'),
    }
    findings_by_scenario={'RV-007':['UIUX-F-008','UIUX-F-009'],'RV-009':['UIUX-F-023','UIUX-F-024','UIUX-F-130'],'RV-011':['UIUX-F-092','UIUX-F-093'],'RV-013':['UIUX-F-012','UIUX-F-013','UIUX-F-014'],'RV-015':[],'RV-017':['UIUX-F-040','UIUX-F-041'],'RV-018':['UIUX-F-005','UIUX-F-006','UIUX-F-058','UIUX-F-059','UIUX-F-067','UIUX-F-068','UIUX-F-069'],'RV-028':['UIUX-F-011'],'RV-029':[],'RV-030':['UIUX-F-038'],'RV-031':['UIUX-F-019'],'RV-032':['UIUX-F-060','UIUX-F-129']}
    before=read('baseline_HTTP.json');after=read('after_HTTP.json');browser=read('final_BROWSER.json')
    records=[]
    for number,id in enumerate(ids,41):
        scenario=next(x for x in matrix['scenarios'] if x['scenario_id']==id)
        result,reason=decisions[id]
        observations=[r for r in after if r['scenario']==id]
        captures=[r for r in browser if r['scenario']==id]
        records.append(dict(evidence_id=f'RV-EV-{number:03}',scenario_id=id,executed_at=stamp,runtime=dict(environment_name='Development',base_url='http://127.0.0.1:8015',git_sha=read('ENTRY.json')['head'],effective_build='Existing accepted dirty source plus TOUCH_SET.json; FILES_BEFORE.json and final artifact index identify bytes',browser='Microsoft Edge',browser_version=browser[0]['browser'],viewports=[[1440,900],[390,844]]),persona=dict(persona_ids=scenario['persona_ids'],actual_actors=sorted(set(r['actor'] for r in observations+captures)),effective_permission_bundle_reference=['INVENTORY.json','INVENTORY_PERSONA.json','READINESS.json']),surfaces=scenario['surfaces'],expected_result=scenario['validate'],actual_result=reason,result=result,disposition='PASS' if result=='PASS' else 'BLOCKED',finding_ids=findings_by_scenario[id],http_reference='after_HTTP.json',http_observations=len(observations),browser_reference='final_BROWSER.json',browser_observations=len(captures),screenshots=[s for r in captures for s in r['screenshots']],accessibility=dict(keyboard_only='Six Tab steps captured per view; targeted disclosures separately checked. No whole-scenario accessibility PASS inferred.',focus_visible='Recorded in final_BROWSER.json',landmarks='One main on all 20 captured pages',notes='Denied pages are negative controls, not positive specialist evidence'),authorization=dict(server_authorization_verified_when_applicable=True,cross_tenant_leakage_observed=False,scope='165 real authenticated HTTP observations + 9 delta + 20 direct services; VERIFICATION.json gives exact metadata controls; blocking gates limit positive lifecycle coverage'),mutation_performed=id in ['RV-007','RV-009','RV-011'],mutation_record_or_cleanup='INTEGRITY.json; three canonical issued synthetic RFQs + two immutable empty statement projections; one retained P-22 reference account; no temporary authority',notes='Every canonical validation target is explicit; unexecuted targets remain blocked and do not inherit PASS from a page render.'))
    # Evidence timestamps are capture-file times, not the documentation timestamp.
    for record in records:
        captures=[OUT/r['html'] for r in after if r['scenario']==record['scenario_id']]+[OUT/s for r in browser if r['scenario']==record['scenario_id'] for s in r['screenshots']]
        times=[p.stat().st_mtime for p in captures]
        record['recorded_at']=record.pop('executed_at')
        record['executed_at']=datetime.fromtimestamp(max(times),ZoneInfo('Asia/Tehran')).isoformat()
        record['runtime']['evidence_capture_interval']={'starts_at':datetime.fromtimestamp(min(times),ZoneInfo('Asia/Tehran')).isoformat(),'ends_at':datetime.fromtimestamp(max(times),ZoneInfo('Asia/Tehran')).isoformat(),'basis':'Capture-file modification times; recorded_at is reconciliation time'}
    summary=dict(decision='WAVE_C_BLOCKED',execution='PARTIAL_WITH_EXPLICIT_STOP_BOUNDARY_BLOCKERS',session_closed=True,wave_closed=False,report='UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md',evidence_directory='wave_c_evidence/',scenario_results=records,all_12_scenarios_dispositioned=True,full_required_execution_complete=False,utv='Positive specialist lifecycles named in each blocked record',migration='NO',new_findings=['UIUX-F-129','UIUX-F-130'],production='UNTOUCHED',cep078079='NOT_EXECUTED',git_add_commit_push='NOT_EXECUTED')
    # Retain the prior 128 objects exactly except for explicit bounded retest metadata.
    register=UI/'UIUX_FINDINGS_REGISTER.yaml'
    text=register.read_text(encoding='utf-8')
    original=yaml.safe_load(text)
    (OUT/'FINDINGS_ENTRY_OBJECTS.json').write_text(json.dumps(original['findings'],ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    resolved={'UIUX-F-009':'RV-007','UIUX-F-011':'RV-028','UIUX-F-014':'RV-013','UIUX-F-019':'RV-031','UIUX-F-023':'RV-009','UIUX-F-024':'RV-009','UIUX-F-038':'RV-030','UIUX-F-041':'RV-017','UIUX-F-092':'RV-011','UIUX-F-093':'RV-011'}
    for id,scenario in resolved.items():
        start=text.index('- finding_id: '+id+'\n')
        match=re.search(r'\n- finding_id: |\n[a-zA-Z_]+:',text[start+1:])
        end=start+1+match.start() if match else len(text)
        block=text[start:end]
        assert 'wave_c_retest:' not in block
        retest=dict(status='RUNTIME_VERIFIED_RESOLVED',scenario=scenario,report='UIUX_RUNTIME_VALIDATION_WAVE_C_REPORT.md',evidence='wave_c_evidence/VERIFICATION.json',root_cause='Primary templates directly rendered implementation terms or enum/hash data; bounded presentation only',validation='final_BROWSER.json; after_HTTP.json; focused_final.xml; regression.xml',limit='Closure concerns this finding only. Blocked specialist/source lifecycle and unrelated usability findings remain explicit.')
        text=text[:end]+'\n  wave_c_retest: '+json.dumps(retest,ensure_ascii=False)+text[end:]
    new_findings=[dict(finding_id='UIUX-F-129',module='Procurement supplier portal',surface_id='RV-032-ACCEPT',route='/procurement/portal/accept/',page_title='پذیرش دعوت‌نامه',roles=[],category='ACCESSIBILITY',severity='MEDIUM',status='RESOLVED',runtime_status='RUNTIME_VERIFIED_RESOLVED',problem='Portal acceptance template nested its main landmark inside the application main.',evidence=dict(before='wave_c_evidence/before_BROWSER.json',after='wave_c_evidence/final_BROWSER.json',tests='wave_c_evidence/focused_final.xml',source_paths=['templates/procurement/portal_accept.html']),root_pattern_candidate=['RP-C14-SEMANTIC-LANDMARK-INCONSISTENCY'],recommendation='Keep the application main and use a labelled section in the acceptance content.',business_logic_impact='NONE',needs_domain_review=False,related_cep=[],related_standard=[],resolution='Inner main replaced with labelled section; genuine desktop/mobile captures show one main. Acceptance/authentication semantics unchanged.'),dict(finding_id='UIUX-F-130',module='Inventory',surface_id='RV-009-VALUATION',route='/inventory/valuation/',page_title='ارزش میانگین موزون متحرک',roles=['viewer'],category='PERMISSION_UX',severity='MEDIUM',status='RESOLVED',runtime_status='RUNTIME_VERIFIED_RESOLVED',problem='Authorized organization-scoped valuation Viewer received 403 because the page unconditionally called a separately protected reconciliation projection.',evidence=dict(before='wave_c_evidence/before_fixed_BROWSER.json',after='wave_c_evidence/final_BROWSER.json',tests='wave_c_evidence/focused_final.xml',direct='wave_c_evidence/DIRECT_SERVICE.json',source_paths=['apps/inventory/p8_views.py','templates/inventory/valuation_workbench.html']),root_pattern_candidate=['RP-C05-TASK-GUIDANCE-DEFICIT'],recommendation='Render independently authorized valuation reads; retrieve/show optional reconciliation only with its own organization-context permission.',business_logic_impact='NONE; protected service and permission definitions unchanged',needs_domain_review=False,related_cep=[],related_standard=[],resolution='Optional view-layer reconciliation query. Reader HTTP 200; reconciliation service still denies; reviewer branch and cross-tenant/project/revoked/POST controls tested. No valuation, posting or source facts created.')]
    pos=text.index('\nruntime_wave_a:')
    text=text[:pos]+'\n'+yaml.safe_dump(new_findings,allow_unicode=True,sort_keys=False,width=100).rstrip()+text[pos:]
    text=text.replace('  finding_count: 128\n','  finding_count: 130\n',1)
    text=text.replace('    MEDIUM: 46\n','    MEDIUM: 48\n',1)
    register.write_text(text,encoding='utf-8',newline='\n')
    append(register,'wave_c',dict(decision=summary['decision'],new_findings=['UIUX-F-129','UIUX-F-130'],bounded_existing_finding_retests=sorted(resolved),prior_resolved_findings_preserved=True,all_scenarios_runtime_complete=False,report=summary['report']))
    results=UI/'UIUX_RUNTIME_VALIDATION_RESULTS.yaml'
    text=results.read_text(encoding='utf-8').replace('Waves C-E not executed.','Wave C partial execution is appended under wave_c; Waves D-E not executed.',1)
    results.write_text(text,encoding='utf-8',newline='\n')
    append(results,'wave_c',summary)
    append(UI/'UIUX_ROOT_PATTERN_IMPACT_MAP.yaml','wave_c_runtime',dict(report=summary['report'],decision=summary['decision'],bounded_retests=sorted(resolved),new_findings=['UIUX-F-129','UIUX-F-130'],notes='Historical pattern catalogue preserved. Retest metadata closes only identified presentation/access defects; no blocked scenario inherits PASS.'))
    append(UI/'UIUX_RUNTIME_VALIDATION_MATRIX.yaml','wave_c_execution',dict(decision=summary['decision'],results='UIUX_RUNTIME_VALIDATION_RESULTS.yaml# wave_c',full_execution_complete=False,session_closed=True,remediation_authority='Explicit attached user request; bounded Development-only override of observation-only mechanics',future_waves='NOT_EXECUTED',cep078079='NOT_EXECUTED'))
    (OUT/'DOCUMENTS_WRITTEN.json').write_text(json.dumps(dict(at=stamp,decision=summary['decision'],scenario_count=len(records),resolved_existing=list(resolved),new_findings=[f['finding_id'] for f in new_findings]),indent=2)+'\n')
    print('Canonical append complete: 12 scenario dispositions; 10 bounded existing retests; two new findings resolved; material execution blockers preserved')

if __name__=='__main__':main()
