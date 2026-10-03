from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.models import PayableCertificate, ProgressClaim
from apps.contracts.commercial_review import get_commercial_review
from apps.contracts.contractual_services import (
    add_contractual_evidence,
    create_contractual_record,
    create_contractual_revision,
    decide_contractual_record,
    get_contractual_records,
    submit_contractual_record,
    withdraw_contractual_record,
)
from apps.contracts.models import (
    ContractAmendment,
    ContractStatus,
    ContractualRecordStatus,
    ContractualRevisionAction,
)
from apps.contracts.services import create_contract, transition_contract_status
from apps.documents.models import DocumentVersion
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.projects.models import (
    BudgetVersion,
    ProjectChangeProposal,
    ProjectScheduleRevision,
)
from apps.projects.services import create_project, propose_project_change
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement
from apps.workflows.models import WorkflowInstanceStatus


class ContractualRecordTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p6-contractual-owner")
        self.approver = User.objects.create_user(username="p6-contractual-approver")
        self.organization = Organization.objects.create(
            name="P6 contractual", slug="p6-contractual"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.organization.memberships.create(
            user=self.approver,
            role=MembershipRole.COMPANY_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P6-CR",
            name="Contractual controls",
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Contract party",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="CR-001",
            title="Controlled contract",
            counterparty_name="Contract party",
            party=self.party,
            contract_value=Decimal("1000.00"),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status=ContractStatus.ACTIVE,
        )
        self.contract.refresh_from_db()

    def make_record(self, *, key="record-1", kind="claim"):
        return create_contractual_record(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            kind=kind,
            record_number="CCR-001",
            title="Evidence-backed contractual matter",
            description="No automatic downstream effect.",
            requested_amount=Decimal("125.5000"),
            requested_eot_days=7,
            valuation_assumptions="Manually asserted valuation.",
            schedule_impact_assumptions="Referenced only.",
            idempotency_key=key,
        )

    def test_governed_approval_records_explicit_facts_and_no_source_effects(
        self,
    ) -> None:
        record = self.make_record()
        contract_value = self.contract.contract_value
        schedule_count = ProjectScheduleRevision.objects.count()
        claim_count = ProgressClaim.objects.count()
        payable_count = PayableCertificate.objects.count()

        first = submit_contractual_record(
            organization=self.organization, actor=self.owner, record=record
        )
        replay = submit_contractual_record(
            organization=self.organization, actor=self.owner, record=record
        )
        self.assertEqual(first.pk, replay.pk)
        decided = decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=record,
            approved=True,
            reason="Explicit contractual decision",
            entitlement_approved=True,
            approved_amount=Decimal("100.0000"),
            approved_eot_days=5,
            delay_responsibility="Employer-responsibility fact approved by reviewer.",
        )

        self.assertEqual(decided.status, ContractualRecordStatus.APPROVED)
        self.assertTrue(decided.entitlement_approved)
        self.assertEqual(decided.approved_amount, Decimal("100.0000"))
        self.assertEqual(decided.approved_eot_days, 5)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.contract_value, contract_value)
        self.assertEqual(ProjectScheduleRevision.objects.count(), schedule_count)
        self.assertEqual(ProgressClaim.objects.count(), claim_count)
        self.assertEqual(PayableCertificate.objects.count(), payable_count)
        self.assertEqual(decided.submission_snapshot["effects"]["accounting"], "none")

    def test_read_only_commercial_review_orders_evidence_and_marks_advisory_gap(
        self,
    ) -> None:
        record = self.make_record()
        before = (
            self.contract.contract_value,
            ContractAmendment.objects.count(),
            ProgressClaim.objects.count(),
            PayableCertificate.objects.count(),
            ProjectChangeProposal.objects.count(),
            ProjectScheduleRevision.objects.count(),
            DocumentVersion.objects.count(),
            BudgetVersion.objects.count(),
            Obligation.objects.count(),
            JournalEntry.objects.count(),
            TreasuryMovement.objects.count(),
        )

        review = get_commercial_review(
            organization=self.organization, actor=self.owner, contract_id=self.contract.pk
        )

        self.assertEqual(review.contract.pk, self.contract.pk)
        self.assertEqual(len(review.timeline), 1)
        self.assertEqual(review.comparison_rows[0].reference, record.record_number)
        self.assertTrue(any(item.category == "شاهد" for item in review.exceptions))
        self.contract.refresh_from_db()
        self.assertEqual(
            (
                self.contract.contract_value,
                ContractAmendment.objects.count(),
                ProgressClaim.objects.count(),
                PayableCertificate.objects.count(),
                ProjectChangeProposal.objects.count(),
                ProjectScheduleRevision.objects.count(),
                DocumentVersion.objects.count(),
                BudgetVersion.objects.count(),
                Obligation.objects.count(),
                JournalEntry.objects.count(),
                TreasuryMovement.objects.count(),
            ),
            before,
        )

    def test_commercial_review_includes_permitted_billing_references_and_permissions(self) -> None:
        self.make_record()
        claim = SimpleNamespace(
            pk=uuid4(), approved_at=None, period_end=date(2026, 1, 10),
            claim_number=3, revision_number=2, status="approved",
            gross_amount=Decimal("150.0000"), net_amount=Decimal("125.0000"),
            currency_code="IRR",
        )
        certificate = SimpleNamespace(
            pk=uuid4(), approved_at=None, period_end=date(2026, 1, 20),
            certificate_number=4, revision_number=1, status="approved",
            gross_amount=Decimal("90.0000"), net_amount=Decimal("80.0000"),
            currency_code="IRR",
        )
        claim_qs = MagicMock()
        claim_qs.order_by.return_value = [claim]
        certificate_qs = MagicMock()
        certificate_qs.order_by.return_value = [certificate]
        with (
            patch("apps.contracts.commercial_review._can_view", return_value=True),
            patch.object(ProgressClaim.objects, "filter", return_value=claim_qs),
            patch.object(PayableCertificate.objects, "filter", return_value=certificate_qs),
        ):
            review = get_commercial_review(
                organization=self.organization,
                actor=self.owner,
                contract_id=self.contract.pk,
            )
        self.assertEqual(review.timeline[0].title, "صورت‌وضعیت 3 / نسخه 2")
        self.assertEqual(review.comparison_rows[-2].approved_amount, Decimal("125.0000"))
        self.assertEqual(review.comparison_rows[-1].approved_amount, Decimal("80.0000"))

        with patch("apps.contracts.commercial_review._can_view", return_value=False):
            restricted = get_commercial_review(
                organization=self.organization,
                actor=self.owner,
                contract_id=self.contract.pk,
            )
        self.assertEqual(
            restricted.unavailable_sources,
            ("صورت‌وضعیت‌های دریافتنی", "گواهی‌های پرداخت پیمان جزء"),
        )

    def test_commercial_review_fails_closed_for_cross_tenant_contract(self) -> None:
        other = Organization.objects.create(name="Other review", slug="other-review")
        with self.assertRaises(PermissionDenied):
            get_commercial_review(
                organization=other, actor=self.owner, contract_id=self.contract.pk
            )

    def test_workflow_sod_and_returned_revision_lineage(self) -> None:
        record = self.make_record()
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=record
        )
        with self.assertRaises(PermissionDenied):
            decide_contractual_record(
                organization=self.organization,
                actor=self.owner,
                record=record,
                approved=True,
                reason="Self approval",
                entitlement_approved=True,
            )
        returned = decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=record,
            approved=False,
            reason="Revise the evidence",
        )
        revised = create_contractual_revision(
            organization=self.organization,
            actor=self.owner,
            predecessor=returned,
            revision_action=ContractualRevisionAction.CORRECTION,
            reason="Corrected evidence",
            description="Corrected without rewriting returned history.",
            idempotency_key="record-1-r2",
        )
        returned.refresh_from_db()
        self.assertEqual(returned.status, ContractualRecordStatus.RETURNED)
        self.assertEqual(revised.supersedes, returned)
        self.assertEqual(revised.version, 2)

    def test_submitted_withdrawal_closes_workflow_atomically(self) -> None:
        record = self.make_record()
        instance = submit_contractual_record(
            organization=self.organization, actor=self.owner, record=record
        )
        withdrawn = withdraw_contractual_record(
            organization=self.organization,
            actor=self.owner,
            record=record,
            reason="Contractual notice withdrawn",
        )
        instance.refresh_from_db()
        self.assertEqual(withdrawn.status, ContractualRecordStatus.WITHDRAWN)
        self.assertEqual(instance.status, WorkflowInstanceStatus.CANCELLED)

    def test_approved_correction_and_cancellation_preserve_final_history(self) -> None:
        original = self.make_record()
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=original
        )
        decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=original,
            approved=True,
            reason="Approve original",
            entitlement_approved=True,
        )
        cancellation = create_contractual_revision(
            organization=self.organization,
            actor=self.owner,
            predecessor=original,
            revision_action=ContractualRevisionAction.CANCELLATION,
            reason="Controlled cancellation",
            idempotency_key="record-1-cancel",
        )
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=cancellation
        )
        decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=cancellation,
            approved=True,
            reason="Approve cancellation evidence",
            entitlement_approved=False,
            approved_amount=Decimal(0),
            approved_eot_days=0,
        )
        original.refresh_from_db()
        self.assertEqual(original.status, ContractualRecordStatus.CANCELLED)
        self.assertEqual(original.approval_reason, "Approve original")
        with self.assertRaises(ValidationError):
            original.title = "Silent rewrite"
            original.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(original).objects.filter(pk=original.pk).update(
                title="Bulk silent rewrite"
            )

    def test_withdrawal_idempotency_tenant_and_permission_isolation(self) -> None:
        record = self.make_record()
        replay = self.make_record()
        self.assertEqual(replay.pk, record.pk)
        withdrawn = withdraw_contractual_record(
            organization=self.organization,
            actor=self.owner,
            record=record,
            reason="No longer pursued",
        )
        self.assertEqual(withdrawn.status, ContractualRecordStatus.WITHDRAWN)
        other_user = User.objects.create_user(username="p6-other")
        other = Organization.objects.create(name="Other", slug="p6-other")
        other.memberships.create(
            user=other_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            get_contractual_records(actor=other_user, organization=self.organization)
        member = User.objects.create_user(username="p6-read-only-member")
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            create_contractual_record(
                organization=self.organization,
                actor=member,
                contract=self.contract,
                kind="claim",
                record_number="DENIED-001",
                title="Denied",
                description="No prepare permission.",
                idempotency_key="denied-create",
            )
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.CONTRACTUAL_RECORD_WITHDRAWN,
                entity_id=str(record.pk),
            ).exists()
        )

    def test_project_control_evidence_is_linked_without_mutating_source(self) -> None:
        proposal = propose_project_change(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            occurrence_id="P6-CHANGE-EVIDENCE",
            title="Observed project change",
            reason="Observation only",
            evidence_reference="FIELD-001",
            schedule_impact_description="Possible impact; not an EOT decision.",
        )
        record = self.make_record(kind="variation")
        link = add_contractual_evidence(
            organization=self.organization,
            actor=self.owner,
            record=record,
            label="پیشنهاد تغییر کنترل پروژه",
            project_change_proposal=proposal,
        )
        proposal.refresh_from_db()
        self.assertEqual(link.project_change_proposal, proposal)
        self.assertEqual(proposal.contractual_impact_status, "unassessed")
        self.assertEqual(proposal.financial_effect_status, "observation_only")
        review = get_commercial_review(
            organization=self.organization,
            actor=self.owner,
            contract_id=self.contract.pk,
        )
        self.assertEqual(review.evidence[0].label, "پیشنهاد تغییر کنترل پروژه")
        self.assertEqual(review.evidence[0].source_type, "project_change_proposal")
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(link).objects.filter(pk=link.pk).update(label="Silent relabel")

        other_project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P6-OTHER",
            name="Other scoped project",
        )
        other_proposal = propose_project_change(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            occurrence_id="P6-OTHER-EVIDENCE",
            title="Wrong project evidence",
            reason="Scope test",
            evidence_reference="FIELD-OTHER",
            schedule_impact_description="No conclusion.",
        )
        with self.assertRaises(ValidationError):
            add_contractual_evidence(
                organization=self.organization,
                actor=self.owner,
                record=record,
                label="Wrong project",
                project_change_proposal=other_proposal,
            )

    def test_rtl_operational_views_are_tenant_scoped(self) -> None:
        record = self.make_record()
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("contracts:contractual_detail", args=[record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "هیچ تغییر خودکاری")
        review_response = self.client.get(
            reverse("contracts:commercial_review", args=[self.contract.pk])
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'dir="rtl"')
        self.assertContains(review_response, "خط زمانی و مقایسه تجاری قرارداد")

    def test_audit_failure_rolls_back_approval(self) -> None:
        record = self.make_record()
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=record
        )
        from unittest.mock import patch

        with (
            patch(
                "apps.contracts.contractual_services.record_audit_event",
                side_effect=RuntimeError("audit unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            decide_contractual_record(
                organization=self.organization,
                actor=self.approver,
                record=record,
                approved=True,
                reason="Would approve",
                entitlement_approved=True,
            )
        record.refresh_from_db()
        self.assertEqual(record.status, ContractualRecordStatus.SUBMITTED)


class ContractualRecordConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="p6-concurrent-owner")
        self.organization = Organization.objects.create(
            name="P6 concurrent", slug="p6-concurrent"
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P6-CON",
            name="Concurrent contractual record",
        )
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Concurrent party",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="CONCURRENT-001",
            title="Concurrent contract",
            counterparty_name="Concurrent party",
            party=party,
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status=ContractStatus.ACTIVE,
        )

    def test_concurrent_same_idempotency_key_creates_one_record(self) -> None:
        barrier = Barrier(2)

        def create_once():
            close_old_connections()
            barrier.wait()
            try:
                return create_contractual_record(
                    organization=Organization.objects.get(pk=self.organization.pk),
                    actor=User.objects.get(pk=self.owner.pk),
                    contract=self.contract,
                    kind="site_instruction",
                    record_number="SI-001",
                    title="Concurrent instruction",
                    description="One retained result.",
                    idempotency_key="concurrent-si-001",
                ).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create_once(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(
            self.organization.contractual_records.filter(
                idempotency_key="concurrent-si-001"
            ).count(),
            1,
        )
