"""Read-only exact source, receipt and scenario-mapping re-evaluation."""
import json
from pathlib import Path
import sys
from datetime import datetime
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,REAL_NOW
from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership
from apps.procurement.portal_services import get_supplier_portal_rfq_context
from apps.procurement.models import SupplierPortalSubmissionReceipt
import re

guard()
prior=OUT.parent/'CEP-078_REENTRY_03'
fixture=json.loads((prior/'PORTAL_FIXTURE.json').read_text(encoding='utf-8'))
actor=User.objects.get(username=fixture['external'])
receipt=SupplierPortalSubmissionReceipt.objects.select_related('grant','quote_revision').get(pk=fixture['receipt'])
context=get_supplier_portal_rfq_context(actor=actor,grant=receipt.grant)
assert str(receipt.grant_id)==fixture['grant'] and str(receipt.quote_revision_id)==fixture['quote_revision']
results=json.loads((prior/'SURFACE_RESULTS.json').read_text(encoding='utf-8'))
cells=[r for r in results if r['id']=='CEP078-R3-SURFACE-069']
latest={(r['family'],tuple(r['viewport'])):r for r in cells}
assert len(latest)==6 and all(r['result']=='PASS' for r in latest.values())
receipt_result={'at':REAL_NOW(),'result':'RESOLVED_CURRENT_REQUIRED_RECEIPT_COVERAGE_WITH_EXISTING_VALID_EVIDENCE','receipt':str(receipt.pk),'grant':str(receipt.grant_id),'quote_revision':str(receipt.quote_revision_id),'actor':actor.username,'non_member':not OrganizationMembership.objects.filter(user=actor).exists(),'canonical_current_read_guard':'get_supplier_portal_rfq_context PASS for exact receipt grant','source_rfq':fixture['rfq'],'current_source_purpose':context['title'],'retained_actual_cells':[{k:r[k] for k in ['at','family','viewport','result','capture']} for r in latest.values()],'historical_row067':'Original missing receipt404/FAIL/Edge unexecuted records remain unchanged. The required current receipt scenario is covered by separate actual069 evidence; original067 is not relabeled PASS.','new_fixture_or_browser_replay':'NONE_NEEDED; current service/read identity/source unchanged and existing six actual cells sufficient','no_mutation':True}
(OUT/'RECEIPT_RECONCILIATION.json').write_text(json.dumps(receipt_result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
catalogue=(ROOT/'docs/governance/uiux/UIUX_REFERENCE_PERSONA_CATALOGUE.yaml').read_text(encoding='utf-8')
catalog_rows=[]
for pid,body in re.findall(r'^- persona_id: (P-\d+)\n(.*?)(?=^- persona_id:|\Z)',catalogue,re.M|re.S):
    def scalar(key):
        m=re.search(r'^  '+key+r': (.*)$',body,re.M)
        return m.group(1).strip() if m else None
    aliases=[s for s in [scalar('reconciled_identity'),scalar('reference_username_target')] if s and s not in {'null','NONE'}]
    users=list(User.objects.filter(username__in=aliases).values('username','is_active','is_staff','is_superuser'))
    catalog_rows.append({'persona_id':pid,'catalogue_status':scalar('provisioning_status'),'documented_aliases':aliases,'existing_aliases':users})
assert len(catalog_rows)==26
mapping={'at':REAL_NOW(),'result':'SCENARIO_MAPPING_CORRECTION_NO_STAFF_ELEVATION','canonical_surface_rule':'Reference retention policy section4 permits equivalent existing user/access-management surface, not mandatory Django staff administration','canonical_staff_boundary':'CustomUserAdmin.has_view_permission additionally requires Django permissions and tenant management scope (or Superuser); has_add_permission false. PersianUserChangeForm explicitly excludes groups/user_permissions. No generic fixture mechanism may bypass that boundary.','existing_test_staff_candidates':[],'staff_admin_route':'Optional technical administration diagnostic; incorrectly substituted for Platform Admin in row093. Correct mapping preserves denial result and removes invented mandatory staff requirement, without deleting canonical SC033.','existing_equivalent_tenant_surface':'/organizations/members/ -> exact member authorization detail; P16 already legitimately authorized. Live browser check will identify its exact supported scope.','remaining_review':'Verify whether all defined/provisioned reference aliases, including non-member external/platform identities, are discoverable through existing qualified surfaces; no new role/capability/catalogue implied.','catalogue_entries':catalog_rows,'writes':False}
(OUT/'SC033_MAPPING.json').write_text(json.dumps(mapping,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Receipt current service guard and six retained actual cells PASS; all26 catalogue entries retained; staff mapping corrected without new grants.')
