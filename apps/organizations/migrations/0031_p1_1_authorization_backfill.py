from django.db import migrations
from django.utils import timezone


NEW_PERMISSIONS = {
    "authorization_roles.view": "مشاهده نقش‌های عضویت",
    "authorization_roles.assign": "تخصیص نقش عضویت",
    "authorization_roles.revoke": "لغو نقش عضویت",
    "authorization_grants.view": "مشاهده دامنه‌های دسترسی",
    "authorization_grants.create": "ایجاد دامنه دسترسی",
    "authorization_grants.revoke": "لغو دامنه دسترسی",
    "authorization_unresolved.recover": "بازیابی کار حل‌نشده",
}

ROLE_METADATA = {
    "tenant_owner": ("Tenant Owner", "مالک Tenant با نقش و دامنه مستقل."),
    "tenant_admin": ("Tenant Admin", "مدیر محلی مستقل از مالک و مدیر کسب‌وکار."),
    "tenant_manager": ("Tenant Manager", "مدیر کسب‌وکار بدون اختیار حفاظت‌شده مالک."),
    "project_manager": ("Project Manager", "مدیر دامنه‌دار پروژه و کارگاه."),
    "accountant": ("Accountant", "نقش حسابداری مستقل و دامنه‌دار."),
    "supervisor": ("Supervisor", "ناظر عملیات روزمره در دامنه صریح."),
}

PROTECTED_OPERATIONS = {
    "authorization.self_grant": "Self-grant or access increase",
    "authorization.own_privileged_role": "Own privileged-role assignment or approval",
    "authorization.own_support_access": "Own support or emergency access",
    "authorization.policy_weaken": "Authorization or security-policy weakening",
    "authorization.audit_control_weaken": "Audit or security-control weakening",
    "authorization.protected_classification_change": "Protected classification change",
}


