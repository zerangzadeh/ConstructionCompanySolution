from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.access_services import (
    assign_platform_admin,
    assign_platform_role,
    bootstrap_membership_authorization,
    create_organization_role,
    protect_last_platform_admin,
    revoke_platform_role,
    update_organization_role,
)
from apps.organizations.authorization import is_platform_admin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    PlatformRoleAssignment,
    PlatformRoleCode,
)
from apps.organizations.platform_companies import (
    incomplete_company_onboarding,
    retry_company_onboarding,
    update_platform_company,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_by_system_admin,
    create_organization_with_owner,
)


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class PlatformConsoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(username="console-root")
        cls.admin = User.objects.create_user(username="console-admin")
        cls.owner = User.objects.create_user(
            username="console-owner", password="fixture-password"
        )
        assign_platform_admin(
            actor=cls.root, approver=cls.root, target=cls.admin, reason="test bootstrap"
        )
        cls.company = create_organization_with_owner(
            owner=cls.owner, name="Console Co", slug="console-co"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_all_seven_destinations_are_reachable_and_separate(self):
        sections = (
            "platform_dashboard",
            "platform_company_list",
            "platform_users",
            "platform_administrators",
            "platform_role_catalog",
            "platform_settings",
            "platform_audit",
            "platform_status",
        )
        dashboard = self.client.get(reverse("organizations:platform_dashboard"))
        for section in sections:
            with self.subTest(section=section):
                url = reverse(f"organizations:{section}")
                self.assertContains(
                    dashboard,
                    f'href="{url}"',
                    count=4
                    if section == "platform_users"
                    else 3
                    if section != "platform_company_list"
                    else 2,
                )
                self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.owner)
        for section in sections:
            self.assertEqual(
                self.client.get(reverse(f"organizations:{section}")).status_code, 403
            )

    def test_operator_grants_and_revokes_without_superuser_or_tenant_authority(self):
        url = reverse("organizations:platform_administrators")
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "action": "grant",
                    "username": self.owner.username,
                    "reason": "rotation",
                },
            ),
            url,
        )
        self.owner.refresh_from_db()
        self.assertTrue(is_platform_admin(self.owner))
        self.assertFalse(self.owner.is_superuser)
        assignment = PlatformRoleAssignment.objects.get(user=self.owner)
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "action": "revoke",
                    "assignment": assignment.pk,
                    "reason": "rotation ended",
                },
            ),
            url,
        )
        self.assertFalse(is_platform_admin(self.owner))
        self.assertEqual(
            AuditEvent.objects.get(action=AuditAction.PLATFORM_ROLE_REVOKED).metadata[
                "approval_mode"
            ],
            "platform_operator",
        )
        with self.assertRaises(PermissionDenied):
            protect_last_platform_admin(self.admin.pk)
        with self.assertRaises(PermissionDenied):
            revoke_platform_role(
                actor=self.admin,
                assignment_id=PlatformRoleAssignment.objects.get(user=self.admin).pk,
                reason="self revoke",
            )
        with self.assertRaises(PermissionDenied):
            assign_platform_role(
                actor=self.admin,
                target=self.owner,
                role=PlatformRoleCode.PLATFORM_SECURITY,
                reason="other duty",
            )

    def test_audit_excludes_tenant_business_events_and_nested_sensitive_metadata(self):
        event = record_audit_event(
            action=AuditAction.ORGANIZATION_STATUS_CHANGED,
            entity_type="organizations.Organization",
            organization=self.company,
            actor=self.admin,
            allow_platform_actor=True,
            metadata={"reason": "private-payload-marker"},
        )
        record_audit_event(
            action=AuditAction.PROJECT_CREATED,
            entity_type="projects.Project",
            organization=self.company,
            actor=self.owner,
            entity_id="hidden-business-object",
        )
        response = self.client.get(
            reverse("organizations:platform_audit"),
            {
                "company": self.company.pk,
                "action": event.action,
                "actor": self.admin.username,
            },
        )
        self.assertContains(response, self.company.name)
        self.assertNotContains(response, "private-payload-marker")
        self.assertNotContains(response, "hidden-business-object")
        for field in ("metadata", "changes"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                record_audit_event(
                    action=AuditAction.ROLE_UPDATED,
                    entity_type="test",
                    **{field: {"items": [[{"secret": "synthetic"}]]}},
                )

    def test_legacy_onboarding_retry_is_safe_and_creation_failure_rolls_back(self):
        self.assertTrue(incomplete_company_onboarding(self.company))
        for _ in range(2):
            retry_company_onboarding(actor=self.admin, organization_id=self.company.pk)
        self.assertFalse(incomplete_company_onboarding(self.company))
        self.assertEqual(
            AuditEvent.objects.filter(
                action=AuditAction.ORGANIZATION_ONBOARDING_RETRIED
            ).count(),
            1,
        )
        with (
            patch(
                "apps.daily_reports.workflow.ensure_daily_report_compatibility_workflow",
                side_effect=ValidationError("test"),
            ),
            self.assertRaises(ValidationError),
        ):
            create_organization_by_system_admin(
                actor=self.admin, owner=self.owner, name="Failed", slug="failed-console"
            )
        self.assertFalse(Organization.objects.filter(slug="failed-console").exists())
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.ORGANIZATION_CREATED).count(),
            1,
        )

    def test_role_only_operator_cannot_inspect_or_change_tenant_member_assignments(
        self,
    ):
        member = self.company.memberships.get(user=self.owner)
        response = self.client.get(
            reverse("organizations:platform_member_roles"),
            {"organization": self.company.pk},
        )
        self.assertContains(response, "به عضویت و مجوزهای لازم")
        self.assertIsNone(response.context["page_obj"])
        url = reverse(
            "organizations:platform_member_authorization",
            args=[self.company.pk, member.pk],
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {"action": "revoke_role"}).status_code, 403
        )

    def test_platform_role_catalog_protects_owner_grants_and_stale_versions(self):
        role = OrganizationRole.objects.get(
            organization__isnull=True, code=MembershipRole.TENANT_OWNER
        )
        kwargs = {
            "actor": self.admin,
            "role_id": role.pk,
            "name": role.name,
            "description": role.description,
            "reason": "test",
            "platform_operation": True,
            "permissions": [BusinessPermissionCode.MEMBERSHIP_VIEW],
        }
        with self.assertRaises(ValidationError):
            update_organization_role(**kwargs)
        with self.assertRaises(PermissionDenied):
            update_organization_role(**kwargs, expected_updated_at=role.updated_at)

    def test_tenant_catalog_entry_does_not_inherit_platform_definition_authority(self):
        with self.assertRaises(PermissionDenied):
            create_organization_role(
                actor=self.admin,
                organization=self.company,
                code="console-invalid-tenant-role",
                name="Invalid tenant role",
                description="",
                permissions=[BusinessPermissionCode.PROJECTS_VIEW],
                reason="tenant entry requires tenant authority",
                platform_operation=False,
            )
        self.assertFalse(
            OrganizationRole.objects.filter(code="console-invalid-tenant-role").exists()
        )

    def test_explicit_tenant_authority_can_assign_and_revoke_through_console(self):
        company = create_organization_with_owner(
            owner=self.admin, name="Delegation Co", slug="console-delegation"
        )
        context_company = create_organization_with_owner(
            owner=self.admin, name="Working Co", slug="console-context"
        )
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(context_company.pk)
        session.save()
        approver = OrganizationMembership.objects.create(
            organization=company,
            user=self.owner,
            status=MembershipStatus.ACTIVE,
            role=MembershipRole.COMPANY_OWNER,
            role_definition=OrganizationRole.objects.get(
                code=MembershipRole.COMPANY_OWNER, organization__isnull=True
            ),
        )
        bootstrap_membership_authorization(
            membership=approver, actor=self.owner, source="bootstrap"
        )
        target = OrganizationMembership.objects.create(
            organization=company,
            user=User.objects.create_user(username="console-target"),
            status=MembershipStatus.ACTIVE,
            role=MembershipRole.MEMBER,
        )
        listing = self.client.get(
            reverse("organizations:platform_member_roles"), {"organization": company.pk}
        )
        self.assertContains(listing, target.user.username)
        url = reverse(
            "organizations:platform_member_authorization", args=[company.pk, target.pk]
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        role = OrganizationRole.objects.get(
            code=MembershipRole.VIEWER, organization__isnull=True
        )
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "action": "assign_role",
                    "role-role": role.pk,
                    "role-approver_membership": approver.pk,
                    "role-reason": "delegation test",
                },
            ),
            url,
        )
        assignment = target.role_assignments.get(role=role)
        forged_url = reverse(
            "organizations:platform_member_authorization",
            args=[company.pk, approver.pk],
        )
        payload = {
            "action": "revoke_role",
            "assignment_id": assignment.pk,
            "approver_membership_id": approver.pk,
            "reason": "end delegation",
        }
        self.assertEqual(self.client.post(forged_url, payload).status_code, 404)
        self.assertRedirects(self.client.post(url, payload), url)
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.revoked_at)
        self.assertEqual(
            self.client.session[ACTIVE_ORGANIZATION_SESSION_KEY],
            str(context_company.pk),
        )

    def test_platform_login_default_and_no_self_owner_assignment(self):
        self.assertRedirects(
            self.client.get(reverse("accounts:login")),
            reverse("organizations:platform_dashboard"),
        )
        with self.assertRaises(ValidationError):
            create_organization_by_system_admin(
                actor=self.admin, owner=self.admin, name="Self Co", slug="console-self"
            )
        self.assertFalse(Organization.objects.filter(slug="console-self").exists())

    def test_platform_settings_reject_financial_configuration_changes(self):
        original_currency = self.company.settings.currency
        with self.assertRaises(ValidationError):
            update_platform_company(
                actor=self.admin,
                organization_id=self.company.pk,
                expected_updated_at=self.company.updated_at,
                reason="attempt financial setting change",
                profile_data={"name": "Rejected name"},
                settings_data={"currency": "USD"},
            )
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "Console Co")
        self.assertEqual(self.company.settings.currency, original_currency)
        self.assertFalse(
            AuditEvent.objects.filter(
                organization=self.company,
                action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            ).exists()
        )

    def test_platform_permissions_cannot_be_transferred_into_business_roles(self):
        permissions = (
            BusinessPermissionCode.PLATFORM_ADMIN_MANAGE_OPERATORS,
            BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_AUDIT,
            BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_HEALTH,
        )
        self.assertFalse(
            OrganizationRole.objects.filter(permissions__code__in=permissions).exists()
        )
        for permission in permissions:
            with (
                self.subTest(permission=permission),
                self.assertRaises(ValidationError),
            ):
                create_organization_role(
                    actor=self.admin,
                    organization=self.company,
                    code="console-forbidden-platform-permission",
                    name="Forbidden platform permission",
                    description="",
                    permissions=[permission],
                    reason="must remain platform authority",
                    platform_operation=True,
                )

    def test_dashboard_counts_and_history_use_actual_safe_records(self):
        now = timezone.now()
        for status in ("suspended", "cancelled", "archived"):
            Organization.objects.create(
                name=f"Dashboard {status}",
                slug=f"dashboard-{status}",
                status=status,
                archived_at=now if status == "archived" else None,
            )
        Organization.objects.create(
            name="Second archived",
            slug="dashboard-archived-timestamp",
            status="archived",
            archived_at=now,
        )
        Organization.objects.create(
            name="Deleted", slug="dashboard-deleted", deleted_at=now
        )
        record_audit_event(
            action=AuditAction.ROLE_UPDATED,
            entity_type="organizations.OrganizationRole",
            actor=self.admin,
            metadata={"note": "private-dashboard-marker"},
        )
        with patch("django.utils.timezone.now", return_value=now - timedelta(days=9)):
            record_audit_event(
                action=AuditAction.ROLE_UPDATED,
                entity_type="organizations.OrganizationRole",
                actor=self.admin,
            )
        record_audit_event(
            action=AuditAction.PROJECT_CREATED,
            entity_type="projects.Project",
            actor=self.owner,
            organization=self.company,
        )
        response = self.client.get(reverse("organizations:platform_dashboard"))
        self.assertEqual(
            response.context["counts"],
            {"total": 5, "active": 1, "suspended": 1, "cancelled": 1, "archived": 2},
        )
        self.assertEqual(len(response.context["kpis"]), 5)
        self.assertEqual(response.context["registered_users"], User.objects.count())
        self.assertEqual(
            response.context["memberships"], OrganizationMembership.objects.count()
        )
        self.assertEqual(
            sum(row["value"] for row in response.context["company_status_rows"]), 5
        )
        self.assertEqual(response.context["activity_total"], 2)
        self.assertEqual(len(response.context["activity_rows"]), 7)
        self.assertEqual(
            sum(row["value"] for row in response.context["activity_rows"]), 2
        )
        self.assertContains(response, self.admin.username)
        self.assertNotContains(response, "private-dashboard-marker")
        for route in (
            "create",
            "platform_role_catalog",
            "platform_administrators",
            "platform_settings",
        ):
            self.assertEqual(
                self.client.get(reverse(f"organizations:{route}")).status_code, 200
            )

    def test_dashboard_hides_unavailable_actions_and_handles_zero_companies(self):
        BusinessPermission.objects.filter(
            code__in=(
                BusinessPermissionCode.PLATFORM_ADMIN_MANAGE_OPERATORS,
                BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_AUDIT,
                BusinessPermissionCode.PLATFORM_ADMIN_INSPECT_HEALTH,
            )
        ).update(is_active=False)
        Organization.objects.update(deleted_at=timezone.now())
        response = self.client.get(reverse("organizations:platform_dashboard"))
        self.assertEqual(response.context["counts"]["total"], 0)
        self.assertEqual(response.context["company_status_rows"], [])
        self.assertEqual(response.context["activity_rows"], [])
        self.assertEqual(response.context["health_signals"], ())
        self.assertFalse(response.context["can_manage_operators"])
        self.assertContains(response, "هنوز شرکتی ثبت نشده است.")
        self.assertContains(response, "تأیید نشده")
        self.assertContains(
            response,
            f'href="{reverse("organizations:platform_administrators")}"',
            count=2,
        )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_status_sanitizes_probe_failures_and_marks_missing_sources_unverified(self):
        with (
            patch(
                "apps.organizations.platform_console.probe_database",
                side_effect=RuntimeError("synthetic-connection-detail"),
            ),
            patch("apps.organizations.platform_console.probe_cache"),
            patch(
                "apps.organizations.platform_console.recent_operations_alerts",
                return_value=None,
            ),
        ):
            response = self.client.get(reverse("organizations:platform_status"))
        self.assertEqual(
            response.context["health_signals"],
            ["database.unreachable", "cache.unverified"],
        )
        self.assertFalse(response.context["alert_source_available"])
        self.assertContains(response, "تأیید نشده")
        self.assertNotContains(response, "synthetic-connection-detail")
