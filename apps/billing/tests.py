from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.models import (
    ClaimSettlementAllocation,
    ProgressClaim,
    ProgressRecordStatus,
    ProjectBaselineStatus,
)
from apps.billing.services import (
    add_baseline_item,
    allocate_progress_claim_settlement,
    approve_progress_claim,
    approve_project_baseline,
    create_progress_claim,
    create_progress_claim_revision,
    create_progress_correction,
    create_progress_record,
    create_project_baseline,
    get_progress_claim_settlement_summary,
    recalculate_progress_claim,
    request_progress_verification,
    request_project_baseline_approval,
    return_progress_claim,
    reverse_progress_claim_settlement,
    submit_progress_claim,
    update_billing_policy,
    verify_progress_record,
)
from apps.contracts.models import (
    ContractAmendment,
    ContractAmendmentStatus,
    ContractDirection,
    ContractStatus,
)
from apps.contracts.services import create_contract
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.organizations.services import set_active_organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.payments.models import PaymentAllocationStatus, PaymentDirection
from apps.payments.services import (
    allocate_payment,
    create_payment,
    reverse_payment_allocation,
    void_payment,
)
from apps.projects.services import create_project
from apps.workflows.models import (
    WorkflowInstanceStatus,
    WorkItemCandidate,
    WorkItemStatus,
)
from apps.workforce.models import Employee, EmployeePositionAssignment, Position


class ProjectBaselineWorkflowTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="f61-owner")
        self.manager = User.objects.create_user(username="f61-manager")
        self.member = User.objects.create_user(username="f61-member")
        self.organization = Organization.objects.create(name="F61", slug="f61")
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
            code="F61-P",
            name="Baseline project",
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Client",
        )
        self.contract = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract_number="F61-C",
            title="Receivable contract",
            counterparty_name="Client",
            party=self.party,
            direction=ContractDirection.RECEIVABLE,
            status=ContractStatus.ACTIVE,
            contract_value=Decimal("100.00"),
        )
        ContractAmendment.objects.create(
            organization=self.organization,
            contract=self.contract,
            amendment_number=1,
            title="Approved addition",
            reason="Scope change",
            value_change=Decimal("20.00"),
            status=ContractAmendmentStatus.APPROVED,
            created_by=self.owner,
        )

    def _baseline(self, total: Decimal = Decimal("120.00")):
        baseline = create_project_baseline(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            effective_date=date(2026, 9, 19),
        )
        add_baseline_item(
            organization=self.organization,
            actor=self.owner,
            baseline=baseline,
            line_key="ITEM-01",
            description="Concrete work",
            unit="m3",
            planned_quantity=Decimal("1.0000"),
            unit_rate=total,
        )
        return baseline

    def test_approval_uses_shared_work_item_and_snapshots_exact_ceiling(self) -> None:
        baseline = self._baseline()

        instance = request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        item = instance.work_items.get()
        approved = approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=baseline,
            reason="Commercial review complete",
        )

        self.assertEqual(approved.status, ProjectBaselineStatus.APPROVED)
        self.assertEqual(approved.contract_value_snapshot, Decimal("100.00"))
        self.assertEqual(approved.approved_amendments_snapshot, Decimal("20.00"))
        self.assertEqual(approved.effective_ceiling, Decimal("120.00"))
        item.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.PROJECT_BASELINE_APPROVED,
                entity_id=str(approved.pk),
                organization=self.organization,
            ).exists()
        )

    def test_approval_rejects_total_that_is_not_effective_contract_ceiling(
        self,
    ) -> None:
        baseline = self._baseline(total=Decimal("119.99"))
        instance = request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        item = instance.work_items.get()

        with self.assertRaises(ValidationError):
            approve_project_baseline(
                organization=self.organization,
                actor=self.manager,
                baseline=baseline,
                reason="Commercial review complete",
            )

        baseline.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(baseline.status, ProjectBaselineStatus.DRAFT)
        self.assertEqual(item.status, WorkItemStatus.OPEN)

    def test_approved_baseline_is_superseded_by_new_approved_version(self) -> None:
        first = self._baseline()
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=first
        )
        approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=first,
            reason="First approval",
        )
        second = self._baseline()
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=second
        )
        approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=second,
            reason="Amendment baseline refresh",
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, ProjectBaselineStatus.SUPERSEDED)
        self.assertEqual(first.superseded_by_id, second.pk)
        self.assertEqual(second.status, ProjectBaselineStatus.APPROVED)

    def test_unqualified_member_cannot_approve_or_act_on_work_item(self) -> None:
        baseline = self._baseline()
        instance = request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )

        with self.assertRaises(PermissionDenied):
            approve_project_baseline(
                organization=self.organization,
                actor=self.member,
                baseline=baseline,
                reason="Not allowed",
            )

        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)

    def test_member_with_removed_candidacy_cannot_approve(self) -> None:
        baseline = self._baseline()
        instance = request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        candidate = WorkItemCandidate.objects.get(
            work_item=instance.work_items.get(), membership=self.manager_membership
        )
        WorkItemCandidate.objects.filter(pk=candidate.pk).update(is_active=False)

        with self.assertRaises(PermissionDenied):
            approve_project_baseline(
                organization=self.organization,
                actor=self.manager,
                baseline=baseline,
                reason="Candidate was removed",
            )

    def test_precision_and_binary_float_are_rejected(self) -> None:
        baseline = create_project_baseline(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            effective_date=date(2026, 9, 19),
        )

        with self.assertRaises(ValidationError):
            add_baseline_item(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                line_key="ITEM-01",
                description="Over-precision quantity",
                unit="m3",
                planned_quantity=Decimal("1.00001"),
                unit_rate=Decimal("1.00"),
            )
        with self.assertRaises(ValidationError):
            add_baseline_item(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                line_key="ITEM-02",
                description="Binary float",
                unit="m3",
                planned_quantity=1.0,
                unit_rate=Decimal("1.00"),
            )

    def test_cross_tenant_project_is_rejected_at_service_boundary(self) -> None:
        other_owner = User.objects.create_user(username="f61-other-owner")
        other_organization = Organization.objects.create(
            name="F61 Other", slug="f61-other"
        )
        other_organization.memberships.create(
            user=other_owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        other_project = create_project(
            organization=other_organization,
            actor=other_owner,
            code="F61-OTHER",
            name="Other project",
        )

        with self.assertRaises(PermissionDenied):
            create_project_baseline(
                organization=self.organization,
                actor=self.owner,
                project=other_project,
                contract=self.contract,
                effective_date=date(2026, 9, 19),
            )

    def test_domain_workflow_and_audit_rollback_together(self) -> None:
        baseline = self._baseline()
        instance = request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        item = instance.work_items.get()

        with (
            patch("apps.billing.services.record_audit_event", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            approve_project_baseline(
                organization=self.organization,
                actor=self.manager,
                baseline=baseline,
                reason="Must roll back",
            )

        baseline.refresh_from_db()
        item.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(baseline.status, ProjectBaselineStatus.DRAFT)
        self.assertEqual(item.status, WorkItemStatus.OPEN)
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)


class ProgressRecordWorkflowTests(ProjectBaselineWorkflowTests):
    def _approved_baseline(self):
        baseline = self._baseline()
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=baseline
        )
        return approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=baseline,
            reason="Baseline approved",
        )

    def _record(self, *, cumulative: str = "0.5000", period: str = "0.5000"):
        baseline = self._approved_baseline()
        return create_progress_record(
            organization=self.organization,
            actor=self.owner,
            baseline=baseline,
            baseline_item=baseline.items.get(),
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            measured_on=date(2026, 9, 19),
            source_type="site_report",
            source_reference="DR-001",
            period_quantity=Decimal(period),
            cumulative_quantity=Decimal(cumulative),
            evidence="signed site report",
        )

    def test_verification_uses_shared_work_item_and_pins_cumulative_ledger(
        self,
    ) -> None:
        record = self._record()
        instance = request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        verified = verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="Source checked",
        )
        self.assertEqual(verified.status, ProgressRecordStatus.VERIFIED)
        self.assertEqual(verified.previous_cumulative_quantity, Decimal("0.0000"))
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.COMPLETED)

    def test_duplicate_source_and_baseline_ceiling_are_rejected(self) -> None:
        record = self._record()
        baseline = record.baseline
        item = record.baseline_item
        with self.assertRaises(ValidationError):
            create_progress_record(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                baseline_item=item,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                measured_on=date(2026, 9, 20),
                source_type="site_report",
                source_reference="DR-001",
                period_quantity=Decimal("0.1000"),
                cumulative_quantity=Decimal("0.6000"),
            )
        with self.assertRaises(ValidationError):
            create_progress_record(
                organization=self.organization,
                actor=self.owner,
                baseline=baseline,
                baseline_item=item,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                measured_on=date(2026, 9, 20),
                source_type="site_report",
                source_reference="DR-002",
                period_quantity=Decimal("1.0001"),
                cumulative_quantity=Decimal("1.0001"),
            )

    def test_correction_is_linked_and_verified_records_are_immutable(self) -> None:
        record = self._record()
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        verified = verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="Verified",
        )
        with self.assertRaises(ValidationError):
            verified.evidence = "changed"
            verified.save()
        correction = create_progress_correction(
            organization=self.organization,
            actor=self.owner,
            record=verified,
            source_type="correction_sheet",
            source_reference="COR-001",
            period_quantity=Decimal("0.4000"),
            cumulative_quantity=Decimal("0.4000"),
            evidence="corrected quantity",
        )
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=correction
        )
        correction = verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=correction,
            reason="Correction checked",
        )
        self.assertEqual(correction.corrects_id, verified.pk)
        self.assertEqual(correction.previous_cumulative_quantity, Decimal("0.0000"))

    def test_cross_tenant_progress_and_unqualified_verifier_are_rejected(self) -> None:
        record = self._record()
        outsider = User.objects.create_user(username="f62-outsider")
        with self.assertRaises(PermissionDenied):
            request_progress_verification(
                organization=self.organization, actor=outsider, record=record
            )
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        with self.assertRaises(PermissionDenied):
            verify_progress_record(
                organization=self.organization,
                actor=self.member,
                record=record,
                reason="Not allowed",
            )

    def test_verification_work_item_and_domain_state_roll_back_with_audit(self) -> None:
        record = self._record()
        instance = request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        with (
            patch("apps.billing.services.record_audit_event", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            verify_progress_record(
                organization=self.organization,
                actor=self.manager,
                record=record,
                reason="Audit must roll back",
            )
        record.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(record.status, ProgressRecordStatus.SUBMITTED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)


class ProgressClaimCalculationTests(ProgressRecordWorkflowTests):
    def _verified_record(self):
        record = self._record()
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        return verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="Verified measurement",
        )

    def _claim(self, record=None):
        record = record or self._verified_record()
        return create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=record.baseline,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            measurement_cutoff=date(2026, 9, 30),
        )

    def test_claim_calculates_current_and_cumulative_from_verified_source(self) -> None:
        claim = self._claim()
        item = claim.items.get()
        self.assertEqual(item.previous_cumulative_quantity, Decimal("0.0000"))
        self.assertEqual(item.current_quantity, Decimal("0.5000"))
        self.assertEqual(item.new_cumulative_quantity, Decimal("0.5000"))
        self.assertEqual(item.current_amount, Decimal("60.0000"))
        self.assertEqual(claim.gross_amount, Decimal("60.0000"))
        self.assertEqual(claim.net_amount, Decimal("60.0000"))

    def test_policy_drives_rounding_and_adjustments(self) -> None:
        record = self._verified_record()
        update_billing_policy(
            organization=self.organization,
            actor=self.owner,
            money_decimal_places=2,
            tax_rate=Decimal(10),
            insurance_rate=Decimal(5),
            retention_rate=Decimal(10),
            retention_cap=Decimal(3),
            advance_recovery_rate=Decimal(10),
            advance_recovery_cap=Decimal(2),
        )
        claim = create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=record.baseline,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            measurement_cutoff=date(2026, 9, 30),
        )
        self.assertEqual(claim.adjustment_amount, Decimal("-2.0000"))
        self.assertEqual(claim.net_amount, Decimal("58.0000"))
        self.assertEqual(claim.adjustments.count(), 4)

    def test_claim_revision_reuses_sources_without_rewriting_history(self) -> None:
        claim = self._claim()
        revision = create_progress_claim_revision(
            organization=self.organization, actor=self.owner, claim=claim
        )
        self.assertEqual(revision.revision_number, 2)
        self.assertEqual(revision.items.get().sources.count(), 1)
        self.assertEqual(claim.items.get().sources.count(), 1)

    def test_overlapping_draft_period_and_negative_net_are_rejected(self) -> None:
        record = self._verified_record()
        update_billing_policy(
            organization=self.organization,
            actor=self.owner,
            retention_rate=Decimal(200),
            retention_cap=Decimal(999),
        )
        with self.assertRaises(ValidationError):
            create_progress_claim(
                organization=self.organization,
                actor=self.owner,
                baseline=record.baseline,
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                measurement_cutoff=date(2026, 9, 30),
            )
        update_billing_policy(
            organization=self.organization,
            actor=self.owner,
            retention_rate=Decimal(0),
            retention_cap=Decimal(0),
        )
        self._claim(record)
        with self.assertRaises(ValidationError):
            create_progress_claim(
                organization=self.organization,
                actor=self.owner,
                baseline=record.baseline,
                period_start=date(2026, 9, 15),
                period_end=date(2026, 10, 15),
                measurement_cutoff=date(2026, 9, 30),
            )


