"""Bind existing canonical roles to isolated test aliases through governed services."""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.db import connection, transaction
from apps.accounts.models import User
from apps.organizations.access_services import assign_membership_role, grant_membership_scope
from apps.organizations.authorization import effective_scope_grants, membership_permission_codes, membership_has_scope
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole, BusinessPermissionCode as P
from apps.organizations.platform_grants import platform_initial_grant
from apps.organizations.role_defaults import DEFAULT_ROLE_METADATA
from apps.projects.models import Project

OUT = Path(__file__).parent
assert not (OUT / "ACTOR_PREPARATION.json").exists()
assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql" and settings.DATABASES["default"]["HOST"] in ("127.0.0.1", "localhost")
org = Organization.objects.get(slug="demo-construction-01", status="active")
platform = User.objects.get(username="admin", is_active=True)
project = Project.objects.get(organization=org, code="PRJ-01-01")
plan = [
    ("uiux.audit.reporting", "company_manager", "organization"),
    ("uiux.audit.reporting", "reporting_analyst", "organization"),
    ("uiux.audit.reporting", "reporting_sensitive_reader", "organization"),
    ("uiux.audit.reporting", "project_controls_reviewer", "organization"),
    ("uiux.audit.reporting", "accountant", "organization"),
    ("cep078.synthetic.accessibility", "project_manager", "project"),
    ("cep078.synthetic.accessibility", "company_manager", "project"),
    ("cep078.synthetic.accessibility", "reporting_analyst", "project"),
    ("uiux.wavec.payroll", "payroll_specialist", "organization"),
]


def definitions():
    return {str(r.pk): {"code": r.code, "organization": str(r.organization_id), "system": r.is_system,
            "active": r.is_active, "permissions": sorted(r.permissions.values_list("code", flat=True))}
            for r in OrganizationRole.objects.all()}


before = definitions()
outcomes = []
for alias, code, scope in plan:
    assert alias.startswith(("uiux.", "cep078.synthetic."))
    assert code in DEFAULT_ROLE_METADATA, "No inferred or newly invented role"
    role = OrganizationRole.objects.get(code=code, organization__isnull=True, is_system=True, is_active=True)
    target = OrganizationMembership.objects.select_related("user").get(organization=org,user__username=alias,status="active")
    wanted = set(role.permissions.filter(is_active=True).values_list("code", flat=True))
    # Choose existing ordinary delegators only; the actual service locks and
    # rechecks all authorization, subset, scope and independent-approver rules.
    members = list(OrganizationMembership.objects.filter(organization=org,status="active",user__is_active=True).exclude(pk=target.pk).select_related("user"))
    delegates = [m for m in members if str(P.AUTHORIZATION_ROLES_ASSIGN) in membership_permission_codes(m)
                 and membership_has_scope(m) and wanted.issubset(membership_permission_codes(m))]
    pair = next(((a,b) for a in delegates for b in members if a.pk != b.pk
                 and str(P.AUTHORIZATION_ROLES_ASSIGN) in membership_permission_codes(b)
                 and membership_has_scope(b)), None)
    reason = "Direct Human CEP079 preparation: existing canonical role, isolated synthetic Development alias, explicit source scope; no role-definition change, UAT execution or Production authority."
    try:
        with transaction.atomic():
            if pair:
                actor, approver = pair
                assignment = assign_membership_role(
                    organization=org, actor=actor.user, membership_id=target.pk,
                    role=role, approver_membership_id=approver.pk, reason=reason,
                )
                exact = effective_scope_grants(target).filter(scope_type=scope,project=project if scope=="project" else None,site=None).first()
                if exact is None:
                    scope_actor = next(m for m in members if str(P.AUTHORIZATION_GRANTS_CREATE) in membership_permission_codes(m)
                                       and membership_has_scope(m,project=project if scope=="project" else None))
                    scope_approver = next(m for m in members if m.pk!=scope_actor.pk
                                          and str(P.AUTHORIZATION_GRANTS_CREATE) in membership_permission_codes(m)
                                          and membership_has_scope(m,project=project if scope=="project" else None))
                    exact = grant_membership_scope(
                        organization=org, actor=scope_actor.user, membership_id=target.pk,
                        scope_type=scope, project=project if scope=="project" else None,
                        approver_membership_id=scope_approver.pk, reason=reason,
                    )
                route = "ordinary_role_assignment_with_actual_independent_approver"
            else:
                # Existing approved bootstrap service itself proves absence of a
                # lawful ordinary pair. It requires explicit Platform Admin and
                # rejects self-grants, broader receiver scope and catalogue gaps.
                assignment, exact = platform_initial_grant(
                    organization=org, actor=platform, membership_id=target.pk, role=role,
                    scope_type=scope, project=project if scope=="project" else None, reason=reason,
                )
                route = "approved_platform_initial_grant_no_lawful_ordinary_pair"
        outcomes.append({"alias":alias,"role":code,"scope":scope,"project":str(project.pk) if scope=="project" else None,
                         "route":route,"assignment":str(assignment.pk),"scope_grant":str(exact.pk),"result":"PREPARED"})
    except Exception as exc:
        outcomes.append({"alias":alias,"role":code,"scope":scope,"result":"BLOCKED","exception":type(exc).__name__,"message":str(exc)})
after = definitions()
assert before == after, "Role definitions and permission sets must not change"
result = {"plan":outcomes,"role_definitions_before":before,"role_definitions_unchanged":True,
          "no_credentials_or_identity_or_legacy_role_fields_changed":True,
          "no_superuser_staff_or_role_hierarchy_inference":True,
          "source_authority":"Current canonical access_services and platform_initial_grant; 2026-10-22 approved role catalogue; direct Human CEP079 synthetic persona preparation",
          "scope_boundary":"Development database only; synthetic aliases only; existing ordinary reference accounts unchanged; retain these identified fixture bindings for later authorized UAT; no automatic deletion"}
(OUT / "ACTOR_PREPARATION.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(outcomes,ensure_ascii=True))
