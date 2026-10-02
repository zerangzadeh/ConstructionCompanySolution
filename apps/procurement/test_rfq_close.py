from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRole,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
)
from apps.parties.models import BusinessParty, PartyKind, PartyRole, PartyRoleType
from apps.procurement.models import (
    QuoteRevision,
    QuoteRevisionStatus,
    RequestForQuotation,
    RequestForQuotationStatus,
    RFQCloseEntryDisposition,
    RFQCloseManifest,
    RFQCloseManifestEntry,
)
from apps.procurement.quote_services import (
    capture_quote_revision,
    submit_quote_revision,
    withdraw_quote_revision,
)
from apps.procurement.rfq_services import (
    add_rfq_line,
    close_rfq,
    create_rfq,
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.tests import ProcurementFixtureMixin
from apps.projects.models import Project


class RFQCloseFixtureMixin(ProcurementFixtureMixin):
    def _issued(self, *, include_absent_invitation: bool = False):
        request, item = self.create_approved_request()
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=request,
            rfq_number="RFQ-CLOSE-001",
            title="Custody close test",
            closing_at=now + timedelta(days=2),
            earliest_opening_at=now + timedelta(days=2),
        )
        add_rfq_line(
            organization=self.organization,
            actor=self.member,
            rfq=rfq,
            purchase_request_item=item,
            quantity=Decimal("10.0000"),
        )
        submit_rfq_for_issue(organization=self.organization, actor=self.member, rfq=rfq)
        suppliers = [self.supplier]
        if include_absent_invitation:
            absent_supplier = BusinessParty.objects.create(
                organization=self.organization,
                display_name="Absent Supplier",
                party_kind=PartyKind.COMPANY,
            )
            PartyRole.objects.create(
                organization=self.organization,
                party=absent_supplier,
                role=PartyRoleType.SUPPLIER,
            )
            suppliers.append(absent_supplier)
        version = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=suppliers,
            idempotency_key="close-test-issue",
        )
        return rfq, version, version.invitations.get(supplier=self.supplier)

    def _grant_close(self, user=None) -> None:
        user = user or self.owner
        membership = self.organization.memberships.get(user=user)
        permission = BusinessPermission.objects.get(
            code=BusinessPermissionCode.RFQS_CLOSE_CUSTODY
        )
        membership.role_definition.permissions.add(permission)

    def _close_after_deadline(self, *, rfq, version, key="close-001", actor=None):
        with patch(
            "apps.procurement.rfq_services.timezone.now",
            return_value=version.closing_at + timedelta(seconds=1),
        ):
            return close_rfq(
                organization=self.organization,
                actor=actor or self.owner,
                rfq=rfq,
                idempotency_key=key,
            )


