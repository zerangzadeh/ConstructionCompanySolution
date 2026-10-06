"""Seed deterministic development-only tenant account data without replacement."""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import LoginPageSettings, User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.access_services import create_organization_role
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.role_defaults import (
    DEFAULT_ROLE_METADATA,
    DEFAULT_ROLE_PERMISSIONS,
    PAYROLL_SENSITIVE_PERMISSIONS,
    WORKFORCE_SENSITIVE_PERMISSIONS,
)
from apps.organizations.services import create_organization_account

DEMO_ADMIN_USERNAME = "admin"
DEMO_PASSWORD = "۱۲۳۴۵۶"
DEMO_ORGANIZATION_PREFIX = "demo-construction-"
P7_DEMO_PAYROLL_ORGANIZATION = "demo-construction-01"
P7_DEMO_PAYROLL_ROLE_CODE = "p7_demo_payroll_assurance"
P7_DEMO_ASSURANCE_PERMISSIONS = (
    PAYROLL_SENSITIVE_PERMISSIONS | WORKFORCE_SENSITIVE_PERMISSIONS
)


@dataclass(frozen=True)
class AccountSeed:
    key: str
    membership_role: MembershipRole
    first_name: str
    last_name: str


ACCOUNT_SEEDS = (
    AccountSeed("owner", MembershipRole.COMPANY_OWNER, "علی", "رضایی"),
    AccountSeed("manager", MembershipRole.COMPANY_MANAGER, "مریم", "کاظمی"),
    # The current membership catalog has no separate accountant role.  The
    # company-manager role is the existing permission-backed equivalent.
    AccountSeed("accountant", MembershipRole.COMPANY_MANAGER, "رضا", "محمدی"),
    # The current membership catalog names the supervisor capability
    # operations_manager; no new role is introduced by development seed data.
    AccountSeed("supervisor", MembershipRole.OPERATIONS_MANAGER, "نگار", "احمدی"),
    AccountSeed("viewer", MembershipRole.VIEWER, "سارا", "قاسمی"),
)


@dataclass
class SeedSummary:
    created: Counter[str] = field(default_factory=Counter)
    existing: Counter[str] = field(default_factory=Counter)
    passwords_updated: int = 0

    def record(self, label: str, created: bool) -> None:
        (self.created if created else self.existing)[label] += 1


