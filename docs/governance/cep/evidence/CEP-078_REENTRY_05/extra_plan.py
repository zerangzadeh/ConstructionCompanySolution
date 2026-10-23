"""Keep only previously unobserved approved-route/state cells in the delta plan."""
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from apps.contracts.models import Contract
from apps.billing.models import ProjectBaseline
from django.urls import reverse
guard()
prior=json.loads((OUT.parent/'CEP-078_REENTRY_03/EXTENDED_BROWSER_PLAN.json').read_text(encoding='utf-8'))['rows']
seen={(r['actor'],r['path']) for r in prior}
rows=[]
def add(actor,scenarios,paths):
    for path in paths:
        if (actor,path) not in seen:
            rows.append({'id':f'CEP078-R5-DELTA-{len(rows)+1:03d}','actor':actor,'scenarios':scenarios,'path':path,'viewports':[[1440,900],[1024,768],[390,844]],'scope':'Previously unobserved approved GET state; no domain transition or business submission'})
for actor in ('uiux.persona.tenant-admin','account.demo-construction-01.owner'):
    add(actor,[26],['/organizations/settings/','/organizations/configuration-profiles/'])
add('admin',[27],['/organizations/platform/protected-operations/','/organizations/platform/accounting-policies/','/organizations/'])
doc='ca7ca134-a6e5-4a5c-8bd5-68e3b56a9251'
add('uiux.wavec.documents',[28],['/documents/mine/','/documents/upload/'])
baseline=ProjectBaseline.objects.select_related('contract').filter(organization__slug='demo-construction-01',contract__project__code='PRJ-01-01',status='approved').order_by('pk').first()
assert baseline is not None
contract=baseline.contract
add('uiux.wavec.commercial',[30],[reverse('contracts:detail',kwargs={'contract_id':contract.pk}),reverse('contracts:commercial_review',kwargs={'contract_id':contract.pk})])
(OUT/'POST_ENDPOINT_RECONCILIATION.json').write_text(json.dumps({'scope_unchanged':True,'source':'Current views.py require_POST / request.method checks','action_routes_not_get_screens':[f'/documents/{doc}/versions/add/',f'/documents/{doc}/links/add/','/commercial/571c67f4-2796-4487-9207-4793f0c83a75/revise/','/commercial/571c67f4-2796-4487-9207-4793f0c83a75/evidence/'],'runtime_surface':'Existing actual document/tender detail and inline forms, already measured in REENTRY03; source actions unchanged','disposition':'No GET405 misclassified as product failure; no business POST or duplicate metadata render required'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'DELTA_PLAN.json').write_text(json.dumps({'basis':'Unchanged33 approved scenario blocks; exact current named routes and retained data; subtraction of already observed actor/routes','rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Previously unobserved approved GET routes:',len(rows),'per browser; no replay of accepted93-surface sweep')