def seed_and_backfill(apps, schema_editor):
    Permission = apps.get_model("organizations", "BusinessPermission")
    Role = apps.get_model("organizations", "OrganizationRole")
    Membership = apps.get_model("organizations", "OrganizationMembership")
    RoleAssignment = apps.get_model("organizations", "MembershipRoleAssignment")
    ScopeGrant = apps.get_model("organizations", "MembershipScopeGrant")
    MigrationIssue = apps.get_model("organizations", "AuthorizationMigrationIssue")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    PolicyVersion = apps.get_model("organizations", "AuthorizationPolicyVersion")

    for code, name in NEW_PERMISSIONS.items():
        Permission.objects.update_or_create(
            code=code,
            defaults={"name": name, "description": "P1.1 authorization control", "is_active": True},
        )

    roles = {}
    for code, (name, description) in ROLE_METADATA.items():
        roles[code], _ = Role.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "is_active": True,
                "is_system": True,
                "is_owner": False,
            },
        )

    all_permissions = list(Permission.objects.filter(is_active=True))
    mutation_exclusions = {
        "accounts.create",
        "accounts.reset_password",
        "membership.change_role",
        "membership.change_status",
        "authorization_roles.assign",
        "authorization_roles.revoke",
        "authorization_grants.create",
        "authorization_grants.revoke",
        "authorization_unresolved.recover",
    }
    roles["tenant_owner"].permissions.set(all_permissions)
    roles["tenant_admin"].permissions.set(
        [p for p in all_permissions if p.code != "authorization_unresolved.recover"]
    )
    roles["tenant_manager"].permissions.set(
        [p for p in all_permissions if p.code not in mutation_exclusions]
    )
    roles["project_manager"].permissions.set(
        [
            p
            for p in all_permissions
            if p.code.split(".", 1)[0]
            not in {
                "accounts",
                "membership",
                "authorization_roles",
                "authorization_grants",
                "authorization_unresolved",
                "company",
                "audit",
            }
        ]
    )
    roles["accountant"].permissions.set(
        [
            p
            for p in all_permissions
            if p.code.split(".", 1)[0]
            in {
                "expenses",
                "payments",
                "claims",
                "claim_settlements",
                "progress",
                "baselines",
                "contracts",
                "projects",
                "project_sites",
                "documents",
                "work_items",
            }
        ]
    )
    legacy_member = Role.objects.filter(code="member").first()
    if legacy_member:
        roles["supervisor"].permissions.set(legacy_member.permissions.all())

    now = timezone.now()
    role_map = {
        "company_owner": roles["tenant_owner"],
        "company_manager": roles["tenant_manager"],
        "operations_manager": roles["supervisor"],
    }
    memberships = Membership.objects.exclude(status="pending_role").select_related(
        "role_definition"
    )
    for membership in memberships.iterator():
        legacy_role = membership.role_definition
        if legacy_role is None:
            MigrationIssue.objects.get_or_create(
                organization_id=membership.organization_id,
                membership=membership,
                issue_code="missing_role",
                defaults={"detail": "Legacy membership has no role definition."},
            )
            membership.authorization_migrated_at = now
            membership.authorization_quarantined_at = now
            membership.save(
                update_fields=["authorization_migrated_at", "authorization_quarantined_at"]
            )
            continue
        target_role = role_map.get(legacy_role.code, legacy_role)
        RoleAssignment.objects.get_or_create(
            organization_id=membership.organization_id,
            membership=membership,
            role=target_role,
            revoked_at__isnull=True,
            defaults={
                "starts_at": membership.joined_at or membership.created_at or now,
                "reason": "P1.1 evidence-preserving role backfill",
                "source": "backfill",
            },
        )
        membership.authorization_migrated_at = now
        if legacy_role.code == "company_owner":
            ScopeGrant.objects.get_or_create(
                organization_id=membership.organization_id,
                membership=membership,
                scope_type="organization",
                project=None,
                site=None,
                revoked_at__isnull=True,
                defaults={
                    "starts_at": membership.joined_at or membership.created_at or now,
                    "reason": "Evidence-supported ownership/governance scope backfill",
                    "source": "backfill",
                },
            )
            membership.authorization_quarantined_at = None
        else:
            membership.authorization_quarantined_at = now
            MigrationIssue.objects.get_or_create(
                organization_id=membership.organization_id,
                membership=membership,
                issue_code="scope_not_evidenced",
                defaults={
                    "detail": "Legacy tenant-wide behavior is not evidence of organization-wide scope."
                },
            )
        membership.save(
            update_fields=["authorization_migrated_at", "authorization_quarantined_at"]
        )

    for code, name in PROTECTED_OPERATIONS.items():
        ProtectedOperation.objects.get_or_create(
            code=code,
            version=1,
            defaults={
                "name": name,
                "description": "Non-overridable P1.1 Protected Operation.",
                "effective_at": now,
                "reason": "P1.1 G3 baseline",
            },
        )
    PolicyVersion.objects.get_or_create(
        code="site_parent_context",
        version=1,
        defaults={
            "policy": {"project_fields": ["id", "code", "name", "status"]},
            "effective_at": now,
            "reason": "P1.1 B1 minimal site-parent context",
        },
    )


def reverse_backfill(apps, schema_editor):
    RoleAssignment = apps.get_model("organizations", "MembershipRoleAssignment")
    ScopeGrant = apps.get_model("organizations", "MembershipScopeGrant")
    Membership = apps.get_model("organizations", "OrganizationMembership")
    MigrationIssue = apps.get_model("organizations", "AuthorizationMigrationIssue")
    ProtectedOperation = apps.get_model("organizations", "ProtectedOperation")
    PolicyVersion = apps.get_model("organizations", "AuthorizationPolicyVersion")
    Role = apps.get_model("organizations", "OrganizationRole")
    Permission = apps.get_model("organizations", "BusinessPermission")

    if RoleAssignment.objects.exclude(source="backfill").exists() or ScopeGrant.objects.exclude(
        source="backfill"
    ).exists():
        raise RuntimeError(
            "Unsafe P1.1 schema rollback refused: explicit post-backfill restrictions exist. "
            "Use the application compatibility rollback while retaining scope records."
        )
    RoleAssignment.objects.filter(source="backfill").delete()
    ScopeGrant.objects.filter(source="backfill").delete()
    MigrationIssue.objects.all().delete()
    Membership.objects.update(
        authorization_migrated_at=None, authorization_quarantined_at=None
    )
    ProtectedOperation.objects.filter(version=1, code__in=PROTECTED_OPERATIONS).delete()
    PolicyVersion.objects.filter(code="site_parent_context", version=1).delete()
    Role.objects.filter(code__in=ROLE_METADATA).delete()
    Permission.objects.filter(code__in=NEW_PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [("organizations", "0030_p1_1_authorization_foundation")]

    operations = [migrations.RunPython(seed_and_backfill, reverse_backfill)]
