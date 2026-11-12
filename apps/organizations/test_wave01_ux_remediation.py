from datetime import timedelta

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.access_services import (
    assign_platform_admin,
    create_protected_operation_version,
)
from apps.organizations.models import Organization, ProtectedOperationCode
from apps.organizations.role_presentation import tenant_selector
from core.jalali import format_jalali


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class Wave01UXRemediationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        root = User.objects.create_superuser(username="ux-test-root")
        cls.admin = User.objects.create_user(username="ux-test-admin")
        assign_platform_admin(
            actor=root, approver=root, target=cls.admin, reason="Synthetic test"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_selector_fallback_stays_available_before_enhancement(self):
        widget = (
            tenant_selector(Organization.objects.none()).fields["organization"].widget
        )
        self.assertEqual(widget.attrs["data-hide-enhanced-source"], "true")
        self.assertNotIn("aria-hidden", widget.attrs)
        self.assertNotIn("disabled", widget.attrs)

    def test_audit_calendar_labels_and_inclusive_date_boundaries(self):
        event = record_audit_event(
            actor=self.admin,
            action=AuditAction.ROLE_UPDATED,
            entity_type="organizations.OrganizationRole",
            entity_id=self.admin.pk,
            metadata={"control_plane": True},
        )
        day = timezone.localtime(event.created_at).date()
        url = reverse("organizations:platform_audit")
        response = self.client.get(
            url, {"start": day.isoformat(), "end": day.isoformat()}
        )
        self.assertContains(response, "از تاریخ شمسی")
        self.assertContains(response, "تا تاریخ شمسی")
        self.assertNotContains(response, "تاریخ میلادی")
        self.assertIn(event, [row[0] for row in response.context["rows"]])
        for outside in (day - timedelta(days=1), day + timedelta(days=1)):
            with self.subTest(outside=outside):
                response = self.client.get(
                    url, {"start": outside.isoformat(), "end": outside.isoformat()}
                )
                self.assertNotIn(event, [row[0] for row in response.context["rows"]])
        response = self.client.get(url, {"start": "not-a-date"})
        self.assertIn("start", response.context["form"].errors)
        self.assertEqual(response.context["rows"], [])

    def test_audit_jalali_invalid_redisplay_and_canonical_conversion(self):
        event = record_audit_event(
            actor=self.admin,
            action=AuditAction.ROLE_UPDATED,
            entity_type="organizations.OrganizationRole",
            entity_id=self.admin.pk,
            metadata={"control_plane": True},
        )
        day = timezone.localtime(event.created_at).date()
        url = reverse("organizations:platform_audit")
        for value in ("1405/13/50", "1405/08", "۱۴۰۵/۱۳/۵۰"):
            with self.subTest(invalid=value):
                response = self.client.get(url, {"start": value})
                self.assertIn("start", response.context["form"].errors)
                self.assertEqual(response.context["rows"], [])
                self.assertContains(response, f'value="{value}"')
                self.assertContains(response, 'aria-invalid="true"')
                self.assertContains(response, 'data-filter-submit="explicit"')
        for value in (format_jalali(day), day.isoformat()):
            with self.subTest(valid=value):
                response = self.client.get(url, {"start": value, "end": value})
                self.assertFalse(response.context["form"].errors)
                self.assertIn(event, [row[0] for row in response.context["rows"]])
                self.assertEqual(response.context["form"].cleaned_data["start"], day)
        response = self.client.get(
            url,
            {"start": day.isoformat(), "end": (day - timedelta(days=1)).isoformat()},
        )
        self.assertIn("end", response.context["form"].errors)
        self.assertEqual(response.context["rows"], [])

    def test_retirement_confirmation_keeps_service_csrf_and_audit_boundaries(self):
        operation = create_protected_operation_version(
            actor=self.admin,
            code=ProtectedOperationCode.values[0],
            name="Synthetic retirement target",
            description="Synthetic version",
            reason="Test setup",
        )
        url = reverse("organizations:protected_operation_catalog")
        response = self.client.get(url)
        self.assertContains(response, "data-confirm-title=")
        self.assertContains(response, "تأیید بازنشستگی نسخه")
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        payload = {
            "action": "retire",
            "code": operation.code,
            "reason": "Test retirement",
        }
        self.assertEqual(strict.post(url, payload).status_code, 403)
        operation.refresh_from_db()
        self.assertIsNone(operation.retired_at)
        before_version = operation.version
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        operation.refresh_from_db()
        self.assertIsNotNone(operation.retired_at)
        self.assertEqual(operation.version, before_version)
        self.assertEqual(operation.retirement_reason, "Test retirement")
