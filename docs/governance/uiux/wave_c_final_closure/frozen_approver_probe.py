"""Exact unchanged legacy-approver input under the immutable HEAD implementation."""
import json,os,sys
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'docs/governance/uiux/wave_c_final_closure'
from dotenv import load_dotenv
load_dotenv(ROOT/'.env');os.environ['DB_NAME']='test_bonira_uiux_batch09';os.environ['DJANGO_SETTINGS_MODULE']='config.settings.development'
frozen=Path(json.loads((OUT/'FROZEN_SOURCE.json').read_text())['path']);sys.path.insert(0,str(frozen));os.chdir(frozen)
import django;django.setup()
from django.conf import settings
from django.db import connection,transaction
from django.core.exceptions import PermissionDenied
from apps.accounts.models import User
from apps.organizations.models import Organization,OrganizationMembership,MembershipRole,MembershipStatus,BusinessPermissionCode
from apps.organizations.authorization import require_business_permission
assert connection.settings_dict['NAME']=='test_bonira_uiux_batch09' and settings.DEBUG
with transaction.atomic():
 org=Organization.objects.create(name='Frozen baseline probe',slug='wc-frozen-approver-probe')
 user=User.objects.create_user(username='wc-frozen-approver-probe')
 member=OrganizationMembership.objects.create(organization=org,user=user,role=MembershipRole.COMPANY_OWNER,status=MembershipStatus.ACTIVE)
 denied=False
 try:require_business_permission(user=user,organization=org,permission=BusinessPermissionCode.INVOICE_MATCH_POLICIES_APPROVE,message='Frozen baseline approver',allow_any_scope=True)
 except PermissionDenied:denied=True
 assert denied and member.scope_grants.count()==0
 data={'implementation':'Immutable HEAD export','head':json.loads((OUT/'FROZEN_SOURCE.json').read_text())['head'],'guard_module':str(sys.modules['apps.organizations.authorization'].__file__),'isolated_test_database':True,'fixture_input':'Exact P5S26S27MatchReviewTests.setUp approver: legacy owner string; active; no explicit role/scope evidence','role_definition_is_null':member.role_definition_id is None,'scope_grants':0,'permission':str(BusinessPermissionCode.INVOICE_MATCH_POLICIES_APPROVE),'result':'PermissionDenied','transaction_rolled_back':True,'source_proof':'SOURCE_ATTRIBUTION.json: fixture and authorization functions unchanged; Owner/Admin permission sets unchanged in authorization_reconciliation/MATRIX_SUMMARY.json'}
 transaction.set_rollback(True)
(OUT/'FROZEN_APPROVER_PROBE.json').write_text(json.dumps(data,indent=2)+'\n')
print('Frozen exact approver input: policy approval denied; no role/scope evidence. Probe rolled back.')
