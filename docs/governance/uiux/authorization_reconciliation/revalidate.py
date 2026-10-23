"""Bounded local Development reconciliation; never prints or saves credentials."""

import csv
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import (
    has_business_permission, is_platform_admin, membership_permission_codes,
)
from apps.organizations.models import (
    Organization, OrganizationMembership, OrganizationRole,
)
from apps.organizations.platform_grants import platform_initial_grant
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.role_reconciliation import UNASSIGNED_PERMISSION_REASONS
from apps.projects.models import Project


def save(name, data):
    (OUT / name).write_text(json.dumps(data, default=str, indent=2) + "\n", encoding="utf-8")


def store_credential(alias, password):
    program = "$d=[Console]::In.ReadToEnd()|ConvertFrom-Json; $p=Join-Path $env:LOCALAPPDATA 'BONIRA/UIUXRuntimeAudit/credentials'; [System.IO.Directory]::CreateDirectory($p)|Out-Null; $s=ConvertTo-SecureString $d.password -AsPlainText -Force; [pscredential]::new($d.alias,$s)|Export-Clixml -LiteralPath (Join-Path $p ($d.alias+'.clixml'))"
    subprocess.run([r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe",
                    "-NoProfile", "-Command", program],
        input=json.dumps({"alias": alias, "password": password}),
        capture_output=True, text=True, check=True)


def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["HOST"] in ("127.0.0.1", "localhost", "::1")
    assert connection.settings_dict["NAME"] == "construction_erp"
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")


def snapshot():
    result = {}
    for model in apps.get_models():
        if model._meta.app_label == "sessions":
            continue
        columns = [f.attname for f in model._meta.concrete_fields if f.name != "last_login"]
        result[model._meta.label] = {
            str(row[model._meta.pk.attname]): hashlib.sha256(
                json.dumps(row, sort_keys=True, default=str).encode()
            ).hexdigest()
            for row in model.objects.values(*columns)
        }
    return result


def ground():
    guard()
    assert not (OUT / "DATA_BEFORE.json").exists(), "Never overwrite the entry snapshot"
    save("DATA_BEFORE.json", snapshot())
    save("ENVIRONMENT.json", {k: connection.settings_dict[k]
                               for k in ("ENGINE", "NAME", "HOST", "PORT")})
    print("Development-only environment and immutable entry fingerprints recorded")


