"""No financial writes: establish required populated claim provenance."""
import sys,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from django.utils import timezone
from apps.organizations.models import Organization,PlatformPolicyVersion
from apps.billing.models import ProgressClaim,ProjectBaseline
from apps.contracts.models import ContractTermVersion
from apps.billing.services import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
guard()
org=Organization.objects.get(slug='demo-construction-01')
base=ProjectBaseline.objects.filter(organization=org,status='approved')
contract_ids=list(base.values_list('contract_id',flat=True))
terms=list(ContractTermVersion.objects.filter(organization=org,contract_id__in=contract_ids).values('id','contract_id','status','effective_from'))
policy=list(PlatformPolicyVersion.objects.filter(policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE).values('id','status','effective_from'))
result={'at':timezone.now(),'scenario':'CEP-078-SC-014 populated claim detail','claims':list(ProgressClaim.objects.filter(organization=org).values_list('id',flat=True)),'approved_baselines':list(base.values_list('id',flat=True)),'contract_term_versions':terms,'regulatory_policy_code':RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,'regulatory_versions':policy,'no_mutation':True,'rule':'No statutory/commercial policy, values or owner approvals may be invented to create verification evidence. Empty list and preparation forms do not prove populated claim detail.'}
(OUT/'BILLING_STATE.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'claims':len(result['claims']),'approved_baselines':len(result['approved_baselines']),'term_versions':len(terms),'regulatory_versions':len(policy),'code':RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE}))
