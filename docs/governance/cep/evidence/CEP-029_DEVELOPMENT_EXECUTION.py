import os,sys,json
from pathlib import Path
sys.path.insert(0,os.getcwd());os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings.development")
assert os.environ["DJANGO_SETTINGS_MODULE"]=="config.settings.development"
import django;django.setup()
from django.conf import settings
assert settings.DATABASES["default"]["HOST"] in ("localhost","127.0.0.1","::1")
from apps.workforce import identity_migration as service
from apps.workforce.models import Employee,Person,WorkRelationship,WorkRelationshipRevision
from apps.workforce.identity_migration_models import EmployeeIdentityMigration
from apps.organizations.models import Organization,OrganizationRole,MembershipStatus,BusinessPermissionCode as P
from apps.organizations.authorization import effective_role_assignments,require_business_permission
from django.core.management import call_command
from django.db import transaction
E=Path("docs/governance/cep/evidence")
def global_snapshot():
 return {m._meta.label:{"count":m.objects.count(),"fingerprint":service.fingerprint(list(m.objects.order_by("pk").values()))} for m in [Employee,Person,WorkRelationship,WorkRelationshipRevision,OrganizationRole.permissions.through]}
mode=sys.argv[1]
if mode=="schema":
 before=global_snapshot();(E/"CEP-029_SCHEMA_BEFORE.json").write_text(json.dumps(before,indent=2)+"\n")
 call_command("migrate","workforce","0015_cep029_identity_migration",interactive=False,verbosity=1)
 after=global_snapshot();assert before==after
 (E/"CEP-029_SCHEMA_RECONCILIATION.json").write_text(json.dumps({"before":before,"after":after,"preserved":True,"production":False},indent=2)+"\n")
 print("Additive configured Development schema preserved all source/target identities and existing grants")
else:
 runs=[]
 with transaction.atomic():
  for organization in Organization.objects.filter(employees__isnull=False).distinct().order_by("pk"):
   candidates=[]
   for membership in organization.memberships.filter(status=MembershipStatus.ACTIVE,user__is_active=True).select_related("user"):
    if effective_role_assignments(membership).filter(role__code="tenant_owner").exists():candidates.append(membership)
   assert candidates,"No active explicitly assigned tenant owner for authorized Development conversion"
   membership=sorted(candidates,key=lambda x:str(x.pk))[0];actor=membership.user
   for code in (P.EMPLOYEES_VIEW,P.EMPLOYEES_CREATE):require_business_permission(user=actor,organization=organization,permission=code,message="Development operator lacks explicit migration capability/scope")
   before_source=service.fingerprint(service._source_state(organization));before_counts=service._counts(organization)
   key="CEP029-development-source-v1-20261019"
   result=service.migrate_employee_identities(organization=organization,actor=actor,source_key=key,reason="Human-authorized CEP029 Development/non-production source-evidenced conversion; no cutover or User linkage",rehearsal=(mode=="rehearsal"))
   assert before_source==service.fingerprint(service._source_state(organization))
   if mode=="rehearsal":assert before_counts==service._counts(organization)
   if mode=="apply":
    repeat=service.migrate_employee_identities(organization=organization,actor=actor,source_key=key,reason="Human-authorized CEP029 Development/non-production source-evidenced conversion; no cutover or User linkage")
    assert repeat["repeated"] and repeat["mapping"]==result["mapping"]
   runs.append({"actor_id":str(actor.pk),"organization_id":str(organization.pk),"result":result,"counts_after_transaction":service._counts(organization),"source_unchanged":True})
  # Rehearsal rollback is scoped within each service savepoint; no target/run persists.
  record={"mode":mode,"environment":"configured loopback Development PostgreSQL","runs":runs,"totals":{"source":sum(r["result"]["source_count"] for r in runs),"mapped":sum(r["result"]["mapped_count"] for r in runs),"exceptions":sum(r["result"]["exception_count"] for r in runs)},"production":False,"cutover":False,"user_links_created":False,"leave_opening_backfill":False}
 (E/("CEP-029_DEVELOPMENT_"+mode.upper()+".json")).write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
 print(mode,record["totals"],"source hashes unchanged; User and assignment authority retained")
