"""Read-only missing scenario state and current authorization evidence."""
import sys
import json
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0,str(ROOT / 'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from apps.accounts.models import User
from apps.organizations.models import OrganizationMembership, OrganizationRole, Organization
from apps.organizations.authorization import membership_permission_codes, effective_role_assignments, effective_scope_grants
from apps.procurement.models import SupplierPortalGrant, SupplierPortalSubmissionReceipt
from django.utils import timezone

guard()
def save(name,value):
    (OUT/name).write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
aliases=['account.demo-construction-01.accountant','uiux.persona.treasury','uiux.persona.project-operations','uiux.wavec.controls','uiux.wavec.buyer','uiux.audit.reporting','uiux.audit.empty']
rows=[]
for alias in aliases:
    user=User.objects.get(username=alias)
    memberships=[]
    for m in OrganizationMembership.objects.filter(user=user).select_related('organization'):
        memberships.append({'organization':m.organization.slug,'status':m.status,'roles':list(effective_role_assignments(m).values_list('role__code',flat=True)),'permissions':sorted(membership_permission_codes(m)),'scopes':list(effective_scope_grants(m).values('scope_type','project_id','site_id'))})
    rows.append({'alias':alias,'active':user.is_active,'memberships':memberships})
external=User.objects.get(username='uiux.wcd.external')
grants=[]
for g in SupplierPortalGrant.objects.filter(principal__user=external).select_related('portal_invitation'):
    grants.append({'id':g.pk,'organization':g.organization_id,'expires_at':g.portal_invitation.expires_at,'expired':g.portal_invitation.expires_at<=timezone.now(),'receipts':list(SupplierPortalSubmissionReceipt.objects.filter(grant=g).values_list('id',flat=True))})
save('STATE_READINESS.json',{'at':timezone.now(),'actors':rows,'external_memberships':OrganizationMembership.objects.filter(user=external).count(),'external_grants':grants,'no_writes':True})
org=Organization.objects.get(slug='demo-construction-01')
owner=OrganizationMembership.objects.get(organization=org,user__username='account.demo-construction-01.owner')
owner_codes=membership_permission_codes(owner)
roles=[]
for r in OrganizationRole.objects.filter(is_active=True):
    if r.organization_id not in (None,org.pk):continue
    codes=set(r.permissions.filter(is_active=True).values_list('code',flat=True))
    roles.append({'id':r.pk,'code':r.code,'organization':r.organization_id,'permissions':sorted(codes),'owner_can_delegate_all_codes':codes<=owner_codes,'missing_delegator_codes':sorted(codes-owner_codes)})
save('ROLE_INVENTORY.json',{'at':timezone.now(),'roles':roles,'no_role_definition_changes':True})
print('Read-only current role/state review saved')
