"""Machine-check Wave C evidence without promoting blocked journeys to PASS."""
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]

def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))

def main():
    before=read('baseline_HTTP.json')
    after=read('after_HTTP.json')
    assert len(before)==len(after)==165
    assert [(r['actor'],r['method'],r['path'],r['status']) for r in before]==[(r['actor'],r['method'],r['path'],r['status']) for r in after]
    assert {r['scenario'] for r in after}=={'RV-007','RV-009','RV-011','RV-013','RV-015','RV-017','RV-018','RV-028','RV-029','RV-030','RV-031','RV-032'}
    fixtures=read('FIXTURES.json')
    metadata=[]
    for r in after:
        body=html.unescape((OUT/r['html']).read_text(encoding='utf-8'))
        if r['scenario']=='RV-007' and ('scope C' in r['case'] or 'scope X' in r['case'] or 'POST C' in r['case'] or 'POST X' in r['case']):
            assert r['status'] in (403,404)
            assert all(fixtures['rfqs'][k]['number'] not in body for k in ('C','X'))
            metadata.append(dict(path=r['path'],status=r['status'],protected_rfq_metadata_absent=True))
        if r['scenario']=='RV-028' and ('scope C' in r['case'] or 'scope X' in r['case'] or 'POST C' in r['case'] or 'POST X' in r['case']):
            assert r['status'] in (403,404)
            assert not any(x in body for x in ('BATCH_02_RUNTIME_CLOSURE_FIXTURE C','BATCH_02_RUNTIME_CLOSURE_FIXTURE X'))
            metadata.append(dict(path=r['path'],status=r['status'],protected_document_metadata_absent=True))
    browsers=read('final_BROWSER.json')
    assert len(browsers)==20
    assert all(r['metrics']['mains']==1 and not r['mobile']['overflow'] for r in browsers)
    assert not any(r['metrics']['technicalText'] for r in browsers)
    inventory=[r for r in browsers if r['actor']=='uiux.persona.inventory']
    assert len(inventory)==3 and all(r['status']==200 for r in inventory)
    assert 'نتایج تطبیق ارزش‌گذاری' not in inventory[2]['metrics']['headings']
    statement=browsers[-1]
    assert statement['metrics']['details']==[{'summary':'ردیابی و ممیزی','open':False}]
    assert any('پیش‌نمایش تراز آزمایشی' in r['metrics']['headings'] for r in browsers)
    for r in browsers:
        for image in r['screenshots']:
            assert (OUT/image).stat().st_size>1000
    services=read('DIRECT_SERVICE.json')
    assert len(services)==20
    assert all(r['persisted_delta']==0 for r in services)
    assert all(r['result']=='DENIED' for r in services if 'portal invitation' in r['case'])
    integrity=read('INTEGRITY.json')
    assert integrity['preexisting_rows_changed']==[]
    assert integrity['unauthorized_business_mutations']==0
    changed=[n for n,h in read('FILES_BEFORE.json').items() if not (ROOT/n).exists() or hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h]
    allowed=read('TOUCH_SET.json')['product']+['docs/governance/uiux/'+n for n in ('UIUX_FINDINGS_REGISTER.yaml','UIUX_ROOT_PATTERN_IMPACT_MAP.yaml','UIUX_RUNTIME_VALIDATION_RESULTS.yaml','UIUX_RUNTIME_VALIDATION_MATRIX.yaml')]
    assert set(changed)<=set(allowed),changed
    result=dict(http_observations=len(after),http_statuses=Counter(r['status'] for r in after),http_by_scenario=Counter(r['scenario'] for r in after),same_authority_and_tenant_denials_preserved=True,metadata_controls=metadata,delta_http=len(read('DELTA_HTTP.json')),direct_services=len(services),browser_observations=len(browsers),screenshots=sum(len(r['screenshots']) for r in browsers),viewports=[[1440,900],[390,844]],browser=browsers[0]['browser'],all_captured_pages_single_main=True,no_page_overflow_observed=True,source_preservation_changed_only_within_touch_set=changed,integrity='INTEGRITY.json',assertions='PASS',scope_limit='Each scenario has a disposition; specialist/policy-blocked subtargets are not executed or passed. This evidence cannot establish complete Wave C execution.')
    (OUT/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Wave C evidence assertions PASS; 12 scenarios represented; no completion claim for blocked journeys')

if __name__=='__main__':main()
