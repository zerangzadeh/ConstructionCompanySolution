"""Existing cross-module accessibility role, canonical initial-grant service only."""
import sys
import json
import secrets
import subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from django.apps import apps
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.services import initialize_personal_password
from apps.organizations.models import Organization,OrganizationRole,OrganizationMembership
from apps.organizations.services import create_organization_account
from apps.organizations.platform_grants import platform_initial_grant
from apps.organizations.authorization import membership_permission_codes,effective_scope_grants
from apps.projects.models import Project

guard()
assert not (OUT/'ACCESSIBILITY_FIXTURE.json').exists()
org=Organization.objects.get(slug='demo-construction-01')
owner=User.objects.get(username='account.demo-construction-01.owner')
platform=User.objects.get(username='admin')
project=Project.objects.get(organization=org,code='PRJ-01-01')
role=OrganizationRole.objects.get(code='uiux_runtime_reporting_test',is_active=True)
assert role.organization_id in (None,org.pk)
alias='cep078.synthetic.accessibility'
reason='CEP078_SYNTHETIC_DEVELOPMENT_ONLY; explicit Human positive-state fixture authority; existing approved cross-module UIUX runtime reporting role, same role definition22 codes; exact projectA only; no lawful tenant delegator, guarded existing Platform Initial Grant service; no existing persona authority edit'
existing=User.objects.filter(username=alias).first()
if existing:
    user=existing
    m=OrganizationMembership.objects.get(organization=org,user=user)
    assignment=m.role_assignments.get(role=role,source='platform_initial_grant',reason=reason,revoked_at__isnull=True)
    grant=m.scope_grants.get(source='platform_initial_grant',project=project,scope_type='project',revoked_at__isnull=True)
    assert set(membership_permission_codes(m))==set(role.permissions.filter(is_active=True).values_list('code',flat=True))
    assert not user.must_change_password
else:
    with transaction.atomic():
        secret=secrets.token_urlsafe(32)
        user,m=create_organization_account(organization=org,actor=owner,username=alias,temporary_password=secrets.token_urlsafe(32),role=role,first_name='آزمون دسترس‌پذیری',last_name='فقط توسعه CEP078')
        assignment,grant=platform_initial_grant(organization=org,actor=platform,membership_id=m.pk,role=role,scope_type='project',project=project,reason=reason)
        initialize_personal_password(user=user,new_password=secret)
        program="$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
        subprocess.run(['pwsh','-NoProfile','-NonInteractive','-Command',program],input=json.dumps({'alias':alias,'password':secret}),text=True,capture_output=True,check=True)
        del secret
states={}
for label in ['reporting.ProjectCloseoutCase','reporting.ProjectCloseoutProfileVersion','billing.ProgressClaim']:
    model=apps.get_model(label)
    records=model.objects.filter(organization=org) if label!='reporting.ProjectCloseoutProfileVersion' else model.objects.all()
    names={f.name for f in model._meta.concrete_fields}
    columns=[n for n in ['id','status','project_id','profile_version_id'] if n in names or n.endswith('_id') and n[:-3] in names]
    states[label]=list(records.values(*columns))
result={'at':timezone.now(),'alias':alias,'user':user.pk,'membership':m.pk,'organization':org.pk,'role':role.pk,'role_code':role.code,'permissions':sorted(membership_permission_codes(m)),'assignment':assignment.pk,'grant':grant.pk,'scopes':list(effective_scope_grants(m).values('scope_type','project_id','site_id')),'mechanism':'create_organization_account + existing platform_initial_grant; its guards proved no lawful ordinary delegator, active explicit Platform authority, registered approved role and exact receiver scope','existing_roles_rules_unchanged':True,'existing_quarantined_reporting_persona':'Retained unchanged; still negative evidence','credential':'current-user DPAPI only','retention':'Retain synthetic identity/audit history; revoke its test role/scope canonically after verification, no deletion','states':states}
(OUT/'ACCESSIBILITY_FIXTURE.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Project-scoped accessibility identity ready through existing guarded mechanism; current case/profile/claim states recorded')