def reconcile():
    guard()
    assert (OUT / "DATA_BEFORE.json").exists()
    assert not (OUT / "GRANTS.json").exists(), "Reconciliation is single-use"
    from apps.accounts.services import initialize_personal_password
    from apps.organizations.access_services import update_organization_role
    from apps.organizations.catalog_bootstrap import synchronize_authorization_catalog
    from apps.organizations.services import create_organization_account

    org = Organization.objects.get(slug="demo-construction-01")
    platform = User.objects.get(username="admin")
    assert is_platform_admin(platform)
    owner = User.objects.get(username="account.demo-construction-01.owner")
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    changes = []
    with transaction.atomic():
        before = {r.code: set(r.permissions.values_list("code", flat=True))
                  for r in OrganizationRole.objects.filter(organization=None)}
        synchronize_authorization_catalog(using="default")
        for role in OrganizationRole.objects.filter(organization=None):
            after = set(role.permissions.values_list("code", flat=True))
            if before.get(role.code) != after:
                record_audit_event(
                    action=AuditAction.ROLE_UPDATED if role.code in before
                    else AuditAction.ROLE_CREATED,
                    entity_type="organizations.OrganizationRole", entity_id=role.pk,
                    actor=platform, allow_platform_actor=True,
                    metadata={"role_code": role.code,
                              "previous_permissions": sorted(before.get(role.code, set())),
                              "new_permissions": sorted(after),
                              "reason": "Human 2026-10-22 Role-Permission reconciliation"},
                )
                changes.append({"role": role.code, "added": sorted(after-before.get(role.code,set())),
                                "removed": sorted(before.get(role.code,set())-after)})
    # Existing own-history specialist needs the DMS reader prerequisite. Its
    # source/identity/category policies remain authoritative.
    own_role = OrganizationRole.objects.get(organization=org, code="wave_c_employment_own")
    update_organization_role(actor=platform, role_id=own_role.pk, name=own_role.name,
        description=own_role.description,
        permissions=["employment_records.view_own", "documents.view"],
        reason="Bounded own Employment history DMS reader prerequisite")
    plans = [
        ("uiux.wavec.buyer", "rfq_opener", project),
        ("uiux.wavec.employment", "wave_c_employment", None),
        ("uiux.wavec.time", "wave_c_employment_own", None),
        ("uiux.wavec.portal", "wave_c_portal", project),
        ("uiux.wavec.opening-approver", "rfq_opening_approver", project),
        ("uiux.wavec.custodian", "rfq_custodian", project),
    ]
    granted = []
    for alias, code, exact_project in plans:
        role = OrganizationRole.objects.get(code=code,
                     organization=org if code.startswith("wave_c_") else None)
        user = User.objects.filter(username=alias).first()
        if user is None:
            with transaction.atomic():
                password = secrets.token_urlsafe(28)
                user, membership = create_organization_account(
                    organization=org, actor=owner, username=alias,
                    temporary_password=secrets.token_urlsafe(28), role=role)
                initialize_personal_password(user=user, new_password=password)
                store_credential(alias, password)
                del password
        else:
            membership = OrganizationMembership.objects.get(organization=org, user=user)
        previous = sorted(membership_permission_codes(membership))
        assignment, scope = platform_initial_grant(
            organization=org, actor=platform, membership_id=membership.pk, role=role,
            scope_type="project" if exact_project else "organization",
            project=exact_project,
            reason="Human 2026-10-22 bounded affected Wave C first-grant revalidation")
        membership.refresh_from_db()
        granted.append({"actor": alias, "membership": str(membership.pk),
            "role": code, "assignment": str(assignment.pk), "scope": str(scope.pk),
            "scope_type": scope.scope_type, "project": str(scope.project_id) if scope.project_id else None,
            "previous_permissions": previous,
            "new_permissions": sorted(membership_permission_codes(membership))})
    save("CATALOG_CHANGES.json", changes)
    save("GRANTS.json", granted)
    print("Catalogue reconciled; six exact specialist grants audited; no domain reset")


def controls():
    guard()
    org = Organization.objects.get(slug="demo-construction-01")
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    platform = User.objects.get(username="admin")
    cases = []
    for row in json.loads((OUT / "GRANTS.json").read_text()):
        user = User.objects.get(username=row["actor"])
        role = OrganizationRole.objects.get(pk=OrganizationMembership.objects.get(pk=row["membership"])
            .role_assignments.get(pk=row["assignment"]).role_id)
        for permission in role.permissions.values_list("code", flat=True):
            assert has_business_permission(user=user, organization=org,
                permission=permission, project=project if row["project"] else None)
        if row["project"]:
            other = Project.objects.filter(organization=org).exclude(pk=project.pk).first()
            for permission in role.permissions.values_list("code", flat=True):
                assert not has_business_permission(user=user, organization=org,
                    permission=permission, project=other)
        try:
            platform_initial_grant(organization=org, actor=platform,
                membership_id=row["membership"], role=role,
                scope_type=row["scope_type"], project=project if row["project"] else None,
                reason="Replay must deny")
        except ValidationError:
            pass
        else:
            raise AssertionError("Duplicate Initial Grant succeeded")
        cases.append({"actor": row["actor"], "role_permissions_allowed": True,
                      "outside_project_denied": bool(row["project"]), "replay_denied": True})
    # Platform Admin's unrelated pre-existing tenant membership is unchanged;
    # this operation gives it none of the newly granted specialist permissions.
    for code in ("rfq_quotes.open", "employment_records.manage", "supplier_portal.invitations_manage"):
        assert not has_business_permission(user=platform, organization=org,
                                          permission=code, project=project)
    save("SERVICE_CONTROLS.json", cases)
    print("Six specialist positive/replay controls and scoped denials passed")


