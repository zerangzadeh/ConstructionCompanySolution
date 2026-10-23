"""Reproduce exact legacy approver authority under immutable HEAD, rolled back."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
frozen_info = json.loads((OUT.parent / "wave_c_final_closure/FROZEN_SOURCE.json").read_text())
frozen = Path(frozen_info["path"])
os.environ["DB_NAME"] = "test_bonira_uiux_batch09"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.chdir(frozen)
sys.path.insert(0, str(frozen))
import django
django.setup()
from django.conf import settings
from django.db import connection, transaction
from django.core.exceptions import PermissionDenied
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership, MembershipRole, MembershipStatus, BusinessPermission, BusinessPermissionCode, OrganizationRole, MembershipScopeGrant
from apps.organizations.authorization import require_business_permission
from apps.projects.models import Project

assert settings.DEBUG and connection.settings_dict["NAME"] == "test_bonira_uiux_batch09"
with transaction.atomic():
    # TransactionTestCase flushes seeded catalogues. Supply the minimal explicit
    # catalogue constants inside this isolated rollback probe if absent.
    for code in (MembershipRole.TENANT_MANAGER, MembershipRole.COMPANY_OWNER):
        OrganizationRole.objects.get_or_create(code=code, defaults={"name": str(code)})
    for code in (BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN, BusinessPermissionCode.RFQS_CLOSE_CUSTODY):
        BusinessPermission.objects.get_or_create(code=code, defaults={"name": str(code)})
    org = Organization.objects.create(name="Frozen RV007 exact approver", slug="rv007-frozen-approver-probe")
    user = User.objects.create_user(username="rv007-frozen-approver-probe", password="x")
    member = OrganizationMembership.objects.create(organization=org, user=user, role=MembershipRole.TENANT_MANAGER, status=MembershipStatus.ACTIVE)
    project = Project.objects.create(organization=org, code="RV007-FROZEN", name="Frozen Project")
    member.role_definition.permissions.add(BusinessPermission.objects.get(code=BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN))
    denied = False
    try:
        require_business_permission(user=user, organization=org, permission=BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN, project=project, message="Exact frozen opening approver")
    except PermissionDenied:
        denied = True
    assert denied
    evidence = {"head": frozen_info["head"], "implementation": "Immutable HEAD export", "authorization_module": str(sys.modules["apps.organizations.authorization"].__file__), "authorization_sha256": hashlib.sha256((frozen / "apps/organizations/authorization.py").read_bytes()).hexdigest(), "factory": "Exact unchanged AdmissibilityFixtureMixin._make_actor: active tenant_manager legacy role; no scope/assignment bootstrap", "grant": "Exact fixture _grant RFQ_QUOTES_APPROVE_OPEN on role_definition", "scope_count": member.scope_grants.count(), "assignment_count": member.role_assignments.count(), "authorization_migrated_at": str(member.authorization_migrated_at), "result": "PermissionDenied", "isolated_test_database": connection.settings_dict["NAME"], "transaction": "ROLLED_BACK"}
    # HEAD buyer override sets a custom compatibility role plus explicit scope.
    # It is effective before the later shared fixture marks the member migrated
    # and creates another active role assignment. Reproduce only this exact seam.
    owner = User.objects.create_user(username="rv007-frozen-custom-role-probe")
    target = OrganizationMembership.objects.create(organization=org, user=owner, role=MembershipRole.COMPANY_OWNER, status=MembershipStatus.ACTIVE)
    role = OrganizationRole.objects.create(code="rv007-frozen-custom-role", name="Exact HEAD buyer custom role")
    role.permissions.add(BusinessPermission.objects.get(code=BusinessPermissionCode.RFQS_CLOSE_CUSTODY))
    target.role_definition = role
    target.save(update_fields=["role_definition"])
    MembershipScopeGrant.objects.create(organization=org, membership=target, scope_type="organization", reason="Exact HEAD buyer fixture")
    require_business_permission(user=owner, organization=org, permission=BusinessPermissionCode.RFQS_CLOSE_CUSTODY, project=project, message="Exact frozen custom role")
    evidence["head_buyer_custom_role"] = {"result": "ALLOWED", "migrated": target.authorization_migrated_at is not None, "role_assignment_count": target.role_assignments.count(), "scope_count": target.scope_grants.count(), "permission": "rfqs.close_custody"}
    evidence["catalogue"] = "Minimal role/permission constants in isolated rollback transaction; no Product/default permission semantics added"
    transaction.set_rollback(True)
(OUT / "FROZEN_APPROVER_PROBE.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print("Immutable HEAD exact approver input: protected opening approval DENIED; missing scope; rolled back.")
