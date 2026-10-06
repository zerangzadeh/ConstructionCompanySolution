"""Focused P9-S25 privacy, evidence, notification, and boundary assurance."""

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.compliance.models import ComplianceEvidenceLink
from apps.daily_reports.field_models import FieldObservationEvidenceLink
from apps.daily_reports.field_services import create_field_observation
from apps.knowledge.models import KnowledgeSourcePin
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import set_active_organization
from apps.partner_qualification.models import PartnerEvidence
from apps.projects.models import Project
from apps.support.models import Notification, SupportCase, SupportEvidence
from apps.support.services import create_notification


class P9S25CrossDomainAssuranceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="s25-owner")
        self.viewer = User.objects.create_user(username="s25-viewer")
        self.recipient = User.objects.create_user(username="s25-recipient")
        self.other = User.objects.create_user(username="s25-other")
        self.outsider = User.objects.create_user(username="s25-outsider")
        self.organization = Organization.objects.create(
            name="P9 S25", slug="p9-s25", created_by=self.owner
        )
        self.other_organization = Organization.objects.create(
            name="P9 S25 Other", slug="p9-s25-other", created_by=self.other
        )
        OrganizationSettings.objects.create(organization=self.organization)
        OrganizationSettings.objects.create(organization=self.other_organization)

        p9_permissions = BusinessPermission.objects.filter(
            code__in=[
                code
                for code in BusinessPermissionCode.values
                if code.startswith(
                    ("field.", "compliance.", "partner.", "support.", "knowledge.")
                )
            ]
        )
        self.full_role = OrganizationRole.objects.create(
            code="p9_s25_full", name="P9 S25 full"
        )
        self.full_role.permissions.add(*p9_permissions)
        self.viewer_role = OrganizationRole.objects.create(
            code="p9_s25_viewer", name="P9 S25 viewer"
        )
        self.viewer_role.permissions.add(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.FIELD_OBSERVATIONS_VIEW
            )
        )
        self.recipient_role = OrganizationRole.objects.create(
            code="p9_s25_recipient", name="P9 S25 recipient"
        )
        self.recipient_role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    BusinessPermissionCode.SUPPORT_NOTIFICATIONS_VIEW,
                    BusinessPermissionCode.SUPPORT_NOTIFICATIONS_ACKNOWLEDGE,
                    BusinessPermissionCode.SUPPORT_CASE_VIEW,
                )
            )
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.recipient,
            role_definition=self.recipient_role,
            status=MembershipStatus.ACTIVE,
        )
        OrganizationMembership.objects.create(
            organization=self.other_organization,
            user=self.other,
            role_definition=self.full_role,
            status=MembershipStatus.ACTIVE,
        )
        self.project = Project.objects.create(
            organization=self.organization,
            code="S25",
            name="S25 assurance",
            created_by=self.owner,
        )
        self.observation = create_field_observation(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=None,
            kind="general",
            title="Sensitive location",
            summary="Safe field summary",
            location_permission="granted",
            latitude=Decimal("35.700001"),
            longitude=Decimal("51.400001"),
            horizontal_accuracy_meters=Decimal("12.00"),
            location_captured_at=timezone.now(),
            client_context={"platform": "android", "device_id": "discarded"},
            operation_key=uuid4(),
        )
        self.case = SupportCase.objects.create(
            organization=self.organization,
            requester=self.owner,
            category="assurance",
            summary="Authorized safe summary",
        )

    def _login(self, user, organization=None):
        self.client.force_login(user)
        set_active_organization(self.client.session, organization or self.organization)

    def _notification(self, **overrides):
        values = {
            "organization": self.organization,
            "actor": self.recipient,
            "recipient": self.recipient,
            "source_type": "support_case",
            "source_id": self.case.pk,
            "source_version": "1",
            "category": "attention",
            "summary": "Minimized safe label",
            "operation_key": uuid4(),
        }
        values.update(overrides)
        return create_notification(**values)

    def test_01_sensitive_permissions_are_distinct_and_registered(self):
        codes = {
            BusinessPermissionCode.FIELD_OBSERVATIONS_LOCATION_VIEW,
            BusinessPermissionCode.COMPLIANCE_SENSITIVE_EVIDENCE_VIEW,
            BusinessPermissionCode.PARTNER_SENSITIVE_EVIDENCE_VIEW,
            BusinessPermissionCode.SUPPORT_EVIDENCE_SENSITIVE_VIEW,
            BusinessPermissionCode.KNOWLEDGE_SENSITIVE_PROVENANCE_VIEW,
        }
        self.assertEqual(
            set(
                BusinessPermission.objects.filter(code__in=codes).values_list(
                    "code", flat=True
                )
            ),
            codes,
        )

    def test_02_cross_domain_evidence_models_pin_version_and_hash(self):
        for model in (
            FieldObservationEvidenceLink,
            ComplianceEvidenceLink,
            PartnerEvidence,
            SupportEvidence,
            KnowledgeSourcePin,
        ):
            names = {field.name for field in model._meta.fields}
            self.assertIn("document_version", names)
            self.assertIn("sha256", names)

    def test_03_p9_evidence_models_do_not_store_bytes(self):
        for model in (
            FieldObservationEvidenceLink,
            ComplianceEvidenceLink,
            PartnerEvidence,
            SupportEvidence,
            KnowledgeSourcePin,
        ):
            self.assertFalse(
                any(
                    isinstance(field, (models.FileField, models.BinaryField))
                    for field in model._meta.fields
                )
            )

    def test_04_field_list_masks_precise_location(self):
        self._login(self.viewer)
        response = self.client.get(reverse("daily_reports:field_observation_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "35.700001")
        self.assertNotContains(response, "51.400001")

    def test_05_field_detail_masks_location_and_is_not_cacheable(self):
        self._login(self.viewer)
        response = self.client.get(
            reverse(
                "daily_reports:field_observation_detail", args=[self.observation.pk]
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "35.700001")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertIn("private", response.headers["Cache-Control"])

    def test_06_field_location_permission_reveals_only_authorized_detail(self):
        self._login(self.owner)
        response = self.client.get(
            reverse(
                "daily_reports:field_observation_detail", args=[self.observation.pk]
            )
        )
        self.assertContains(response, "35.700001")
        self.assertContains(response, "شاهد غیرقابل‌اعتماد")

    def test_07_field_detail_is_tenant_scoped(self):
        self._login(self.other, self.other_organization)
        response = self.client.get(
            reverse(
                "daily_reports:field_observation_detail", args=[self.observation.pk]
            )
        )
        self.assertIn(response.status_code, (403, 404))

    def test_08_notification_exact_retry_is_idempotent(self):
        key = uuid4()
        first = self._notification(operation_key=key)
        second = self._notification(operation_key=key)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_09_notification_changed_payload_key_reuse_is_rejected(self):
        key = uuid4()
        self._notification(operation_key=key)
        with self.assertRaises(ValidationError):
            self._notification(operation_key=key, summary="Changed source payload")

    def test_10_notification_requires_registered_existing_source(self):
        with self.assertRaises(PermissionDenied):
            self._notification(source_type="unregistered")
        with self.assertRaises(PermissionDenied):
            self._notification(source_id=uuid4())

    def test_11_notification_recipient_requires_active_tenant_membership(self):
        with self.assertRaises(PermissionDenied):
            self._notification(recipient=self.outsider)

    def test_12_notification_open_rechecks_source_and_disables_cache(self):
        self._notification()
        self._login(self.recipient)
        response = self.client.get(reverse("support:notifications"))
        self.assertContains(response, "Minimized safe label")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertIn("private", response.headers["Cache-Control"])

    def test_13_notification_lost_source_access_masks_cached_summary(self):
        self._notification()
        self.recipient_role.permissions.remove(
            BusinessPermission.objects.get(
                code=BusinessPermissionCode.SUPPORT_CASE_VIEW
            )
        )
        self._login(self.recipient)
        response = self.client.get(reverse("support:notifications"))
        self.assertNotContains(response, "Minimized safe label")
        self.assertContains(response, "منبع اعلان دیگر در دسترس نیست")

    def test_14_notification_list_is_recipient_and_tenant_scoped(self):
        notification = self._notification()
        self._login(self.other, self.other_organization)
        response = self.client.get(reverse("support:notifications"))
        self.assertNotContains(response, str(notification.pk))
        self.assertNotContains(response, "Minimized safe label")

    def test_15_notification_audit_is_minimized_and_has_no_domain_effect(self):
        project_count = Project.objects.count()
        case_count = SupportCase.objects.count()
        notification = self._notification()
        event = AuditEvent.objects.get(
            action=AuditAction.SUPPORT_NOTIFICATION_CREATED,
            entity_id=str(notification.pk),
        )
        self.assertEqual(event.metadata, {})
        self.assertEqual(event.changes, {})
        self.assertEqual(Project.objects.count(), project_count)
        self.assertEqual(SupportCase.objects.count(), case_count)
