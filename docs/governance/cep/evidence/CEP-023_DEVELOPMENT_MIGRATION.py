import os,sys,json,hashlib
from pathlib import Path
sys.path.insert(0,os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings.development")
assert os.environ["DJANGO_SETTINGS_MODULE"]=="config.settings.development"
import django;django.setup()
from django.conf import settings
assert settings.DATABASES["default"]["HOST"] in ("127.0.0.1","localhost","::1")
from django.core.management import call_command
from apps.workforce.models import Employee,Person,WorkRelationship,WorkRelationshipRevision,LeavePolicyVersion,LeaveBalanceEntry
from apps.timekeeping.models import LeaveMissionRequest
from apps.organizations.models import OrganizationRole,BusinessPermission
models=[Employee,Person,WorkRelationship,WorkRelationshipRevision,LeaveMissionRequest,OrganizationRole.permissions.through]
def snapshot():
 result={}
 for model in models:
  values=list(model.objects.order_by("pk").values())
  result[model._meta.label]={"count":len(values),"sha256":hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()}
 return result
before=snapshot()
Path("docs/governance/cep/evidence/CEP-023_DEVELOPMENT_BEFORE.json").write_text(json.dumps(before,indent=2)+"\n",encoding="utf-8")
call_command("migrate","workforce","0014_cep023_leave_authority",interactive=False,verbosity=1)
after=snapshot()
Path("docs/governance/cep/evidence/CEP-023_DEVELOPMENT_AFTER.json").write_text(json.dumps(after,indent=2)+"\n",encoding="utf-8")
assert before==after,"Existing source/history/grants changed"
assert LeavePolicyVersion.objects.count()==LeaveBalanceEntry.objects.count()==0
codes=["leave_policies.manage","leave_balances.manage","leave_balances.view"]
assert BusinessPermission.objects.filter(code__in=codes,is_active=True).count()==3
record={"environment":"configured loopback Development PostgreSQL","before":before,"after":after,"existing_sources_and_grants_preserved":True,"leave_policy_versions":0,"leave_entries":0,"catalogue_permissions":codes,"default_grants_changed":False,"opening_backfill":False,"production":False}
Path("docs/governance/cep/evidence/CEP-023_DEVELOPMENT_MIGRATION.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
print("CEP023 source identity/history/grant hashes preserved; zero policies and leave entries; activation remains fail-closed")
