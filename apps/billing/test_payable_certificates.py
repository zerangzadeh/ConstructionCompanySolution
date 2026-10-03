from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounting.posting_registry import get_posting_contract
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.models import (
    PayableCertificate,
    PayableCertificateCorrectionKind,
    PayableCertificateStatus,
    PayableMeasurement,
)
from apps.billing.payable_handoffs import (
    PAYABLE_CERTIFICATE_POSTING_EVENT_KIND,
    PAYABLE_CERTIFICATE_SOURCE_KIND,
    resolve_payable_certificate_obligation_source,
)
from apps.billing.payable_services import (
    add_payable_back_charge,
    approve_payable_certificate,
    create_payable_certificate,
    create_payable_certificate_correction,
    create_payable_measurement,
    decide_payable_measurement,
    get_payable_certificates,
    return_payable_certificate,
    submit_payable_certificate,
    submit_payable_measurement,
)
from apps.contracts.models import ContractDirection, ContractStatus, ContractType
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import set_active_organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.projects.services import create_project
from apps.subledgers.models import ObligationDirection
from apps.subledgers.services import recognize_obligation
from apps.workflows.models import WorkflowInstanceStatus, WorkItemStatus


class PayableCertificateTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="pay-cert-owner")
        self.manager = User.objects.create_user(username="pay-cert-manager")
        self.member = User.objects.create_user(username="pay-cert-member")
        self.organization = Organization.objects.create(
            name="Pay Cert", slug="pay-cert"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.manager_membership = self.organization.memberships.create(
            user=self.manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="PAY-P",
            name="Payable certification project",
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Subcontractor",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="SUB-001",
            title="Earth works",
            counterparty_name="Subcontractor",
            party=self.party,
            direction=ContractDirection.PAYABLE,
            contract_type=ContractType.SUBCONTRACT,
            contract_value=Decimal("1000.00"),
        )
        self.item = add_contract_item(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            description="Excavation",
            quantity=Decimal("10.0000"),
            unit_price=Decimal("100.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status=ContractStatus.ACTIVE,
        )
        self.contract.refresh_from_db()
        self.term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 1, 1),
            payment_due_days=10,
            retention_rate=Decimal(10),
            retention_cap=Decimal(60),
            advance_recovery_rate=Decimal(20),
            advance_recovery_cap=Decimal(80),
            reason="Payable commercial terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=self.term,
            reason="Independent term approval",
        )

    def _measurement(
        self,
        *,
        measured_on: date = date(2026, 1, 15),
        period: Decimal = Decimal("5.0000"),
        cumulative: Decimal = Decimal("5.0000"),
    ):
        measurement = create_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            contract_item=self.item,
            measured_on=measured_on,
            period_quantity=period,
            cumulative_quantity=cumulative,
            evidence_reference=f"SITE-{measured_on.isoformat()}",
        )
        submit_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            measurement=measurement,
        )
        return decide_payable_measurement(
            organization=self.organization,
            actor=self.manager,
            measurement=measurement,
            approved=True,
            reason="Verified against site evidence",
        )

    def _certificate(
        self,
        *,
        period_start: date = date(2026, 1, 1),
        period_end: date = date(2026, 1, 31),
        cutoff: date = date(2026, 1, 31),
    ):
        return create_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            period_start=period_start,
            period_end=period_end,
            measurement_cutoff=cutoff,
        )

    def _approve(self, certificate):
        instance = submit_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
        )
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        certificate = approve_payable_certificate(
            organization=self.organization,
            actor=self.manager,
            certificate=certificate,
            reason="Independent commercial certification",
        )
        return certificate

    def test_measurement_calculation_caps_back_charge_and_stable_line(self) -> None:
        self._measurement()
        certificate = self._certificate()
        add_payable_back_charge(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
            amount=Decimal("20.00"),
            description="Rectification by main contractor",
            evidence="NCR-17",
        )
        certificate.refresh_from_db()
        self.assertEqual(certificate.gross_amount, Decimal("500.00"))
        self.assertEqual(certificate.adjustment_amount, Decimal("-150.00"))
        self.assertEqual(certificate.net_amount, Decimal("350.00"))
        line = certificate.items.get()
        self.assertEqual(line.stable_line_id, self.item.pk)
        self.assertEqual(line.measurement.evidence_reference, "SITE-2026-01-15")
        self.assertEqual(certificate.adjustments.count(), 3)

    def test_cumulative_second_certificate_consumes_recovery_caps(self) -> None:
        self._measurement()
        first = self._approve(self._certificate())
        self.assertEqual(first.net_amount, Decimal("370.00"))
        self._measurement(
            measured_on=date(2026, 2, 15),
            period=Decimal("5.0000"),
            cumulative=Decimal("10.0000"),
        )
        second = self._certificate(
            period_start=date(2026, 2, 1),
            period_end=date(2026, 2, 28),
            cutoff=date(2026, 2, 28),
        )
        self.assertEqual(second.gross_amount, Decimal("500.00"))
        self.assertEqual(second.adjustment_amount, Decimal("-10.00"))
        self.assertEqual(second.net_amount, Decimal("490.00"))
        self.assertEqual(
            second.items.get().previous_cumulative_quantity, Decimal("5.0000")
        )

    def test_workflow_candidacy_sod_immutability_and_audit(self) -> None:
        self._measurement()
        certificate = self._certificate()
        instance = submit_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
        )
        item = instance.work_items.get()
        self.assertTrue(
            item.candidates.filter(
                membership=self.manager_membership, is_active=True
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            approve_payable_certificate(
                organization=self.organization,
                actor=self.owner,
                certificate=certificate,
                reason="Self approval must fail",
            )
        certificate = approve_payable_certificate(
            organization=self.organization,
            actor=self.manager,
            certificate=certificate,
            reason="Independent approval",
        )
        item.refresh_from_db()
        self.assertEqual(certificate.status, PayableCertificateStatus.APPROVED)
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(certificate.pk),
                action=AuditAction.PAYABLE_CERTIFICATE_APPROVED,
            ).exists()
        )
        certificate.net_amount = Decimal("1.00")
        with self.assertRaises(ValidationError):
            certificate.save()

    def test_audit_failure_rolls_back_workflow_and_domain_decision(self) -> None:
        self._measurement()
        certificate = self._certificate()
        instance = submit_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
        )
        with (
            patch(
                "apps.billing.payable_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            approve_payable_certificate(
                organization=self.organization,
                actor=self.manager,
                certificate=certificate,
                reason="Should roll back",
            )
        certificate.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(certificate.status, PayableCertificateStatus.SUBMITTED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)

    def test_linked_replacement_and_cancellation_preserve_history(self) -> None:
        self._measurement()
        original = self._approve(self._certificate())
        replacement = create_payable_certificate_correction(
            organization=self.organization,
            actor=self.owner,
            certificate=original,
            correction_kind=PayableCertificateCorrectionKind.REPLACEMENT,
            reason="Correct commercial evidence",
        )
        replacement = self._approve(replacement)
        original.refresh_from_db()
        self.assertEqual(original.status, PayableCertificateStatus.SUPERSEDED)
        self.assertEqual(replacement.status, PayableCertificateStatus.APPROVED)
        cancellation = create_payable_certificate_correction(
            organization=self.organization,
            actor=self.owner,
            certificate=replacement,
            correction_kind=PayableCertificateCorrectionKind.CANCELLATION,
            reason="Cancel with linked evidence",
        )
        self.assertEqual(cancellation.net_amount, Decimal(0))
        cancellation = self._approve(cancellation)
        replacement.refresh_from_db()
        self.assertEqual(replacement.status, PayableCertificateStatus.CANCELLED)
        self.assertEqual(cancellation.status, PayableCertificateStatus.APPROVED)

    def test_return_creates_linked_draft_revision(self) -> None:
        self._measurement()
        certificate = self._certificate()
        submit_payable_certificate(
            organization=self.organization,
            actor=self.owner,
            certificate=certificate,
        )
        returned = return_payable_certificate(
            organization=self.organization,
            actor=self.manager,
            certificate=certificate,
            reason="Revise measurement evidence",
        )
        revision = returned.returned_revision
        self.assertEqual(returned.status, PayableCertificateStatus.RETURNED)
        self.assertEqual(revision.status, PayableCertificateStatus.DRAFT)
        self.assertEqual(revision.revision_number, 2)
        self.assertEqual(revision.certificate_number, returned.certificate_number)
        self.assertEqual(revision.net_amount, returned.net_amount)

    def test_explicit_ap_and_non_operational_posting_handoffs(self) -> None:
        self._measurement()
        certificate = self._approve(self._certificate())
        source = resolve_payable_certificate_obligation_source(
            self.organization, certificate.pk, certificate.revision_number, ""
        )
        self.assertEqual(source.direction, ObligationDirection.PAYABLE)
        self.assertEqual(source.amount, certificate.net_amount)
        posting = get_posting_contract(
            source_kind=PAYABLE_CERTIFICATE_SOURCE_KIND,
            event_kind=PAYABLE_CERTIFICATE_POSTING_EVENT_KIND,
        )
        self.assertFalse(posting.operational_producer)
        recognize_obligation(
            organization=self.organization,
            actor=self.owner,
            source_kind=PAYABLE_CERTIFICATE_SOURCE_KIND,
            source_uuid=certificate.pk,
            source_version=certificate.revision_number,
            idempotency_key=f"PAY-CERT-{certificate.pk}",
        )
        with self.assertRaises(ValidationError):
            create_payable_certificate_correction(
                organization=self.organization,
                actor=self.owner,
                certificate=certificate,
                correction_kind=PayableCertificateCorrectionKind.CANCELLATION,
                reason="Blocked after AP recognition",
            )

    def test_permission_tenant_isolation_and_rtl_ui(self) -> None:
        with self.assertRaises(PermissionDenied):
            create_payable_measurement(
                organization=self.organization,
                actor=self.member,
                contract_item=self.item,
                measured_on=date(2026, 1, 15),
                period_quantity=Decimal("1.0000"),
                cumulative_quantity=Decimal("1.0000"),
                evidence_reference="DENIED",
            )
        self._measurement()
        certificate = self._certificate()
        other = Organization.objects.create(name="Other", slug="pay-cert-other")
        other.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.assertFalse(
            get_payable_certificates(actor=self.owner, organization=other)
            .filter(pk=certificate.pk)
            .exists()
        )
        self.client.force_login(self.owner)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()
        response = self.client.get(
            reverse("billing:payable_certificate_detail", args=[certificate.pk])
        )
        self.assertContains(response, "گواهی پرداخت پیمان جزء")
        self.assertContains(response, str(self.item.pk))

    def test_operational_ui_creates_measurement_and_certificate(self) -> None:
        def select_org(user: User) -> None:
            self.client.force_login(user)
            session = self.client.session
            set_active_organization(session, self.organization)
            session.save()

        select_org(self.owner)
        response = self.client.post(
            reverse("billing:payable_measurement_create"),
            {
                "contract_item": str(self.item.pk),
                "measured_on": "2026-01-15",
                "period_quantity": "5.0000",
                "cumulative_quantity": "5.0000",
                "evidence_reference": "UI-SITE-1",
            },
        )
        measurement = PayableMeasurement.objects.get(evidence_reference="UI-SITE-1")
        self.assertRedirects(
            response,
            reverse("billing:payable_measurement_detail", args=[measurement.pk]),
        )
        self.client.post(
            reverse("billing:payable_measurement_submit", args=[measurement.pk])
        )
        select_org(self.manager)
        self.client.post(
            reverse("billing:payable_measurement_verify", args=[measurement.pk]),
            {"reason": "UI independent verification"},
        )
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, "verified")
        select_org(self.owner)
        response = self.client.post(
            reverse("billing:payable_certificate_create"),
            {
                "contract": str(self.contract.pk),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "measurement_cutoff": "2026-01-31",
            },
        )
        certificate = PayableCertificate.objects.get(contract=self.contract)
        self.assertRedirects(
            response,
            reverse("billing:payable_certificate_detail", args=[certificate.pk]),
        )
        self.assertEqual(certificate.net_amount, Decimal("370.00"))

    def test_recalculation_rejects_contract_ceiling_breach(self) -> None:
        self.contract.contract_value = Decimal("400.00")
        type(self.contract).objects.filter(pk=self.contract.pk).update(
            contract_value=Decimal("400.00")
        )
        self._measurement()
        with self.assertRaises(ValidationError):
            self._certificate()


class PayableCertificateConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="pay-concurrency-owner")
        self.manager = User.objects.create_user(username="pay-concurrency-manager")
        self.organization = Organization.objects.create(
            name="Pay Concurrency", slug="pay-concurrency"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.manager,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="PAY-CON",
            name="Concurrency",
        )
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Concurrent subcontractor",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=project,
            actor=self.owner,
            contract_number="SUB-CON",
            title="Concurrency subcontract",
            counterparty_name="Concurrent subcontractor",
            party=party,
            direction=ContractDirection.PAYABLE,
            contract_type=ContractType.SUBCONTRACT,
            contract_value=Decimal("100.00"),
        )
        item = add_contract_item(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            description="One line",
            quantity=Decimal("1.0000"),
            unit_price=Decimal("100.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status=ContractStatus.ACTIVE,
        )
        self.contract.refresh_from_db()
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 1, 1),
            reason="Concurrency terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent approval",
        )
        measurement = create_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            contract_item=item,
            measured_on=date(2026, 1, 15),
            period_quantity=Decimal("1.0000"),
            cumulative_quantity=Decimal("1.0000"),
            evidence_reference="CONCURRENT",
        )
        submit_payable_measurement(
            organization=self.organization,
            actor=self.owner,
            measurement=measurement,
        )
        decide_payable_measurement(
            organization=self.organization,
            actor=self.manager,
            measurement=measurement,
            approved=True,
            reason="Verified",
        )

    def test_concurrent_duplicate_period_creates_only_one_certificate(self) -> None:
        barrier = Barrier(2)

        def create_one() -> str:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                certificate = create_payable_certificate(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    contract=self.contract,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 1, 31),
                    measurement_cutoff=date(2026, 1, 31),
                )
                return str(certificate.pk)
            except ValidationError:
                return "blocked"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create_one(), range(2)))
        self.assertEqual(results.count("blocked"), 1)
        self.assertEqual(
            self.organization.payable_certificates.filter(revision_number=1).count(),
            1,
        )
