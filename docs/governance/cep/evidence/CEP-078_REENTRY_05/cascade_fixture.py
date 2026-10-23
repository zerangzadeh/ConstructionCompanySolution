"""Minimal isolated canonical fixture for actual stale-form authorization errors."""
import json
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import timedelta
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard,REAL_NOW
from django.db import transaction
from apps.accounts.models import User
from apps.accounts.services import initialize_personal_password
from apps.organizations.models import Organization,OrganizationRole,OrganizationMembership
from apps.organizations.services import create_organization_account
from apps.organizations.access_services import assign_membership_role,grant_membership_scope,revoke_membership_role,revoke_membership_scope
from apps.organizations.authorization import membership_permission_codes,effective_scope_grants

guard()
org=Organization.objects.get(slug='demo-construction-01')
actor=User.objects.get(username='account.demo-construction-01.owner')
approver=OrganizationMembership.objects.get(organization=org,user__username='uiux.persona.tenant-admin')
reason='CEP078_UIUX_TEST_ONLY_NON_AUTHORITATIVE; isolated Development stale-form error-state validation; existing operations_manager is smallest canonical role containing expenses.create and estimates.create; organization scope required by existing form-entry decorators; no real or accepted authority change'
phase=sys.argv[1]
def save(n,v):(OUT/n).write_text(json.dumps(v,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if phase=='prepare':
    assert not (OUT/'CASCADE_FIXTURE.json').exists()
    alias='cep078.synthetic.cascade-errors'
    assert not User.objects.filter(username=alias).exists()
    role=OrganizationRole.objects.get(code='operations_manager',is_active=True,organization__isnull=True)
    at=REAL_NOW()
    with transaction.atomic():
        password=secrets.token_urlsafe(32)
        user,member=create_organization_account(organization=org,actor=actor,username=alias,temporary_password=secrets.token_urlsafe(32),role=role,first_name='آزمون خطای فرم',last_name='UIUX_TEST_ONLY_NON_AUTHORITATIVE')
        assignment=assign_membership_role(organization=org,actor=actor,membership_id=member.pk,role=role,approver_membership_id=approver.pk,reason=reason,ends_at=at+timedelta(hours=1))
        grant=grant_membership_scope(organization=org,actor=actor,membership_id=member.pk,scope_type='organization',approver_membership_id=approver.pk,reason=reason,ends_at=at+timedelta(hours=1))
        initialize_personal_password(user=user,new_password=password)
        command="$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
        subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',command],input=json.dumps({'alias':alias,'password':password}),text=True,capture_output=True,check=True)
        del password
    save('CASCADE_FIXTURE.json',{'at':at,'alias':alias,'membership':member.pk,'role_assignment':assignment.pk,'scope_grant':grant.pk,'ends_at':at+timedelta(hours=1),'authority':'Current explicit Human isolated canonical Development fixture authority','minimum_available_role':role.code,'permission_count':role.permissions.filter(is_active=True).count(),'no_new_roles_permissions_semantics':True,'existing_records_preserved':True,'business_records_created':0,'reason':reason,'credential':'Current-user DPAPI custody only; no reset or evidence secret','lifecycle':'Load four actual browser forms while authorized, revoke only this new synthetic role canonically, observe actual403 error UI without request interception/DOM injection, then revoke synthetic scope; retain identity/audit provenance'})
else:
    data=json.loads((OUT/'CASCADE_FIXTURE.json').read_text(encoding='utf-8'))
    member=OrganizationMembership.objects.get(pk=data['membership'],organization=org)
    with transaction.atomic():
        revoke_membership_role(organization=org,actor=actor,assignment_id=data['role_assignment'],approver_membership_id=approver.pk,reason=reason+'; authorized isolated test role revocation')
        assert not membership_permission_codes(member)
        if phase=='cleanup':
            revoke_membership_scope(organization=org,actor=actor,grant_id=data['scope_grant'],approver_membership_id=approver.pk,reason=reason+'; final isolated test scope cleanup')
            assert not effective_scope_grants(member).exists()
    save('CASCADE_ROLE_REVOKED.json' if phase=='revoke' else 'CASCADE_CLEANUP.json',{'at':REAL_NOW(),'alias':member.user.username,'phase':phase,'effective_permissions':sorted(membership_permission_codes(member)),'effective_scope_count':effective_scope_grants(member).count(),'result':'PASS','method':'Existing audited services and independent existing approver; no direct database writes'})
print('Canonical isolated cascade fixture phase:',phase,'PASS; no business record or existing authority changes')
