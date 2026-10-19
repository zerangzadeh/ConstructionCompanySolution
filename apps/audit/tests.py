from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import (
    get_organization_audit_events,
    record_audit_event,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipStatus,
    Organization,
)
from apps.organizations.services import set_active_organization


class AuditServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="audit-user",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-audit-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Audit Company",
            slug="audit-company",
            created_by=self.user,
            updated_by=self.user,
        )
        self.other_organization = Organization.objects.create(
            name="Other Audit Company",
            slug="other-audit-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.other_organization.memberships.create(
            user=self.other_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        for organization in (self.organization, self.other_organization):
            organization.memberships.get().scope_grants.create(
                organization=organization,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="Explicit Audit test organization scope",
            )

    def test_record_audit_event_persists_metadata(self) -> None:
        event = record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.organization.pk,
            organization=self.organization,
            actor=self.user,
            metadata={"name": self.organization.name},
        )

        self.assertEqual(event.organization, self.organization)
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.metadata["name"], "Audit Company")

    def test_record_audit_event_rejects_sensitive_metadata(self) -> None:
        with self.assertRaisesMessage(
            ValueError,
            "فراداده ممیزی نباید شامل مقادیر حساس باشد.",
        ):
            record_audit_event(
                action=AuditAction.ORGANIZATION_CREATED,
                entity_type="organization",
                entity_id=self.organization.pk,
                organization=self.organization,
                actor=self.user,
                metadata={"request": {"access_token": "sensitive"}},
            )

    def test_record_audit_event_rejects_actor_from_another_organization(self) -> None:
        with self.assertRaises(PermissionDenied):
            record_audit_event(
                action=AuditAction.ORGANIZATION_CREATED,
                entity_type="organization",
                entity_id=self.organization.pk,
                organization=self.organization,
                actor=self.other_user,
            )

    def test_events_are_scoped_to_member_organization(self) -> None:
        record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.organization.pk,
            organization=self.organization,
            actor=self.user,
        )
        record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.other_organization.pk,
            organization=self.other_organization,
            actor=self.other_user,
        )

        events = get_organization_audit_events(
            user=self.user,
            organization=self.organization,
        )

        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().organization, self.organization)

    def test_events_reject_non_member(self) -> None:
        with self.assertRaises(PermissionDenied):
            get_organization_audit_events(
                user=self.other_user,
                organization=self.organization,
            )

    def test_audit_events_are_append_only(self) -> None:
        event = record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.organization.pk,
            organization=self.organization,
            actor=self.user,
        )

        event.action = AuditAction.PROJECT_CREATED
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).update(
                action=AuditAction.PROJECT_CREATED
            )
        with self.assertRaises(ValidationError):
            AuditEvent.objects.filter(pk=event.pk).delete()

    def test_audit_view_shows_only_active_organization_events(self) -> None:
        record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.organization.pk,
            organization=self.organization,
            actor=self.user,
        )
        record_audit_event(
            action=AuditAction.ORGANIZATION_CREATED,
            entity_type="organization",
            entity_id=self.other_organization.pk,
            organization=self.other_organization,
            actor=self.other_user,
        )
        self.client.force_login(self.user)
        set_active_organization(self.client.session, self.organization)
        self.client.session.save()

        response = self.client.get(reverse("audit:log"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Company")
        self.assertNotContains(response, "Other Audit Company")
