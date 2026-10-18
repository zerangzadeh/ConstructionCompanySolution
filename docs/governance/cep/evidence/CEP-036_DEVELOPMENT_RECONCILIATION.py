import os,json,hashlib
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.core.management import call_command
from apps.billing.indexation import ADAPTERS
assert settings.SETTINGS_MODULE=='config.settings.development'
assert connection.vendor=='postgresql'
assert connection.settings_dict['HOST'] in ('localhost','127.0.0.1','::1')
models=[m for label in ('billing','contracts') for m in apps.get_app_config(label).get_models() if not m.__name__.startswith('Indexation')]
from apps.organizations.models import MembershipRoleAssignment,MembershipScopeGrant,OrganizationRole,BusinessPermission
models += [MembershipRoleAssignment,MembershipScopeGrant,OrganizationRole.permissions.through]
def snapshot():
 out={}
 for m in models:
  rows=list(m._base_manager.order_by('pk').values())
  raw=json.dumps(rows,sort_keys=True,default=str,separators=(',',':'),ensure_ascii=False).encode()
  out[m._meta.label]={'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}
 return out
codes=['indexation_rules.manage','indexation.calculate','indexation.correct']
catalog_before=list(BusinessPermission.objects.exclude(code__in=codes).order_by('pk').values('id','code','name','description','is_active','created_at'))
before=snapshot()
call_command('migrate','organizations','0114_cep036_indexation_permissions',verbosity=1)
call_command('migrate','billing','0016_cep036_indexation',verbosity=1)
after=snapshot()
assert before==after
assert catalog_before==list(BusinessPermission.objects.exclude(code__in=codes).order_by('pk').values('id','code','name','description','is_active','created_at'))
assert not OrganizationRole.permissions.through.objects.filter(businesspermission__code__in=codes).exists()
from apps.billing.models import IndexationRuleVersion,IndexationCalculation
assert not ADAPTERS and not IndexationRuleVersion.objects.exists() and not IndexationCalculation.objects.exists()
Path('docs/governance/cep/evidence/CEP-036_DEVELOPMENT_RECONCILIATION.json').write_text(json.dumps({'environment':'configured_local_development_postgresql','source_before':before,'source_after':after,'unchanged':True,'rules':0,'calculations':0,'deployed_adapters':0,'new_capability_grants':0,'existing_catalog_unchanged':True},indent=2),encoding='utf-8')
print('Reconciliation PASS; all existing Billing/Contracts and role assignment/scope/grant rows unchanged; no indexation activation.')
