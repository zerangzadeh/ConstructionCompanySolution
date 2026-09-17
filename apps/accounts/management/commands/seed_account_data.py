"""Seed deterministic development-only tenant account data without replacement."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import LoginPageSettings, User
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.role_defaults import (
    DEFAULT_ROLE_METADATA,
    DEFAULT_ROLE_PERMISSIONS,
)
from apps.organizations.services import create_organization_account

DEMO_ADMIN_USERNAME = "admin"
DEMO_PASSWORD = "۱۲۳۴۵۶"
DEMO_ORGANIZATION_PREFIX = "demo-construction-"


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
        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if settings_module != "config.settings.development" or not settings.DEBUG:
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