class RFQCloseManifestTests(RFQCloseFixtureMixin, TestCase):
    def test_permission_has_no_default_owner_or_platform_bypass_and_deadline_holds(
        self,
    ):
        rfq, _, _ = self._issued()
        with self.assertRaises(PermissionDenied):
            close_rfq(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                idempotency_key="denied-owner",
            )
        admin_user = User.objects.create_user(username="tenant-admin-close")
        self.organization.memberships.create(
            user=admin_user,
            role=MembershipRole.TENANT_ADMIN,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            close_rfq(
                organization=self.organization,
                actor=admin_user,
                rfq=rfq,
                idempotency_key="denied-admin",
            )
        platform_user = User.objects.create_superuser(
            username="platform-close", password="x"
        )
        with self.assertRaises(PermissionDenied):
            close_rfq(
                organization=self.organization,
                actor=platform_user,
                rfq=rfq,
                idempotency_key="denied-platform",
            )
        self._grant_close()
        with self.assertRaises(ValueError):
            close_rfq(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                idempotency_key="too-early",
            )

    def test_close_permission_is_intersected_with_project_scope(self):
        rfq, version, _ = self._issued()
        self._grant_close(user=self.member)
        membership = self.organization.memberships.get(user=self.member)
        other_project = Project.objects.create(
            organization=self.organization, code="OTHER-SCOPE", name="Other Scope"
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=membership.role_definition,
            reason="P5-S07 object-scope test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type=AuthorizationScopeType.PROJECT,
            project=other_project,
            reason="P5-S07 object-scope test",
        )
        type(membership).objects.filter(pk=membership.pk).update(
            authorization_migrated_at=timezone.now()
        )
        with (
            patch(
                "apps.procurement.rfq_services.timezone.now",
                return_value=version.closing_at + timedelta(seconds=1),
            ),
            self.assertRaises(PermissionDenied),
        ):
            close_rfq(
                organization=self.organization,
                actor=self.member,
                rfq=rfq,
                idempotency_key="wrong-project-scope",
            )

    def test_close_freezes_effective_revision_and_excluded_metadata(self):
        rfq, version, invitation = self._issued(include_absent_invitation=True)
        self._grant_close()
        first = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="a" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-first",
        )
        submit_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=first,
            idempotency_key="submit-first",
        )
        effective = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="b" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-effective",
        )
        submit_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=effective,
            idempotency_key="submit-effective",
        )
        withdrawn = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="c" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-withdrawn",
        )
        withdraw_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=withdrawn,
            idempotency_key="withdraw-close-test",
        )
        capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="d" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-unsubmitted",
        )
        with patch(
            "apps.procurement.quote_services.timezone.now",
            return_value=version.closing_at + timedelta(milliseconds=1),
        ):
            capture_quote_revision(
                organization=self.organization,
                actor=self.member,
                invitation=invitation,
                integrity_fingerprint="e" * 64,
                source_channel="manual_capture",
                idempotency_key="capture-late",
            )

        manifest = self._close_after_deadline(rfq=rfq, version=version)
        entry = manifest.entries.get(invitation=invitation)
        absent = manifest.entries.exclude(invitation=invitation).get()
        self.assertEqual(entry.effective_revision_id, effective.pk)
        self.assertEqual(
            entry.disposition, RFQCloseEntryDisposition.EFFECTIVE_SUBMITTED
        )
        self.assertEqual(entry.revision_count, 5)
        self.assertEqual(entry.captured_unsubmitted_count, 2)
        self.assertEqual(entry.withdrawn_count, 1)
        self.assertEqual(entry.superseded_count, 1)
        self.assertEqual(entry.late_count, 1)
        self.assertEqual(
            absent.disposition, RFQCloseEntryDisposition.NO_EFFECTIVE_SUBMISSION
        )
        self.assertIsNone(absent.effective_revision_id)
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, RequestForQuotationStatus.CLOSED)
        event = AuditEvent.objects.get(
            action=AuditAction.RFQ_CLOSED, entity_id=str(rfq.pk)
        )
        self.assertEqual(event.metadata["manifest_id"], str(manifest.pk))
        self.assertEqual(
            event.metadata["payload_fingerprint"], manifest.payload_fingerprint
        )

    def test_idempotency_immutability_and_post_close_evidence_never_supplement_manifest(
        self,
    ):
        rfq, version, invitation = self._issued()
        self._grant_close()
        manifest = self._close_after_deadline(rfq=rfq, version=version)
        retry = self._close_after_deadline(rfq=rfq, version=version)
        self.assertEqual(retry.pk, manifest.pk)
        with self.assertRaises(ValueError):
            self._close_after_deadline(rfq=rfq, version=version, key="different-key")
        before = manifest.entries.get(invitation=invitation)
        fingerprint = manifest.payload_fingerprint
        with patch(
            "apps.procurement.quote_services.timezone.now",
            return_value=version.closing_at + timedelta(seconds=2),
        ):
            post_close = capture_quote_revision(
                organization=self.organization,
                actor=self.member,
                invitation=invitation,
                integrity_fingerprint="f" * 64,
                source_channel="manual_capture",
                idempotency_key="post-close-capture",
            )
        self.assertTrue(post_close.is_late)
        manifest.refresh_from_db()
        before.refresh_from_db()
        self.assertEqual(manifest.payload_fingerprint, fingerprint)
        self.assertEqual(before.revision_count, 0)
        manifest.payload_fingerprint = "0" * 64
        with self.assertRaises(ValidationError):
            manifest.save()
        with self.assertRaises(ValidationError):
            RFQCloseManifest.objects.filter(pk=manifest.pk).update(
                payload_fingerprint="0" * 64
            )
        with self.assertRaises(ValidationError):
            RFQCloseManifestEntry.objects.filter(pk=before.pk).delete()

    def test_cross_tenant_and_non_effective_late_submission_are_excluded(self):
        rfq, version, invitation = self._issued()
        self._grant_close()
        late = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="1" * 64,
            source_channel="manual_capture",
            idempotency_key="late-tamper",
        )
        QuoteRevision.objects.filter(pk=late.pk).update(
            status=QuoteRevisionStatus.SUBMITTED,
            submitted_at=version.closing_at + timedelta(seconds=1),
            is_late=True,
        )
        with self.assertRaises(PermissionDenied):
            close_rfq(
                organization=self.other_organization,
                actor=self.outsider,
                rfq=rfq,
                idempotency_key="cross-tenant",
            )
        manifest = self._close_after_deadline(rfq=rfq, version=version)
        entry = manifest.entries.get(invitation=invitation)
        self.assertIsNone(entry.effective_revision_id)
        self.assertEqual(entry.late_count, 1)

    def test_database_allows_at_most_one_active_submitted_revision(self):
        _, _, invitation = self._issued()
        first = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="2" * 64,
            source_channel="manual_capture",
            idempotency_key="constraint-first",
        )
        second = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="3" * 64,
            source_channel="manual_capture",
            idempotency_key="constraint-second",
        )
        QuoteRevision.objects.filter(pk=first.pk).update(
            status=QuoteRevisionStatus.SUBMITTED, submitted_at=timezone.now()
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            QuoteRevision.objects.filter(pk=second.pk).update(
                status=QuoteRevisionStatus.SUBMITTED, submitted_at=timezone.now()
            )

    def test_audit_failure_rolls_back_manifest_entries_and_rfq_state(self):
        rfq, version, _ = self._issued()
        self._grant_close()
        with (
            patch(
                "apps.procurement.rfq_services.timezone.now",
                return_value=version.closing_at + timedelta(seconds=1),
            ),
            patch(
                "apps.procurement.rfq_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            close_rfq(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                idempotency_key="rollback-close",
            )
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, RequestForQuotationStatus.ISSUED)
        self.assertFalse(RFQCloseManifest.objects.filter(rfq=rfq).exists())


class RFQCloseConcurrencyTests(RFQCloseFixtureMixin, TransactionTestCase):
    def test_concurrent_identical_close_creates_one_manifest(self):
        rfq, version, _ = self._issued()
        self._grant_close()
        barrier = Barrier(2)
        closed_at = version.closing_at + timedelta(seconds=1)

        def close_once() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                with patch(
                    "apps.procurement.rfq_services.timezone.now", return_value=closed_at
                ):
                    manifest = close_rfq(
                        organization=Organization.objects.get(pk=self.organization.pk),
                        actor=User.objects.get(pk=self.owner.pk),
                        rfq=RequestForQuotation.objects.get(pk=rfq.pk),
                        idempotency_key="concurrent-close",
                    )
                return str(manifest.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            manifest_ids = list(pool.map(lambda _: close_once(), range(2)))

        self.assertEqual(manifest_ids[0], manifest_ids[1])
        self.assertEqual(RFQCloseManifest.objects.filter(rfq=rfq).count(), 1)