class Command(BaseCommand):
    help = "Create incremental development account data for existing demo tenants."

    def handle(self, *args: object, **options: object) -> None:
        if not settings.DEBUG and "pytest" not in sys.modules:
            raise CommandError(
                "seed_account_data is restricted to config.settings.development with DEBUG=True."
            )

        summary = SeedSummary()
        with transaction.atomic():
            roles = self._ensure_roles_and_permissions(summary)
            admin = self._ensure_admin(summary)
            self._ensure_login_page_settings(summary)
            organizations = list(
                Organization.objects.filter(
                    slug__startswith=DEMO_ORGANIZATION_PREFIX,
                    status="active",
                    deleted_at__isnull=True,
                    archived_at__isnull=True,
                ).order_by("slug")
            )
            if not organizations:
                raise CommandError(
                    "No active demo tenants were found. Run seed_demo_data before seed_account_data."
                )
            summary.existing["organizations"] += len(organizations)
            for organization in organizations:
                for account_seed in ACCOUNT_SEEDS:
                    self._seed_tenant_account(
                        summary=summary,
                        admin=admin,
                        organization=organization,
                        account_seed=account_seed,
                        role=roles[account_seed.membership_role],
                    )
                self._ensure_p7_demo_payroll_access(
                    summary=summary,
                    admin=admin,
                    organization=organization,
                )

        self.stdout.write(self.style.SUCCESS("Development account seed data is ready."))
        self.stdout.write("Password for seeded users: Persian digits 123456")
        self.stdout.write(
            "Passwords updated: "
            f"{summary.passwords_updated}; users: "
            f"{summary.created['users']} created, {summary.existing['users']} existing; "
            f"memberships: {summary.created['memberships']} created, "
            f"{summary.existing['memberships']} existing."
        )
        for label in ("organizations", "permissions", "roles", "login_page_settings"):
            self.stdout.write(
                f"{label}: {summary.created[label]} created, "
                f"{summary.existing[label]} existing"
            )

    def _ensure_roles_and_permissions(
        self, summary: SeedSummary
    ) -> dict[MembershipRole, OrganizationRole]:
        permissions: dict[str, BusinessPermission] = {}
        for code in BusinessPermissionCode.values:
            permission, created = BusinessPermission.objects.get_or_create(
                code=code,
                defaults={
                    "name": BusinessPermissionCode(code).label,
                    "description": "مجوز سیستمی موردنیاز سامانه ساخت.",
                    "is_active": True,
                },
            )
            summary.record("permissions", created)
            permissions[code] = permission

        roles: dict[MembershipRole, OrganizationRole] = {}
        for role_code in MembershipRole:
            role, created = OrganizationRole.objects.get_or_create(
                code=role_code,
                defaults=DEFAULT_ROLE_METADATA[role_code],
            )
            summary.record("roles", created)
            if created:
                role.permissions.add(
                    *(permissions[code] for code in DEFAULT_ROLE_PERMISSIONS[role_code])
                )
            roles[role_code] = role
        return roles

    def _ensure_admin(self, summary: SeedSummary) -> User:
        admin = User.objects.filter(username=DEMO_ADMIN_USERNAME).first()
        created = admin is None
        if admin is None:
            admin = User.objects.create_superuser(
                username=DEMO_ADMIN_USERNAME,
                password=DEMO_PASSWORD,
                first_name="مدیر",
                last_name="سامانه",
            )
        else:
            update_fields: set[str] = set()
            if not admin.is_superuser:
                admin.is_superuser = True
                update_fields.add("is_superuser")
            if not admin.is_staff:
                admin.is_staff = True
                update_fields.add("is_staff")
            if not admin.check_password(DEMO_PASSWORD):
                admin.set_password(DEMO_PASSWORD)
                update_fields.add("password")
                summary.passwords_updated += 1
            if update_fields:
                admin.save(update_fields=update_fields | {"updated_at"})
        summary.record("users", created)
        return admin

    def _ensure_login_page_settings(self, summary: SeedSummary) -> None:
        _, created = LoginPageSettings.objects.get_or_create(pk=1)
        summary.record("login_page_settings", created)

    def _seed_tenant_account(
        self,
        *,
        summary: SeedSummary,
        admin: User,
        organization: Organization,
        account_seed: AccountSeed,
        role: OrganizationRole,
    ) -> None:
        username = f"account.{organization.slug}.{account_seed.key}"
        user = User.objects.filter(username=username).first()
        if user is None:
            user, membership = create_organization_account(
                organization=organization,
                actor=admin,
                username=username,
                temporary_password=DEMO_PASSWORD,
                role=role,
                first_name=account_seed.first_name,
                last_name=account_seed.last_name,
            )
            summary.record("users", True)
            summary.record("memberships", True)
            return

        summary.record("users", False)
        membership = OrganizationMembership.objects.filter(
            organization=organization,
            user=user,
        ).first()
        if membership is None:
            raise CommandError(
                f"Refusing to attach existing user '{username}' to a new tenant."
            )
        summary.record("memberships", False)
        if not user.check_password(DEMO_PASSWORD):
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password", "updated_at"])
            summary.passwords_updated += 1
        if membership.status != MembershipStatus.ACTIVE:
            raise CommandError(
                f"Existing membership for '{username}' is not active and was not changed."
            )

    def _ensure_p7_demo_payroll_access(
        self,
        *,
        summary: SeedSummary,
        admin: User,
        organization: Organization,
    ) -> None:
        """Provision P7 access only for the designated development demo owner.

        P7 sensitive Workforce, Payroll, statutory, export, and handoff
        permissions remain outside all built-in role defaults. This idempotent
        development seed creates a tenant-local explicit role for the single
        walkthrough account instead.
        """

        if organization.slug != P7_DEMO_PAYROLL_ORGANIZATION:
            return
        owner = User.objects.get(
            username=f"account.{organization.slug}.owner",
            is_active=True,
        )
        membership = OrganizationMembership.objects.get(
            organization=organization,
            user=owner,
            status=MembershipStatus.ACTIVE,
        )
        permission_codes = sorted(P7_DEMO_ASSURANCE_PERMISSIONS)
        if BusinessPermission.objects.filter(
            code__in=permission_codes,
            is_active=True,
        ).count() != len(permission_codes):
            raise CommandError(
                "P7 permission catalog is incomplete; run migrations first."
            )
        role = OrganizationRole.objects.filter(
            organization=organization,
            code=P7_DEMO_PAYROLL_ROLE_CODE,
        ).first()
        if role is None:
            role = create_organization_role(
                actor=admin,
                organization=organization,
                code=P7_DEMO_PAYROLL_ROLE_CODE,
                name="دسترسی تضمین P7 دمو",
                description="دسترسی صریح و محدود به تضمین P7 برای مالک حساب نمایشی.",
                permissions=permission_codes,
                reason="Provision the accepted P7 walkthrough for the designated demo owner.",
            )
            summary.created["p7_demo_payroll_roles"] += 1
        else:
            summary.existing["p7_demo_payroll_roles"] += 1
            existing_codes = set(role.permissions.values_list("code", flat=True))
            missing_codes = set(permission_codes) - existing_codes
            if missing_codes:
                role.permissions.add(
                    *BusinessPermission.objects.filter(code__in=missing_codes)
                )
                record_audit_event(
                    action=AuditAction.ROLE_UPDATED,
                    entity_type="organizations.OrganizationRole",
                    entity_id=role.pk,
                    organization=organization,
                    actor=admin,
                    allow_platform_actor=True,
                    metadata={
                        "role_code": role.code,
                        "previous_permissions": sorted(existing_codes),
                        "new_permissions": sorted(existing_codes | missing_codes),
                        "reason": "Reconcile the development P7 walkthrough role.",
                    },
                )
        assignment, created = MembershipRoleAssignment.objects.get_or_create(
            organization=organization,
            membership=membership,
            role=role,
            revoked_at__isnull=True,
            defaults={
                "reason": "Accepted P7 walkthrough access for the designated demo owner.",
                "source": "development_seed",
            },
        )
        if created:
            summary.created["p7_demo_payroll_assignments"] += 1
            record_audit_event(
                action=AuditAction.MEMBERSHIP_ROLE_ASSIGNED,
                entity_type="organizations.MembershipRoleAssignment",
                entity_id=assignment.pk,
                organization=organization,
                actor=admin,
                allow_platform_actor=True,
                metadata={
                    "target_membership_id": str(membership.pk),
                    "role": role.code,
                    "source": "development_seed",
                    "reason": assignment.reason,
                },
            )
        else:
            summary.existing["p7_demo_payroll_assignments"] += 1
