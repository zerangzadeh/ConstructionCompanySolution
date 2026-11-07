from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    Organization,
    OrganizationStatus,
    PlatformRoleAssignment,
)
from apps.organizations.permission_registry import PLATFORM_COMPANY_PERMISSIONS
from apps.organizations.platform_companies import (
    change_company_status,
    update_platform_company,
)
from apps.organizations.role_defaults import DEFAULT_ROLE_PERMISSIONS
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
    get_valid_memberships,
)


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class PlatformCompanyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser(
            username="company-root", email="root@example.test"
        )
        cls.admin = User.objects.create_user(username="company-admin")
        assign_platform_admin(
            actor=cls.root,
            approver=cls.root,
            target=cls.admin,
            reason="Company oversight",
        )
        cls.owner = User.objects.create_user(username="company-owner")
        cls.company = create_organization_with_owner(
            owner=cls.owner, name="شرکت اول", slug="platform-first"
        )
        cls.other = create_organization_with_owner(
            owner=cls.owner, name="شرکت دوم", slug="platform-second"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def url(self, name="detail", company=None):
        return reverse(
            f"organizations:platform_company_{name}",
            args=[(company or self.company).pk],
        )

    def status_data(self, target=OrganizationStatus.SUSPENDED):
        self.company.refresh_from_db()
        return {
            "target_status": target,
            "reason": "درخواست پشتیبانی",
            "expected_updated_at": self.company.updated_at.isoformat(),
        }

    def edit_data(self):
        self.company.refresh_from_db()
        response = self.client.get(self.url("edit"))
        data = {
            "reason": "تصحیح مشخصات",
            "expected_updated_at": self.company.updated_at.isoformat(),
        }
        for key in ("profile_form", "settings_form"):
            form = response.context[key]
            data.update(
                {
                    form.add_prefix(name): form[name].value() or ""
                    for name in form.fields
                }
            )
        return data

    def test_list_and_activity_are_platform_scoped_without_selecting_a_tenant(self):
        response = self.client.get(reverse("organizations:platform_company_list"))
        self.assertContains(response, self.company.name)
        self.assertContains(response, self.other.name)
        self.assertContains(
            self.client.get(reverse("home")),
            reverse("organizations:platform_company_list"),
        )
        event = record_audit_event(
            action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            actor=self.owner,
            organization=self.company,
            entity_type="organization",
            metadata={"private_test_value": "hidden-payload-marker"},
        )
        foreign = record_audit_event(
            action=AuditAction.PROJECT_CREATED,
            actor=self.owner,
            organization=self.other,
            entity_type="private-other-record",
        )
        response = self.client.get(self.url())
        self.assertIn(event, response.context["events"])
        self.assertNotIn(foreign, response.context["events"])
        self.assertNotContains(response, "hidden-payload-marker")
        self.assertNotContains(response, "private-other-record")
        self.assertNotIn(ACTIVE_ORGANIZATION_SESSION_KEY, self.client.session)
        self.assertFalse(self.company.memberships.filter(user=self.admin).exists())

    def test_filters_pagination_and_unknown_company(self):
        url = reverse("organizations:platform_company_list")
        response = self.client.get(url, {"q": "platform-first"})
        self.assertEqual(
            [item.pk for item in response.context["companies"]], [self.company.pk]
        )
        self.assertEqual(
            self.client.get(url, {"status": "invalid"}).context["companies"], []
        )
        response = self.client.get(
            self.url(), {"q": "no-such-actor", "page": "invalid"}
        )
        self.assertEqual(response.context["events"], [])
        self.assertEqual(
            self.client.get(
                reverse("organizations:platform_company_detail", args=[uuid4()])
            ).status_code,
            404,
        )

    def test_owner_and_superuser_without_platform_duty_cannot_read_or_write(self):
        for user in (self.owner, self.root):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(
                    reverse("organizations:platform_company_list")
                ).status_code,
                403,
            )
            for name in ("detail", "edit", "status"):
                with self.subTest(user=user.username, route=name):
                    self.assertEqual(self.client.get(self.url(name)).status_code, 403)
                    self.assertEqual(
                        self.client.post(
                            self.url(name), self.status_data()
                        ).status_code,
                        403,
                    )

    def test_anonymous_and_csrf_guards(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(
            csrf_client.post(self.url("status"), self.status_data()).status_code, 403
        )
        self.assertEqual(csrf_client.post(self.url("edit"), {}).status_code, 403)

    def test_platform_permissions_have_no_tenant_default_grants(self):
        for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            with self.subTest(role=role):
                self.assertFalse(permissions & PLATFORM_COMPANY_PERMISSIONS)
        BusinessPermission.objects.filter(
            code=BusinessPermissionCode.PLATFORM_COMPANIES_CHANGE_STATUS
        ).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            change_company_status(
                actor=self.admin,
                organization_id=self.company.pk,
                target_status="suspended",
                reason="test",
                expected_updated_at=self.company.updated_at,
            )

    def test_suspend_and_reactivate_preserve_memberships_and_audit_transitions(self):
        membership = self.company.memberships.get(user=self.owner)
        data = self.status_data()
        self.assertEqual(self.client.get(self.url("status")).status_code, 405)
        self.assertEqual(self.client.post(self.url("status"), data).status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.status, OrganizationStatus.SUSPENDED)
        self.assertNotIn(
            self.company.pk,
            get_valid_memberships(self.owner).values_list("organization_id", flat=True),
        )
        self.assertContains(self.client.get(self.url()), self.company.name)
        event = AuditEvent.objects.get(
            organization=self.company, action=AuditAction.ORGANIZATION_STATUS_CHANGED
        )
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(
            event.changes["status"], {"before": "active", "after": "suspended"}
        )
        self.assertEqual(event.metadata["reason"], data["reason"])
        self.client.post(
            self.url("status"), self.status_data(OrganizationStatus.ACTIVE)
        )
        self.company.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(self.company.status, OrganizationStatus.ACTIVE)
        self.assertEqual(membership.status, "active")
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.company,
                action=AuditAction.ORGANIZATION_STATUS_CHANGED,
            ).count(),
            2,
        )

    def test_stale_or_invalid_status_and_blank_reason_cannot_mutate(self):
        stale = self.status_data()
        self.client.post(self.url("status"), stale)
        stale["target_status"] = OrganizationStatus.ACTIVE
        self.client.post(self.url("status"), stale)
        self.company.refresh_from_db()
        self.assertEqual(self.company.status, OrganizationStatus.SUSPENDED)
        for data in (
            {**self.status_data(), "target_status": "cancelled"},
            {**self.status_data(), "reason": " "},
        ):
            self.client.post(self.url("status"), data)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.company,
                action=AuditAction.ORGANIZATION_STATUS_CHANGED,
            ).count(),
            1,
        )

    def test_settings_reuse_authoritative_configuration_and_record_reason(self):
        data = self.edit_data()
        legacy_timezone = self.company.timezone
        data["profile-name"] = "شرکت اصلاح‌شده"
        data["settings-timezone"] = "Asia/Tehran"
        response = self.client.post(self.url("edit"), data)
        self.assertRedirects(response, self.url())
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, data["profile-name"])
        self.assertEqual(self.company.settings.timezone, "Asia/Tehran")
        self.assertEqual(self.company.timezone, legacy_timezone)
        event = AuditEvent.objects.get(
            organization=self.company, action=AuditAction.ORGANIZATION_SETTINGS_UPDATED
        )
        self.assertEqual(event.metadata["reason"], data["reason"])
        self.assertIn("name", event.metadata["profile_changed_fields"])
        self.assertEqual(event.actor, self.admin)
        self.assertNotIn(ACTIVE_ORGANIZATION_SESSION_KEY, self.client.session)

    def test_edit_rejects_stale_version_and_invalid_configuration(self):
        data = self.edit_data()
        self.client.post(self.url("status"), self.status_data())
        data["profile-name"] = "stale-overwrite"
        self.assertContains(
            self.client.post(self.url("edit"), data), "اطلاعات شرکت تغییر کرده"
        )
        self.company.refresh_from_db()
        self.assertNotEqual(self.company.name, "stale-overwrite")
        data = self.edit_data()
        data["settings-timezone"] = "Invalid/Zone"
        self.client.post(self.url("edit"), data)
        self.assertFalse(
            AuditEvent.objects.filter(
                organization=self.company,
                action=AuditAction.ORGANIZATION_SETTINGS_UPDATED,
            ).exists()
        )

    def test_cancelled_and_archived_companies_remain_inspectable(self):
        for status in (OrganizationStatus.CANCELLED, OrganizationStatus.ARCHIVED):
            Organization.objects.filter(pk=self.company.pk).update(
                status=status,
                archived_at=timezone.now() if status == "archived" else None,
            )
            self.assertContains(self.client.get(self.url()), self.company.name)
            with self.assertRaises(ValidationError):
                change_company_status(
                    actor=self.admin,
                    organization_id=self.company.pk,
                    **{
                        **self.status_data(),
                        "expected_updated_at": self.company.updated_at,
                    },
                )
            with self.assertRaises(ValidationError):
                update_platform_company(
                    actor=self.admin,
                    organization_id=self.company.pk,
                    expected_updated_at=self.company.updated_at,
                    reason="blocked",
                    profile_data={"name": "forbidden"},
                    settings_data={},
                )

    def test_status_and_settings_roll_back_when_audit_fails(self):
        for target in ("status", "settings"):
            with self.subTest(target=target):
                self.company.refresh_from_db()
                original_name = self.company.name
                patch_target = (
                    "apps.organizations.platform_companies.record_audit_event"
                    if target == "status"
                    else "apps.organizations.services.record_audit_event"
                )
                with (
                    patch(patch_target, side_effect=RuntimeError("audit unavailable")),
                    self.assertRaises(RuntimeError),
                ):
                    if target == "status":
                        change_company_status(
                            actor=self.admin,
                            organization_id=self.company.pk,
                            target_status="suspended",
                            reason="test",
                            expected_updated_at=self.company.updated_at,
                        )
                    else:
                        update_platform_company(
                            actor=self.admin,
                            organization_id=self.company.pk,
                            expected_updated_at=self.company.updated_at,
                            reason="test",
                            profile_data={"name": "rollback"},
                            settings_data={"timezone": "Asia/Tehran"},
                        )
                self.company.refresh_from_db()
                self.assertEqual(self.company.status, "active")
                self.assertEqual(self.company.name, original_name)
                self.assertEqual(self.company.settings.timezone, "UTC")

    def test_mutations_recheck_expired_revoked_and_inactive_platform_authority(self):
        assignment = PlatformRoleAssignment.objects.get(user=self.admin)
        for change in (
            {
                "ends_at": timezone.now() - timedelta(seconds=1),
                "starts_at": timezone.now() - timedelta(days=1),
            },
            {"revoked_at": timezone.now(), "ends_at": None},
        ):
            PlatformRoleAssignment.objects.filter(pk=assignment.pk).update(**change)
            with self.assertRaises(PermissionDenied):
                change_company_status(
                    actor=self.admin,
                    organization_id=self.company.pk,
                    target_status="suspended",
                    reason="test",
                    expected_updated_at=self.company.updated_at,
                )
        PlatformRoleAssignment.objects.filter(pk=assignment.pk).update(revoked_at=None)
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            update_platform_company(
                actor=self.admin,
                organization_id=self.company.pk,
                expected_updated_at=self.company.updated_at,
                reason="test",
                profile_data={},
                settings_data={},
            )
