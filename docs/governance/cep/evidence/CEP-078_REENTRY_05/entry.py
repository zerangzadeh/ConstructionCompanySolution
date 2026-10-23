"""Ground the final bounded CEP078 gap closure and inventory existing authority."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
os.environ['GIT_OPTIONAL_LOCKS']='0'
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,snapshot,REAL_NOW
from apps.accounts.models import User
from apps.organizations.models import PlatformPolicyVersion,Organization
from apps.billing.models import ProgressClaim,ProjectBaseline
from apps.contracts.models import ContractTermVersion
from apps.billing.services import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,value):(OUT/name).write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
guard()
assert not (OUT/'ENTRY.json').exists()
prior=json.loads((OUT.parent/'CEP-078_REENTRY_04/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/p)==v for p,v in prior['product_hashes'].items())
assert git('rev-parse','HEAD')==prior['head']==git('rev-parse','origin/main')
assert git('branch','--show-current')=='main' and git('diff','--cached','--name-only')==''
assert sha(ROOT/'docs/governance/cep/PROMPTS/CEP-078_EXECUTION_PROMPT.md')=='313eb92ea69db33fe2ccaa6d881a6346949286aa8d9c688ac87dd820b0e92030'
save('ENTRY.json',{'at':REAL_NOW(),'head':prior['head'],'branch':'main','upstream':git('rev-parse','@{u}'),'origin_main':git('rev-parse','origin/main'),'status':git('status','--short'),'diff_name_status':git('diff','--name-status'),'diff_stat':git('diff','--stat'),'index_sha256':sha(ROOT/'.git/index'),'product_hashes':prior['product_hashes'],'prior_evidence':{p.relative_to(ROOT).as_posix():sha(p) for i in range(1,5) for p in (OUT.parent/f'CEP-078_REENTRY_0{i}').rglob('*') if p.is_file() and '__pycache__' not in p.parts},'registry_before':(ROOT/'CEP_EXECUTION_REGISTRY.yaml').read_text(encoding='utf-8'),'registry_raw_sha256':sha(ROOT/'CEP_EXECUTION_REGISTRY.yaml'),'authority':'Direct Human continuation through final supported CEP078 reconciliation; minimal isolated canonical Development fixtures and bounded ordinary technical remediation; no new policy-role-permission-behavior; no CEP079-Production-HumanSignoff-Git writes','touch_set':['this evidence directory','bounded CEP078 Registry state/history/counts/frontier','minimal actually demonstrated technical UI source/test repairs if necessary'],'accepted_tests':'53/54 distinct PASS; one unchanged NAV019 baseline failure; no duplicate rerun','accepted_runtime':'60/60 cells408 assertions PASS in REENTRY04, prior surface/login/portal evidence retained'})
save('DATA_BEFORE.json',snapshot())
custody=Path(os.environ['LOCALAPPDATA'])/'BONIRA/UIUXRuntimeAudit/credentials'
staff=[]
for u in User.objects.filter(is_staff=True,is_active=True):
    test_actor=bool(re.search(r'admin|uiux|test|demo|root',u.username,re.I))
    staff.append({'alias':u.username if test_actor else 'NON_TEST_ACTOR_REDACTED','id':str(u.pk) if test_actor else None,'is_staff':True,'is_superuser':u.is_superuser,'canonical_test_candidate':test_actor,'local_credential_available':(custody/(u.username+'.clixml')).is_file() if test_actor else False})
org=Organization.objects.get(slug='demo-construction-01')
save('SOURCE_AND_ACTOR_REVIEW.json',{'at':REAL_NOW(),'staff_candidates':staff,'platform_actor':list(User.objects.filter(username='admin').values('username','is_staff','is_superuser','is_active')),'billing':{'claims_in_target_tenant':list(ProgressClaim.objects.filter(organization=org).values_list('pk',flat=True)),'all_tenant_claim_count':ProgressClaim.objects.count(),'approved_baselines':list(ProjectBaseline.objects.filter(organization=org,status='approved').values_list('pk',flat=True)),'term_versions':list(ContractTermVersion.objects.filter(organization=org).values('pk','contract_id','status','effective_from')),'relevant_global_regulatory_versions':list(PlatformPolicyVersion.objects.filter(policy__code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE).values('pk','status','effective_from'))},'writes':False,'new_staff_or_superuser_authority':False})
print('Entry PASS:1497 final sources unchanged; existing staff candidates:',[(s['alias'],s['local_credential_available']) for s in staff])
