import os,sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.core.management import call_command
from apps.organizations.models import BusinessPermission,OrganizationRole,MembershipRoleAssignment,MembershipScopeGrant
from apps.workflows.models import WorkflowType,WorkflowDefinition
assert settings.SETTINGS_MODULE=='config.settings.development'
assert connection.vendor=='postgresql' and connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1')
new={'EmploymentRecord','OffboardingCase','OffboardingReview','RosterVersion','RosterSlot'}
source=[m for label in ('workforce','timekeeping','documents') for m in apps.get_app_config(label).get_models() if m.__name__ not in new]
source += [MembershipRoleAssignment,MembershipScopeGrant,OrganizationRole.permissions.through]
codes=['employment_records.manage','employment_records.view_own','offboarding.start','offboarding.view','offboarding.review','rosters.manage','rosters.view']
def snapshot():
 out={}
 for m in source:
  rows=list(m._base_manager.order_by('pk').values())
  out[m._meta.label]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
 return out
before=snapshot()
catalog_before=list(BusinessPermission.objects.exclude(code__in=codes).order_by('pk').values('id','code','name','description','is_active','created_at'))
targets=[('workforce','0013_cep022_employment_lifecycle'),('timekeeping','0003_cep022_employment_lifecycle'),('organizations','0115_cep022_employment_permissions')]
plan=MigrationExecutor(connection).migration_plan(targets)
assert all((m.app_label,m.name) in targets and not backwards for m,backwards in plan)
print('Verified targeted plan:',[(m.app_label,m.name) for m,_ in plan])
call_command('migrate','workforce','0013_cep022_employment_lifecycle',verbosity=1)
call_command('migrate','timekeeping','0003_cep022_employment_lifecycle',verbosity=1)
after=snapshot();assert before==after
assert catalog_before==list(BusinessPermission.objects.exclude(code__in=codes).order_by('pk').values('id','code','name','description','is_active','created_at'))
assert not OrganizationRole.permissions.through.objects.filter(businesspermission__code__in=codes).exists()
assert BusinessPermission.objects.filter(code__in=codes,is_active=True).count()==7
assert not WorkflowDefinition.objects.filter(workflow_type__code='workforce.offboarding').exists()
for name in new:
 model=next(m for m in apps.get_models() if m.__name__==name);assert not model.objects.exists()
result={'environment':'verified_configured_local_development_postgresql','targeted_plan':[(m.app_label,m.name) for m,_ in plan], 'source_before':before,'source_after':after,'unchanged':True,'existing_permission_catalog_unchanged_except_bootstrap_timestamps':True,'new_capability_grants':0,'new_source_records':0,'default_offboarding_definitions':0,'other_pending_migrations':'Projects0010 and Treasury0009 NOT EXECUTED'}
Path('docs/governance/cep/evidence/CEP-022_DEVELOPMENT_RECONCILIATION.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Reconciliation PASS; existing Workforce/Timekeeping/DMS and role grants unchanged; seven capabilities, zero grants/default workflows/new source rows. No prior pending migrations applied.')
