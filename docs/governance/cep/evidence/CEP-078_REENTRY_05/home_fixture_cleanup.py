"""Canonical cleanup of this continuation's disposable membership, after two logins."""
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,REAL_NOW
from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership,MembershipStatus
from apps.organizations.services import update_organization_membership
guard()
data=json.loads((OUT/'CASCADE_FIXTURE.json').read_text(encoding='utf-8'))
member=OrganizationMembership.objects.select_related('organization','role_definition').get(pk=data['membership'])
assert not member.role_assignments.filter(revoked_at__isnull=True).exists()
assert not member.scope_grants.filter(revoked_at__isnull=True).exists()
assert member.user.username=='cep078.synthetic.cascade-errors'
result=update_organization_membership(organization=member.organization,actor=User.objects.get(username='account.demo-construction-01.owner'),membership=member,role=member.role_definition,status=MembershipStatus.REVOKED)
(OUT/'HOME_FIXTURE_CLEANUP.json').write_text(json.dumps({'at':REAL_NOW(),'membership':str(result.pk),'status':result.status,'method':'Existing update_organization_membership; only isolated new test membership, original role definition unchanged; no grants/elevation. Two existing authenticated synthetic sessions now naturally carry an invalidated selection for first-request unauthorized Home rendering.','result':'PASS'},default=str,indent=2)+'\n',encoding='utf-8')
print('New isolated membership canonically revoked; prior memberships unchanged')
