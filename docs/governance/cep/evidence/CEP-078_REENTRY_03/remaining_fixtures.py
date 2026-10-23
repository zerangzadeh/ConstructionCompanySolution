"""Minimal labeled browser evidence fixtures; canonical services, no real record edits."""
import sys
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
sys.path.insert(0,str(ROOT/'docs/governance/uiux/rv007_controlled_time'))
from support import guard
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.organizations.models import Organization,OrganizationMembership
from apps.organizations.access_services import grant_membership_scope
from apps.projects.models import Project,ProjectStatus
from apps.projects.services import create_project
from apps.reporting.project_closeout import create_closeout_case
from apps.reporting.models import ProjectCloseoutProfileVersion
from apps.billing.models import ProjectBaseline,TenantBillingConfiguration,ProgressClaim

guard()
assert not (OUT/'REMAINING_FIXTURES.json').exists()
org=Organization.objects.get(slug='demo-construction-01')
operator=User.objects.get(username='cep078.synthetic.operations')
keyboard=User.objects.get(username='cep078.synthetic.accessibility')
owner=User.objects.get(username='account.demo-construction-01.owner')
approver=OrganizationMembership.objects.get(organization=org,user__username='admin')
member=OrganizationMembership.objects.get(organization=org,user=keyboard)
profiles=list(ProjectCloseoutProfileVersion.objects.filter(status='published'))
assert len(profiles)==1
before=list(Project.objects.filter(organization=org).values('id','status','code'))
# Per-page25 is fixed by the actual shared contract. Filter planning + name sort
# requires26 rows. Reuse existing planning rows; append only the shortfall.
planning=Project.objects.filter(organization=org,status=ProjectStatus.PLANNING).count()
needed=max(0,26-planning)
created=[]
with transaction.atomic():
    for n in range(1,needed+1):
        p=create_project(organization=org,actor=operator,code=f'CEP078-FIX-PAG-{n:02d}',name=f'آزمون ساختگی CEP078 فقط توسعه {n:02d}',description='CEP078_SYNTHETIC_RUNTIME_ONLY; pagination evidence; canonical planning/zero-budget defaults; no financial activity')
        created.append(p)
    target=created[0]
    scope=grant_membership_scope(organization=org,actor=owner,membership_id=member.pk,scope_type='project',project=target,approver_membership_id=approver.pk,reason='CEP078 isolated synthetic case accessibility only; existing target role, minimum new synthetic project scope; no real-project authority edit')
    case=create_closeout_case(organization=org,actor=keyboard,project=target,operation_key='CEP078_SYNTHETIC_RUNTIME_CASE_01')
after=list(Project.objects.filter(pk__in=[p['id'] for p in before]).values('id','status','code'))
assert {str(p['id']):(p['status'],p['code']) for p in before}=={str(p['id']):(p['status'],p['code']) for p in after}
result={'at':timezone.now(),'authority':'Direct Human CEP078 positive-fixture preparation; existing roles/scopes/lifecycles and canonical defaults only; no rule/policy change','purpose':'SC023 real filtered/sorted page2 and SC024 actual case-detail accessibility; smallest current row shortfall','per_page':25,'existing_planning_count':planning,'created_project_count':len(created),'project_ids':[p.pk for p in created],'prefix':'CEP078-FIX-PAG-','service':'create_project; defaults planning, no dates, zero budgets; no financial transaction or financial policy selected','case':case.pk,'case_project':target.pk,'case_status':case.status,'scope_grant':scope.pk,'case_profile':profiles[0].pk,'profile_governance_reference':profiles[0].governance_reference,'published_profile_not_modified':True,'no_assessment_acceptance_or_project_lifecycle_transition':True,'existing_projects_unchanged':True,'baseline_rows':list(ProjectBaseline.objects.filter(organization=org).values('id','status','effective_date','contract_id')),'billing_config_exists':TenantBillingConfiguration.objects.filter(organization=org).exists(),'claims':list(ProgressClaim.objects.filter(organization=org).values_list('id',flat=True)),'retention':'Retain labeled synthetic projects/case and append-only audit provenance for reproducible evidence. No hard deletion/real records/Production action; synthetic test authority cleaned up canonically after verification.'}
(OUT/'REMAINING_FIXTURES.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Minimum pagination/case fixtures ready; existing projects/profile untouched; no claim or financial record fabricated')