class ProgressClaimApprovalWorkflowTests(ProgressClaimCalculationTests):
    def _claim_for_approval(self):
        return self._claim()

    def _configure_reporting_line(self) -> None:
        manager_position = Position.objects.create(
            organization=self.organization,
            code="CLAIM-MANAGER",
            title="Claim manager",
        )
        preparer_position = Position.objects.create(
            organization=self.organization,
            code="CLAIM-PREPARER",
            title="Claim preparer",
            parent_position=manager_position,
        )
        manager_employee = Employee.objects.create(
            organization=self.organization,
            user=self.manager,
            employee_number="F64-MANAGER",
            first_name="Claim",
            last_name="Manager",
            position=manager_position,
        )
        owner_employee = Employee.objects.create(
            organization=self.organization,
            user=self.owner,
            employee_number="F64-PREPARER",
            first_name="Claim",
            last_name="Preparer",
            position=preparer_position,
        )
        EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=manager_employee,
            position=manager_position,
            start_date=date(2020, 1, 1),
            is_primary=True,
        )
        EmployeePositionAssignment.objects.create(
            organization=self.organization,
            employee=owner_employee,
            position=preparer_position,
            start_date=date(2020, 1, 1),
            is_primary=True,
        )

    def test_hierarchy_route_requires_permission_and_completes_shared_work_item(self):
        self._configure_reporting_line()
        claim = self._claim_for_approval()

        instance = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        item = instance.work_items.get()
        self.assertTrue(
            WorkItemCandidate.objects.filter(
                work_item=item, membership=self.manager_membership, is_active=True
            ).exists()
        )
        self.assertFalse(
            WorkItemCandidate.objects.filter(
                work_item=item, membership__user=self.owner, is_active=True
            ).exists()
        )

        approved = approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Hierarchy commercial review",
        )
        item.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(approved.status, "approved")
        self.assertEqual(item.status, WorkItemStatus.COMPLETED)
        self.assertEqual(instance.status, WorkflowInstanceStatus.COMPLETED)
        self.assertTrue(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(claim.pk),
                action=AuditAction.PROGRESS_CLAIM_APPROVED,
            ).exists()
        )

    def test_submitted_snapshot_is_immutable_and_return_creates_linked_draft_revision(
        self,
    ):
        self._configure_reporting_line()
        claim = self._claim_for_approval()
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        claim.refresh_from_db()
        snapshot = claim.submission_snapshot
        with self.assertRaises(ValidationError):
            recalculate_progress_claim(
                organization=self.organization, actor=self.owner, claim=claim
            )

        returned = return_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Attach the revised site evidence",
        )
        revision = returned.returned_revision
        self.assertEqual(returned.status, "returned")
        self.assertEqual(revision.status, "draft")
        self.assertEqual(revision.revision_number, claim.revision_number + 1)
        self.assertEqual(returned.submission_snapshot, snapshot)
        self.assertEqual(revision.items.count(), returned.items.count())
        with self.assertRaises(ValidationError):
            returned.net_amount = Decimal("1.0000")
            returned.save()

    def test_submitter_is_excluded_when_another_approver_exists_and_allowed_only_as_last_resort(
        self,
    ):
        claim = self._claim_for_approval()
        instance = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        item = instance.work_items.get()
        self.assertFalse(
            WorkItemCandidate.objects.filter(
                work_item=item, membership__user=self.owner, is_active=True
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            approve_progress_claim(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                reason="Self approval is separated",
            )

    def test_small_tenant_submitter_is_allowed_only_without_another_approver(self):
        fallback_claim = self._claim_for_approval()
        self.manager_membership.status = MembershipStatus.SUSPENDED
        self.manager_membership.save(update_fields=["status", "updated_at"])
        fallback_instance = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=fallback_claim
        )
        fallback_item = fallback_instance.work_items.get()
        self.assertTrue(
            WorkItemCandidate.objects.filter(
                work_item=fallback_item, membership__user=self.owner, is_active=True
            ).exists()
        )
        approved = approve_progress_claim(
            organization=self.organization,
            actor=self.owner,
            claim=fallback_claim,
            reason="Only eligible small-tenant approver",
        )
        self.assertEqual(approved.status, "approved")

    def test_submission_and_decision_retries_are_idempotent(self):
        self._configure_reporting_line()
        claim = self._claim_for_approval()
        first = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        second = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        self.assertEqual(first.pk, second.pk)
        approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="First decision",
        )
        retry = approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="First decision",
        )
        self.assertEqual(retry.status, "approved")
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(claim.pk),
                action=AuditAction.PROGRESS_CLAIM_APPROVED,
            ).count(),
            1,
        )

    def test_cross_tenant_and_audit_failure_roll_back_claim_and_work_item(self):
        self._configure_reporting_line()
        claim = self._claim_for_approval()
        instance = submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        outsider = User.objects.create_user(username="f64-outsider")
        other_organization = Organization.objects.create(
            name="F64 Other", slug="f64-other"
        )
        other_organization.memberships.create(
            user=outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            submit_progress_claim(
                organization=other_organization, actor=outsider, claim=claim
            )
        with self.assertRaises(PermissionDenied):
            approve_progress_claim(
                organization=self.organization,
                actor=outsider,
                claim=claim,
                reason="Cross tenant",
            )
        with (
            patch("apps.billing.services.record_audit_event", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            approve_progress_claim(
                organization=self.organization,
                actor=self.manager,
                claim=claim,
                reason="Rollback all states",
            )
        claim.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(claim.status, "submitted")
        self.assertEqual(instance.status, WorkflowInstanceStatus.ACTIVE)
        self.assertEqual(instance.work_items.get().status, WorkItemStatus.OPEN)


class ProgressClaimSettlementTests(ProgressClaimApprovalWorkflowTests):
    def _approved_claim(self) -> ProgressClaim:
        claim = self._claim_for_approval()
        submit_progress_claim(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
        )
        return approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Settlement approval",
        )

    def _receipt_allocation(self, *, amount: Decimal = Decimal("100.00")):
        payment = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number=f"F65-R-{int(amount)}",
            direction=PaymentDirection.RECEIPT,
            amount=amount,
            paid_on=date(2026, 9, 20),
            counterparty_name=self.party.display_name,
            party=self.party,
            contract=self.contract,
        )
        return payment, allocate_payment(
            payment=payment,
            contract=self.contract,
            actor=self.owner,
            amount=amount,
        )

    def test_partial_settlement_uses_existing_allocation_and_caps_claim_balance(self):
        claim = self._approved_claim()
        payment, payment_allocation = self._receipt_allocation()
        first = allocate_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
            payment_allocation=payment_allocation,
            amount=Decimal("20.00"),
            reason="First partial receipt",
        )
        second = allocate_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
            payment_allocation=payment_allocation,
            amount=Decimal("40.00"),
            reason="Final partial receipt",
        )

        summary = get_progress_claim_settlement_summary(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
        )
        self.assertEqual(summary.approved_net_amount, Decimal("60.0000"))
        self.assertEqual(summary.settled_amount, Decimal("60.00"))
        self.assertEqual(summary.outstanding_amount, Decimal("0.0000"))
        self.assertEqual(ClaimSettlementAllocation.objects.count(), 2)
        self.assertEqual(payment.amount, Decimal("100.00"))
        self.assertEqual(payment_allocation.amount, Decimal("100.00"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.CLAIM_SETTLEMENT_ALLOCATED,
                entity_id=str(first.pk),
            ).exists()
        )
        with self.assertRaises(ValidationError) as context:
            allocate_progress_claim_settlement(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                payment_allocation=payment_allocation,
                amount=Decimal("0.01"),
                reason="Over settlement",
            )
        self.assertIn(
            "مبلغ تسویه از مانده طلب صورت‌وضعیت بیشتر است.",
            context.exception.messages,
        )
        self.assertEqual(second.status, "active")

    def test_receipt_party_is_required_and_must_match_contract_party(self):
        claim = self._approved_claim()
        payment = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="F65-R-NO-PARTY",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("60.00"),
            paid_on=date(2026, 9, 20),
            counterparty_name=self.party.display_name,
            contract=self.contract,
        )
        payment_allocation = allocate_payment(
            payment=payment,
            contract=self.contract,
            actor=self.owner,
            amount=Decimal("60.00"),
        )
        with self.assertRaises(ValidationError) as context:
            allocate_progress_claim_settlement(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                payment_allocation=payment_allocation,
                amount=Decimal("20.00"),
                reason="Name-only match is insufficient",
            )
        self.assertIn(
            "طرف‌حساب دریافت و قرارداد باید با شناسه طرف تجاری یکسان و کامل باشد.",
            context.exception.messages,
        )

    def test_settlement_cannot_exceed_existing_payment_allocation(self):
        claim = self._approved_claim()
        _, payment_allocation = self._receipt_allocation(amount=Decimal("30.00"))
        with self.assertRaisesMessage(
            ValidationError,
            "مبلغ تسویه از مانده تخصیص پرداخت بیشتر است.",
        ):
            allocate_progress_claim_settlement(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                payment_allocation=payment_allocation,
                amount=Decimal("30.01"),
                reason="Over existing allocation",
            )

    def test_settlement_requires_receipt_and_matching_contract(self):
        claim = self._approved_claim()
        disbursement = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="F65-DISBURSEMENT",
            direction="disbursement",
            amount=Decimal("60.00"),
            paid_on=date(2026, 9, 20),
            counterparty_name=self.party.display_name,
            party=self.party,
            contract=self.contract,
        )
        disbursement_allocation = allocate_payment(
            payment=disbursement,
            contract=self.contract,
            actor=self.owner,
            amount=Decimal("60.00"),
        )
        with self.assertRaises(ValidationError) as context:
            allocate_progress_claim_settlement(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                payment_allocation=disbursement_allocation,
                amount=Decimal("20.00"),
                reason="Disbursement cannot settle a claim",
            )
        self.assertIn(
            "فقط دریافت قابل اتصال به صورت‌وضعیت است.",
            context.exception.messages,
        )

        other_contract = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract_number="F65-OTHER-CONTRACT",
            title="Other receivable contract",
            counterparty_name=self.party.display_name,
            party=self.party,
            direction=ContractDirection.RECEIVABLE,
            status=ContractStatus.ACTIVE,
            contract_value=Decimal("100.00"),
        )
        other_payment = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="F65-OTHER-RECEIPT",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("60.00"),
            paid_on=date(2026, 9, 20),
            counterparty_name=self.party.display_name,
            party=self.party,
            contract=other_contract,
        )
        other_allocation = allocate_payment(
            payment=other_payment,
            contract=other_contract,
            actor=self.owner,
            amount=Decimal("60.00"),
        )
        with self.assertRaises(ValidationError) as context:
            allocate_progress_claim_settlement(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                payment_allocation=other_allocation,
                amount=Decimal("20.00"),
                reason="Other contract cannot settle this claim",
            )
        self.assertIn(
            "دریافت و تخصیص آن باید با سازمان، پروژه و قرارداد صورت‌وضعیت یکسان باشد.",
            context.exception.messages,
        )

    def test_reverse_and_payment_void_reverse_settlements_atomically(self):
        claim = self._approved_claim()
        payment, payment_allocation = self._receipt_allocation()
        settlement = allocate_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
            payment_allocation=payment_allocation,
            amount=Decimal("20.00"),
            reason="Manual settlement",
        )
        reverse_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            settlement=settlement,
            reason="Correction",
        )
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, "reversed")
        self.assertEqual(
            get_progress_claim_settlement_summary(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
            ).outstanding_amount,
            Decimal("60.0000"),
        )

        active_settlement = allocate_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
            payment_allocation=payment_allocation,
            amount=Decimal("20.00"),
            reason="Settlement before payment void",
        )
        void_payment(payment=payment, actor=self.owner, reason="Bank correction")
        payment_allocation.refresh_from_db()
        active_settlement.refresh_from_db()
        self.assertEqual(payment_allocation.status, PaymentAllocationStatus.REVERSED)
        self.assertEqual(active_settlement.status, "reversed")
        self.assertTrue(payment_allocation.reversal_reason)
        self.assertTrue(active_settlement.reversal_reason)
        self.assertEqual(
            get_progress_claim_settlement_summary(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
            ).outstanding_amount,
            Decimal("60.0000"),
        )

    def test_payment_allocation_reversal_reverses_dependent_settlement(self):
        claim = self._approved_claim()
        _, payment_allocation = self._receipt_allocation()
        settlement = allocate_progress_claim_settlement(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
            payment_allocation=payment_allocation,
            amount=Decimal("20.00"),
            reason="Settlement before allocation reversal",
        )
        reverse_payment_allocation(
            allocation=payment_allocation,
            actor=self.owner,
            reason="Allocation correction",
        )
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, "reversed")
        self.assertEqual(
            get_progress_claim_settlement_summary(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
            ).outstanding_amount,
            Decimal("60.0000"),
        )

    def test_settlement_service_denies_cross_tenant_claim_and_allocation(self):
        claim = self._approved_claim()
        _, payment_allocation = self._receipt_allocation()
        outsider = User.objects.create_user(username="f65-outsider")
        other_organization = Organization.objects.create(
            name="F65 Other", slug="f65-other"
        )
        other_organization.memberships.create(
            user=outsider,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            allocate_progress_claim_settlement(
                organization=other_organization,
                actor=outsider,
                claim=claim,
                payment_allocation=payment_allocation,
                amount=Decimal("20.00"),
                reason="Cross tenant attempt",
            )
        self.assertFalse(ClaimSettlementAllocation.objects.exists())

    def test_claim_views_enforce_role_tenant_scope_and_csrf(self):
        claim = self._approved_claim()
        _, payment_allocation = self._receipt_allocation()
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)

        detail_url = reverse("billing:claim_detail", args=[claim.pk])
        response = self.client.get(reverse("billing:claim_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, claim.contract.contract_number)
        with CaptureQueriesContext(connection) as detail_queries:
            detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, 200)
        self.assertLessEqual(
            len(detail_queries),
            25,
            "Claim detail must keep a bounded query budget as settlements grow.",
        )

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        set_active_organization(csrf_client.session, self.organization)
        self.assertEqual(
            csrf_client.post(
                reverse("billing:claim_settlement_allocate", args=[claim.pk]),
                {
                    "payment_allocation": payment_allocation.pk,
                    "amount": "20.00",
                    "reason": "CSRF-protected manual settlement",
                },
            ).status_code,
            403,
        )

        other_user = User.objects.create_user(username="f66-other")
        other_organization = Organization.objects.create(
            name="F66 Other", slug="f66-other"
        )
        other_organization.memberships.create(
            user=other_user,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        other_client = Client()
        other_client.force_login(other_user)
        set_active_organization(other_client.session, other_organization)
        self.assertEqual(other_client.get(detail_url).status_code, 404)

        viewer = User.objects.create_user(username="f66-viewer")
        self.organization.memberships.create(
            user=viewer,
            role=MembershipRole.VIEWER,
            status=MembershipStatus.ACTIVE,
        )
        viewer_client = Client()
        viewer_client.force_login(viewer)
        set_active_organization(viewer_client.session, self.organization)
        self.assertEqual(
            viewer_client.post(
                reverse("billing:claim_settlement_allocate", args=[claim.pk]),
                {
                    "payment_allocation": payment_allocation.pk,
                    "amount": "20.00",
                    "reason": "Viewer must not allocate",
                },
            ).status_code,
            403,
        )

        response = self.client.post(
            reverse("billing:claim_settlement_allocate", args=[claim.pk]),
            {
                "payment_allocation": payment_allocation.pk,
                "amount": "20.00",
                "reason": "Manual partial settlement",
            },
        )
        self.assertRedirects(response, detail_url)
        self.assertEqual(ClaimSettlementAllocation.objects.count(), 1)


class ProgressClaimApprovalWorkflowConcurrencyTests(TransactionTestCase):
    """The submission lock creates one shared runtime instance under retries."""

    reset_sequences = True
    serialized_rollback = True

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        for alias in cls._databases_names(include_mirrors=False):
            database = connections[alias]
            serialized = getattr(database, "_test_serialized_contents", None)
            if serialized:
                database.creation.deserialize_db_from_string(serialized)

    def setUp(self) -> None:
        ProjectBaselineWorkflowTests.setUp(self)

    def _approved_baseline(self):
        return ProgressRecordWorkflowTests._approved_baseline(self)

    def _baseline(self, total: Decimal = Decimal("120.00")):
        return ProjectBaselineWorkflowTests._baseline(self, total=total)

    def _record(self):
        return ProgressRecordWorkflowTests._record(self)

    def _verified_record(self):
        return ProgressClaimCalculationTests._verified_record(self)

    def _claim(self):
        return ProgressClaimCalculationTests._claim(self)

    def _run_in_thread(self, callback):
        close_old_connections()
        try:
            return callback()
        finally:
            close_old_connections()

    def test_concurrent_submission_is_deduplicated_to_one_instance_and_audit(self):
        claim = self._claim()
        barrier = Barrier(2)

        def submit():
            barrier.wait()
            return self._run_in_thread(
                lambda: (
                    submit_progress_claim(
                        organization=Organization.objects.get(pk=self.organization.pk),
                        actor=User.objects.get(pk=self.owner.pk),
                        claim=ProgressClaim.objects.get(pk=claim.pk),
                    ).pk
                )
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            instance_ids = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(len(set(instance_ids)), 1)
        self.assertEqual(
            self.organization.workflow_instances.filter(
                subject_type="billing.progress_claim", subject_id=claim.pk
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                entity_id=str(claim.pk),
                action=AuditAction.PROGRESS_CLAIM_SUBMITTED,
            ).count(),
            1,
        )

    def test_concurrent_partial_settlements_cannot_exceed_claim_outstanding(self):
        claim = self._claim()
        submit_progress_claim(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
        )
        approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Concurrency settlement approval",
        )
        payment = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="F65-CONCURRENT-RECEIPT",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("100.00"),
            paid_on=date(2026, 9, 20),
            counterparty_name=self.party.display_name,
            party=self.party,
            contract=self.contract,
        )
        payment_allocation = allocate_payment(
            payment=payment,
            contract=self.contract,
            actor=self.owner,
            amount=Decimal("100.00"),
        )
        barrier = Barrier(2)

        def settle() -> object | None:
            barrier.wait(timeout=10)
            try:
                return self._run_in_thread(
                    lambda: allocate_progress_claim_settlement(
                        organization=Organization.objects.get(pk=self.organization.pk),
                        actor=User.objects.get(pk=self.owner.pk),
                        claim=ProgressClaim.objects.get(pk=claim.pk),
                        payment_allocation=payment_allocation.__class__.objects.get(
                            pk=payment_allocation.pk
                        ),
                        amount=Decimal("40.00"),
                        reason="Concurrent receipt settlement",
                    )
                )
            except ValidationError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            settlements = list(pool.map(lambda _: settle(), range(2)))
        self.assertEqual(sum(settlement is not None for settlement in settlements), 1)
        self.assertEqual(
            get_progress_claim_settlement_summary(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
            ).settled_amount,
            Decimal("40.00"),
        )
