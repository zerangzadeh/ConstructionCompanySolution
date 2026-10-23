"""Isolated positive-state fixture using an existing canonical role and scope API."""
import sys
import json
import secrets
import subprocess
from datetime import timedelta
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.services import initialize_personal_password
from apps.organizations.models import Organization, OrganizationRole, OrganizationMembership
from apps.organizations.services import create_organization_account
from apps.organizations.access_services import assign_membership_role, grant_membership_scope
from apps.organizations.authorization import membership_permission_codes, effective_scope_grants

guard()
assert not (OUT/'PERSONA_FIXTURE.json').exists()
org=Organization.objects.get(slug='demo-construction-01')
owner=User.objects.get(username='account.demo-construction-01.owner')
approver=OrganizationMembership.objects.get(organization=org,user__username='admin')
role=OrganizationRole.objects.get(code='operations_manager',organization__isnull=True,is_active=True)
role_codes=sorted(role.permissions.filter(is_active=True).values_list('code',flat=True))
existing_role_ids=list(OrganizationRole.objects.values_list('id',flat=True))
alias='cep078.synthetic.operations'
assert not User.objects.filter(username=alias).exists()
now=timezone.now()
reason='CEP078_SYNTHETIC_DEVELOPMENT_ONLY; explicit Human fixture authority; current organization-permission decorators require organization scope for these aggregate workbenches and form-entry routes; existing operations_manager is minimum available canonical role spanning these operations; no real identity authority edit'
with transaction.atomic():
    password=secrets.token_urlsafe(32)
    user,membership=create_organization_account(organization=org,actor=owner,username=alias,temporary_password=secrets.token_urlsafe(32),role=role,first_name='آزمون مصنوعی',last_name='فقط توسعه CEP078')
    assignment=assign_membership_role(organization=org,actor=owner,membership_id=membership.pk,role=role,approver_membership_id=approver.pk,reason=reason,ends_at=now+timedelta(hours=6))
    grant=grant_membership_scope(organization=org,actor=owner,membership_id=membership.pk,scope_type='organization',approver_membership_id=approver.pk,reason=reason,ends_at=now+timedelta(hours=6))
    initialize_personal_password(user=user,new_password=password)
    assert set(role_codes)==membership_permission_codes(membership)
    command="$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
    subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',command],input=json.dumps({'alias':alias,'password':password}),text=True,capture_output=True,check=True)
    del password
assert existing_role_ids==list(OrganizationRole.objects.values_list('id',flat=True))
value={'at':now,'authorization':'Direct Human positive-state fixture instruction 2026-10-23','alias':alias,'organization':org.slug,'user':user.pk,'membership':membership.pk,'role_code':role.code,'role':role.pk,'permissions':role_codes,'role_assignment':assignment.pk,'scope_grant':grant.pk,'scope':list(effective_scope_grants(membership).values('scope_type','project_id','site_id')),'ends_at':now+timedelta(hours=6),'purpose':'P-02 operational forms; P-03 PO preparation; P-04 Equipment/Fleet; P-07 Billing presentation using existing operations authority; exact functional perspective recorded per capture','minimum_scope_basis':reason,'new_roles_permissions':False,'existing_user_authority_changed':False,'credentials':'Existing current-user DPAPI store only; no secret retained in evidence','retention':'Retain labeled synthetic test identity and immutable audit provenance; role/scope authority expires naturally after six hours, no deleting persistent reference personas'}
(OUT/'PERSONA_FIXTURE.json').write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Existing-role isolated Development identity ready; six-hour authority; no real-user/role-definition changes')