def concurrency():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    from apps.organizations.services import create_organization_account
    guard()
    assert not (OUT / "CONCURRENCY.json").exists()
    org = Organization.objects.get(slug="demo-construction-01")
    platform = User.objects.get(username="admin")
    owner = User.objects.get(username="account.demo-construction-01.owner")
    role = OrganizationRole.objects.get(code="wave_c_portal", organization=org)
    project = Project.objects.get(organization=org, code="PRJ-01-01")
    _, target = create_organization_account(organization=org, actor=owner,
        username="uiux.wavec.initial-grant-race", temporary_password=secrets.token_urlsafe(28),
        role=role)
    barrier = Barrier(2)
    def worker():
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET default_transaction_read_only = off")
            barrier.wait(timeout=20)
            try:
                platform_initial_grant(organization=org, actor=platform,
                    membership_id=target.pk, role=role, scope_type="project", project=project,
                    reason="Concurrent Development first-grant control")
                return "GRANTED"
            except ValidationError:
                return "DUPLICATE_DENIED"
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(outcomes) == ["DUPLICATE_DENIED", "GRANTED"]
    assert target.role_assignments.count() == target.scope_grants.count() == 1
    save("CONCURRENCY.json", {"outcomes": outcomes, "role_assignments": 1,
        "scope_grants": 1, "target": str(target.pk), "lost_update_or_duplicate": False})
    print("Concurrent first-grant race: one grant; one duplicate denial")


def matrix():
    from apps.organizations.models import BusinessPermissionCode
    with (OUT / "ROLE_PERMISSION_MATRIX.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["permission", "default_or_specialist_roles", "disposition"])
        for permission in sorted(BusinessPermissionCode.values):
            roles = sorted(str(role) for role, permissions in DEFAULT_ROLE_PERMISSIONS.items()
                           if permission in permissions)
            writer.writerow([permission, ";".join(roles),
                "EXPLICIT_ROLE_MAPPING" if roles else UNASSIGNED_PERMISSION_REASONS[permission]])
    baseline = json.loads((OUT / "BASELINE_ROLE_PERMISSIONS.json").read_text())
    for role in ("tenant_owner", "tenant_admin"):
        assert set(baseline[role]) == DEFAULT_ROLE_PERMISSIONS[role]
    save("MATRIX_SUMMARY.json", {"registered_permission_count": len(BusinessPermissionCode.values),
        "roles": len(DEFAULT_ROLE_PERMISSIONS), "initial_gaps": 148,
        "mapped_gaps": 147, "catalog_only_unassigned": UNASSIGNED_PERMISSION_REASONS,
        "owner_admin_permissions_unchanged_from_head": True})
    print("Complete permission matrix exported; Owner/Admin match HEAD exactly")


def integrity():
    guard()
    before = json.loads((OUT / "DATA_BEFORE.json").read_text())
    after = snapshot()
    delta = {}
    for label in before:
        old, new = before[label], after[label]
        changed = [pk for pk in old.keys() & new.keys() if old[pk] != new[pk]]
        removed = sorted(old.keys()-new.keys())
        added = sorted(new.keys()-old.keys())
        if changed or removed or added:
            delta[label] = {"changed": changed, "removed": removed, "added": added}
    save("DATA_DELTA.json", delta)
    # Never silently accept deletion or a finalized financial/stock mutation.
    for label, changes in delta.items():
        assert not changes["removed"], (label, "existing row removed")
        assert label.split(".")[0] not in {
            "accounting", "treasury", "subledgers", "payroll", "inventory"
        }, (label, "unexpected financial/stock change")
    save("INTEGRITY.json", {"model_count": len(before), "no_existing_rows_deleted": True,
        "financial_payroll_inventory_models_unchanged": True,
        "last_login_and_sessions_excluded": True, "delta": "DATA_DELTA.json"})
    print("Existing rows retained; financial, Payroll and Inventory models unchanged")


if __name__ == "__main__":
    globals()[sys.argv[1]]()
