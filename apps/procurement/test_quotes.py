from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.procurement.models import (
    QuoteRevision,
    QuoteRevisionStatus,
    QuoteRevisionTransition,
    RequestForQuotationInvitation,
)
from apps.procurement.quote_services import (
    capture_quote_revision,
    get_organization_quote_revisions,
    submit_quote_revision,
    withdraw_quote_revision,
)
from apps.procurement.rfq_services import (
    add_rfq_line,
    create_rfq,
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.tests import ProcurementFixtureMixin


class QuoteFixtureMixin(ProcurementFixtureMixin):
    def _issued_invitation(self):
        request, item = self.create_approved_request()
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=request,
            rfq_number="RFQ-QUOTE-001",
            title="Sealed quote test",
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
        version = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="quote-test-issue",
        )
        return version.invitations.get()


class SealedQuoteRevisionTests(QuoteFixtureMixin, TestCase):
    def test_submitted_revision_is_immutable_and_superseded_by_later_revision(self):
        invitation = self._issued_invitation()
        first = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="a" * 64,
            source_channel="internal_email",
            source_reference="MAIL-001",
            idempotency_key="capture-001",
        )
        submit_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=first,
            idempotency_key="submit-001",
        )
        second = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="b" * 64,
            source_channel="internal_email",
            source_reference="MAIL-002",
            idempotency_key="capture-002",
        )
        submit_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=second,
            idempotency_key="submit-002",
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, QuoteRevisionStatus.SUPERSEDED)
        self.assertEqual(second.status, QuoteRevisionStatus.SUBMITTED)
        self.assertEqual(second.supersedes_id, first.pk)
        second.source_reference = "MUTATED"
        with self.assertRaises(ValidationError):
            second.save()

    def test_duplicate_capture_is_idempotent_and_conflict_is_rejected(self):
        invitation = self._issued_invitation()
        captured = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="c" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-idempotent",
        )
        retry = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="c" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-idempotent",
        )
        self.assertEqual(captured.pk, retry.pk)
        with self.assertRaises(ValueError):
            capture_quote_revision(
                organization=self.organization,
                actor=self.member,
                invitation=invitation,
                integrity_fingerprint="d" * 64,
                source_channel="manual_capture",
                idempotency_key="capture-idempotent",
            )

    def test_metadata_scope_and_withdrawal_are_guarded(self):
        invitation = self._issued_invitation()
        revision = capture_quote_revision(
            organization=self.organization,
            actor=self.member,
            invitation=invitation,
            integrity_fingerprint="e" * 64,
            source_channel="manual_capture",
            idempotency_key="capture-withdraw",
        )
        withdrawn = withdraw_quote_revision(
            organization=self.organization,
            actor=self.member,
            revision=revision,
            idempotency_key="withdraw-001",
        )
        self.assertEqual(withdrawn.status, QuoteRevisionStatus.WITHDRAWN)
        self.assertEqual(
            get_organization_quote_revisions(
                user=self.owner, organization=self.organization
            ).count(),
            1,
        )
        with self.assertRaises(PermissionDenied):
            get_organization_quote_revisions(
                user=self.outsider, organization=self.organization
            )
        field_names = {field.name for field in QuoteRevision._meta.fields}
        self.assertFalse(
            {
                "price",
                "terms",
                "attachment",
                "qualification",
                "content",
                "withdrawal_reason",
            }
            & field_names
        )
        transition_fields = {
            field.name for field in QuoteRevisionTransition._meta.fields
        }
        self.assertNotIn("reason", transition_fields)
        with self.assertRaises(ValueError):
            capture_quote_revision(
                organization=self.organization,
                actor=self.member,
                invitation=invitation,
                integrity_fingerprint="g" * 64,
                source_channel="manual_capture",
                source_reference="commercial terms are prohibited",
                idempotency_key="capture-unsafe-reference",
            )


class SealedQuoteConcurrencyTests(QuoteFixtureMixin, TransactionTestCase):
    def test_concurrent_identical_capture_creates_one_revision(self):
        invitation = self._issued_invitation()
        barrier = Barrier(2)

        def capture_once() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                revision = capture_quote_revision(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.member.pk),
                    invitation=RequestForQuotationInvitation.objects.get(
                        pk=invitation.pk
                    ),
                    integrity_fingerprint="f" * 64,
                    source_channel="manual_capture",
                    idempotency_key="capture-concurrent",
                )
                return str(revision.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            revision_ids = list(pool.map(lambda _: capture_once(), range(2)))

        self.assertEqual(revision_ids[0], revision_ids[1])
        self.assertEqual(QuoteRevision.objects.count(), 1)
