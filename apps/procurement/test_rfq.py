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
from apps.parties.models import BusinessParty
from apps.procurement.models import (
    RequestForQuotation,
    RequestForQuotationVersion,
)
from apps.procurement.rfq_services import (
    add_rfq_line,
    create_rfq,
    get_organization_rfqs,
    issue_rfq,
    issue_rfq_addendum,
    submit_rfq_for_issue,
)
from apps.procurement.tests import ProcurementFixtureMixin


class RequestForQuotationServiceTests(ProcurementFixtureMixin, TestCase):
    def _draft(self):
        request, item = self.create_approved_request()
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=request,
            rfq_number="rfq-001",
            title="Cement RFQ",
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
        return rfq

    def test_issue_is_idempotent_and_snapshots_are_immutable(self):
        rfq = self._draft()
        submit_rfq_for_issue(organization=self.organization, actor=self.member, rfq=rfq)
        version = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="issue-001",
        )
        retry = issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="issue-001",
        )
        self.assertEqual(version.pk, retry.pk)
        self.assertEqual(version.lines.count(), 1)
        self.assertEqual(version.invitations.count(), 1)
        version.terms = "changed"
        with self.assertRaises(ValidationError):
            version.save()

    def test_addendum_cannot_move_opening_boundary_earlier(self):
        rfq = self._draft()
        submit_rfq_for_issue(organization=self.organization, actor=self.member, rfq=rfq)
        issue_rfq(
            organization=self.organization,
            actor=self.owner,
            rfq=rfq,
            suppliers=[self.supplier],
            idempotency_key="issue-001",
        )
        rfq.refresh_from_db()
        with self.assertRaises(ValueError):
            issue_rfq_addendum(
                organization=self.organization,
                actor=self.owner,
                rfq=rfq,
                terms="updated",
                closing_at=rfq.closing_at - timedelta(minutes=1),
                earliest_opening_at=rfq.earliest_opening_at,
                idempotency_key="addendum-001",
            )

    def test_read_scope_and_cross_tenant_project_are_denied(self):
        rfq = self._draft()
        self.assertEqual(
            get_organization_rfqs(
                user=self.member, organization=self.organization
            ).count(),
            1,
        )
        with self.assertRaises(PermissionDenied):
            get_organization_rfqs(user=self.outsider, organization=self.organization)
        with self.assertRaises(PermissionDenied):
            create_rfq(
                organization=self.organization,
                actor=self.member,
                project=self.other_project,
                purchase_request=rfq.purchase_request,
                rfq_number="RFQ-CROSS-TENANT",
                title="Cross tenant",
                closing_at=timezone.now() + timedelta(days=1),
                earliest_opening_at=timezone.now() + timedelta(days=1),
            )


class RequestForQuotationConcurrencyTests(ProcurementFixtureMixin, TransactionTestCase):
    def test_concurrent_identical_issue_creates_one_version(self):
        request, item = self.create_approved_request()
        now = timezone.now()
        rfq = create_rfq(
            organization=self.organization,
            actor=self.member,
            project=self.project,
            purchase_request=request,
            rfq_number="rfq-concurrent",
            title="Concurrent RFQ",
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
        barrier = Barrier(2)

        def issue_once() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                version = issue_rfq(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    rfq=RequestForQuotation.objects.get(pk=rfq.pk),
                    suppliers=[BusinessParty.objects.get(pk=self.supplier.pk)],
                    idempotency_key="rfq-concurrent-issue",
                )
                return str(version.pk)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            version_ids = list(pool.map(lambda _: issue_once(), range(2)))

        self.assertEqual(version_ids[0], version_ids[1])
        self.assertEqual(RequestForQuotationVersion.objects.filter(rfq=rfq).count(), 1)
