from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from apps.accounting.posting_registry import get_posting_contract
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.billing.handoffs import (
    PROGRESS_CLAIM_POSTING_EVENT_KIND,
    PROGRESS_CLAIM_SOURCE_KIND,
    resolve_progress_claim_obligation_source,
)
from apps.billing.models import (
    ProgressClaim,
    ProgressClaimCorrectionKind,
    ProgressRecordStatus,
    ProjectBaselineStatus,
)
from apps.billing.services import (
    _resolve_regulatory_rule_version,
    add_baseline_item,
    approve_progress_claim,
    approve_project_baseline,
    create_progress_claim,
    create_progress_claim_correction,
    create_progress_claim_revision,
    create_progress_correction,
    create_progress_record,
    create_project_baseline,
    recalculate_progress_claim,
    request_progress_verification,
    request_project_baseline_approval,
    return_progress_claim,
    submit_progress_claim,
    update_billing_configuration,
    verify_progress_record,
)
from apps.contracts.models import (
    ContractAmendment,
    ContractAmendmentStatus,
    ContractDirection,
    ContractStatus,
    ContractTermVersionStatus,
)
from apps.contracts.services import (
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
)
from apps.organizations.access_services import assign_platform_admin
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    PlatformPolicyVersion,
    PolicyReviewDisposition,
    PolicySourceBasis,
    PolicyVersionStatus,
)
from apps.organizations.policy_services import (
    create_platform_policy,
    link_policy_version_source,
    publish_platform_policy_version,
    record_optional_policy_review,
    record_policy_source,
    retire_platform_policy_version,
)
from apps.organizations.policy_specs import RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party, update_business_party
from apps.projects.services import create_project
from apps.subledgers.services import recognize_obligation
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
        self.tenant_admin = User.objects.create_user(username="f61-tenant-admin")
        self.policy_author = User.objects.create_superuser(
            username="f61-policy-author", password="unused"
        )
        self.policy_approver = User.objects.create_superuser(
            username="f61-policy-approver", password="unused"
        )
        policy_grantor = User.objects.create_superuser(
            username="f61-policy-grantor", password="unused"
        )
        policy_grant_approver = User.objects.create_superuser(
            username="f61-policy-grant-approver", password="unused"
        )
        assign_platform_admin(
            actor=policy_grantor,
            approver=policy_grant_approver,
            target=self.policy_author,
            reason="Billing policy test author authority",
        )
        assign_platform_admin(
            actor=policy_grantor,
            approver=policy_grant_approver,
            target=self.policy_approver,
            reason="Billing policy test approver authority",
        )
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
        self.organization.memberships.create(
            user=self.tenant_admin,
            role=MembershipRole.TENANT_ADMIN,
            status=MembershipStatus.ACTIVE,
        )
        from tests.retirement_fixtures import explicit_fixture_roles

        explicit_fixture_roles(self.organization)
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
        self.contract_terms = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 1, 1),
            reason="Initial receivable claim terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=self.contract_terms,
            reason="Independent commercial approval",
        )
        self.regulatory_rules = self._publish_regulatory_rules(
            effective_from=date(2026, 1, 1),
            tax_rate="0",
            insurance_rate="0",
        )

    def _publish_regulatory_rules(
        self,
        *,
        effective_from: date,
        tax_rate: str,
        insurance_rate: str,
    ) -> PlatformPolicyVersion:
        policy = create_platform_policy(
            actor=self.policy_author,
            code=RECEIVABLE_CLAIM_REGULATORY_POLICY_CODE,
            reason="Test-only regulatory schema fixture",
        )
        current = policy.versions.filter(status=PolicyVersionStatus.PUBLISHED).first()
        if current is not None:
            retire_platform_policy_version(
                actor=self.policy_approver,
                policy_version=current,
                reason="Superseded by test fixture",
            )
        version_number = policy.versions.count() + 1
        draft = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=version_number,
            parameters={
                "tax_rate": tax_rate,
                "tax_basis": "gross",
                "insurance_rate": insurance_rate,
                "insurance_basis": "gross",
            },
            effective_from=effective_from,
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            created_by=self.policy_author,
            reason="Test-only values; no product statutory assertion",
        )
        source = record_policy_source(
            actor=self.policy_author,
            issuer="Test authority",
            title="Test-only calculation evidence",
            source_identifier=f"TEST-CLAIM-RULE-{version_number}",
            version=str(version_number),
            applicability="Automated test fixture only",
            reason="No legal or production meaning",
            effective_from=effective_from,
        )
        link_policy_version_source(
            actor=self.policy_author,
            policy_version=draft,
            source=source,
            reason="Test provenance",
        )
        record_optional_policy_review(
            actor=self.policy_approver,
            policy_version=draft,
            reviewer_identity="Automated test reviewer",
            qualification_summary="Test fixture only",
            independence_statement="Different test actor from author",
            evidence_reference=f"TEST-REVIEW-{version_number}",
            reviewed_on=effective_from,
            review_scope="Parameter shape and arithmetic only",
            disposition=PolicyReviewDisposition.ACCEPTED,
        )
        published = publish_platform_policy_version(
            actor=self.policy_approver,
            policy_version=draft,
            reason="Independent test-only publication",
        )
        return published

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

    def test_pinned_terms_and_rules_drive_rounding_and_adjustments(self) -> None:
        record = self._verified_record()
        update_billing_configuration(
            organization=self.organization,
            actor=self.owner,
            currency_decimal_places=2,
        )
        terms = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 9, 1),
            reason="September commercial terms",
            retention_rate=Decimal(10),
            retention_cap=Decimal(3),
            advance_recovery_rate=Decimal(10),
            advance_recovery_cap=Decimal(2),
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=terms,
            reason="Independent commercial approval",
        )
        rules = self._publish_regulatory_rules(
            effective_from=date(2026, 9, 1),
            tax_rate="10",
            insurance_rate="5",
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
        self.assertEqual(claim.contract_term_version_id, terms.pk)
        self.assertEqual(claim.regulatory_rule_version_id, rules.pk)

    def test_claim_revision_reuses_sources_without_rewriting_history(self) -> None:
        claim = self._claim()
        revision = create_progress_claim_revision(
            organization=self.organization, actor=self.owner, claim=claim
        )
        self.assertEqual(revision.revision_number, 2)
        self.assertEqual(revision.items.get().sources.count(), 1)
        self.assertEqual(claim.items.get().sources.count(), 1)

    def test_term_and_regulatory_approval_enforce_sod_and_immutability(self) -> None:
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2027, 1, 1),
            reason="Future commercial version",
        )
        with self.assertRaises(PermissionDenied):
            approve_contract_term_version(
                organization=self.organization,
                actor=self.owner,
                term_version=term,
                reason="Self approval is prohibited",
            )
        approved_term = approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent approval",
        )
        self.assertEqual(approved_term.status, ContractTermVersionStatus.APPROVED)
        approved_term.retention_rate = Decimal(1)
        with self.assertRaises(ValidationError):
            approved_term.save()

        retire_platform_policy_version(
            actor=self.policy_approver,
            policy_version=self.regulatory_rules,
            reason="Prepare isolated SoD test version",
        )
        policy = self.regulatory_rules.policy
        rule = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=2,
            parameters={
                "tax_rate": "0",
                "tax_basis": "gross",
                "insurance_rate": "0",
                "insurance_basis": "gross",
            },
            effective_from=date(2027, 1, 1),
            source_basis=PolicySourceBasis.EXTERNAL_AUTHORITY,
            created_by=self.policy_author,
            reason="Future test-only regulatory version",
        )
        source = record_policy_source(
            actor=self.policy_author,
            issuer="Test authority",
            title="Future test rule",
            source_identifier="TEST-CLAIM-RULE-SOD",
            version="2",
            applicability="Automated test fixture only",
            reason="No legal or production meaning",
        )
        link_policy_version_source(
            actor=self.policy_author,
            policy_version=rule,
            source=source,
            reason="Test provenance",
        )
        with self.assertRaises(ValidationError):
            publish_platform_policy_version(
                actor=self.policy_author,
                policy_version=rule,
                reason="Unreviewed rule fails closed for every publisher",
            )
        with self.assertRaises(ValidationError):
            publish_platform_policy_version(
                actor=self.policy_approver,
                policy_version=rule,
                reason="Unreviewed rule fails closed",
            )
        record_optional_policy_review(
            actor=self.policy_approver,
            policy_version=rule,
            reviewer_identity="Independent test reviewer",
            qualification_summary="Test fixture only",
            independence_statement="Different actor from author",
            evidence_reference="TEST-CLAIM-RULE-SOD-REVIEW",
            reviewed_on=date(2026, 10, 2),
            review_scope="Parameter schema and arithmetic only",
            disposition=PolicyReviewDisposition.ACCEPTED,
        )
        approved_rule = publish_platform_policy_version(
            actor=self.policy_approver,
            policy_version=rule,
            reason="Independent reviewed publication",
        )
        self.assertEqual(approved_rule.status, PolicyVersionStatus.PUBLISHED)
        approved_rule.parameters = {**approved_rule.parameters, "tax_rate": "1"}
        with self.assertRaises(ValidationError):
            approved_rule.save()

    def test_claim_creation_fails_closed_without_eligible_regulatory_rule(self) -> None:
        policy = self.regulatory_rules.policy
        policy.is_active = False
        policy.save(update_fields=["is_active", "updated_at"])
        with self.assertRaises(ValidationError):
            _resolve_regulatory_rule_version(
                organization=self.organization,
                on_date=date(2026, 9, 30),
            )

    def test_claim_snapshots_ignore_later_party_and_configuration_changes(self) -> None:
        claim = self._claim()
        party_snapshot_id = claim.party_identity_snapshot_id
        configuration_snapshot = claim.billing_configuration_snapshot.copy()
        update_business_party(
            organization=self.organization,
            actor=self.owner,
            party=self.party,
            party_kind=PartyKind.COMPANY,
            display_name="Renamed client",
            legal_name="Renamed legal client",
        )
        update_billing_configuration(
            organization=self.organization,
            actor=self.owner,
            currency_decimal_places=2,
        )
        refreshed = recalculate_progress_claim(
            organization=self.organization,
            actor=self.owner,
            claim=claim,
        )
        self.assertEqual(refreshed.party_identity_snapshot_id, party_snapshot_id)
        self.assertEqual(
            refreshed.billing_configuration_snapshot, configuration_snapshot
        )

    def test_overlapping_draft_period_and_negative_net_are_rejected(self) -> None:
        record = self._verified_record()
        terms = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 9, 1),
            reason="Negative-net rejection fixture",
            retention_rate=Decimal(100),
            retention_cap=Decimal(999),
            advance_recovery_rate=Decimal(100),
            advance_recovery_cap=Decimal(999),
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=terms,
            reason="Independent commercial approval",
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
        safe_terms = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 10, 1),
            reason="Safe October terms",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=safe_terms,
            reason="Independent commercial approval",
        )
        create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=record.baseline,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measurement_cutoff=date(2026, 10, 31),
        )
        with self.assertRaises(ValidationError):
            create_progress_claim(
                organization=self.organization,
                actor=self.owner,
                baseline=record.baseline,
                period_start=date(2026, 10, 15),
                period_end=date(2026, 11, 15),
                measurement_cutoff=date(2026, 10, 31),
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

    def _approve_claim(self, claim: ProgressClaim) -> ProgressClaim:
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=claim
        )
        return approve_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=claim,
            reason="Independent claim approval",
        )

    def test_cumulative_claim_uses_prior_certified_quantity_across_amended_baseline(
        self,
    ) -> None:
        self._configure_reporting_line()
        first = self._approve_claim(self._claim_for_approval())
        second_baseline = self._baseline()
        request_project_baseline_approval(
            organization=self.organization, actor=self.owner, baseline=second_baseline
        )
        second_baseline = approve_project_baseline(
            organization=self.organization,
            actor=self.manager,
            baseline=second_baseline,
            reason="Approved amendment baseline",
        )
        record = create_progress_record(
            organization=self.organization,
            actor=self.owner,
            baseline=second_baseline,
            baseline_item=second_baseline.items.get(),
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measured_on=date(2026, 10, 20),
            source_type="site_report",
            source_reference="DR-002",
            period_quantity=Decimal("0.3000"),
            cumulative_quantity=Decimal("0.8000"),
            evidence="amendment-aware cumulative evidence",
        )
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=record,
            reason="Verified amended-baseline progress",
        )
        second = create_progress_claim(
            organization=self.organization,
            actor=self.owner,
            baseline=second_baseline,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 31),
            measurement_cutoff=date(2026, 10, 31),
        )
        item = second.items.get()
        self.assertEqual(item.previous_cumulative_quantity, Decimal("0.5000"))
        self.assertEqual(item.current_quantity, Decimal("0.3000"))
        self.assertEqual(item.current_amount, Decimal("36.0000"))
        self.assertEqual(second.calculation_snapshot["prior_approved_gross"], "60.0000")
        self.assertEqual(
            second.calculation_snapshot["prior_active_approved_claim_ids"],
            [str(first.pk)],
        )

    def test_replacement_correction_supersedes_without_rewriting_original(self) -> None:
        self._configure_reporting_line()
        original = self._approve_claim(self._claim_for_approval())
        source = original.items.get().sources.get().progress_record
        corrected = create_progress_correction(
            organization=self.organization,
            actor=self.owner,
            record=source,
            source_type="site_report_correction",
            source_reference="DR-001-C1",
            period_quantity=Decimal("0.4000"),
            cumulative_quantity=Decimal("0.4000"),
            evidence="signed correction",
        )
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=corrected
        )
        verify_progress_record(
            organization=self.organization,
            actor=self.manager,
            record=corrected,
            reason="Verified measurement correction",
        )
        replacement = create_progress_claim_correction(
            organization=self.organization,
            actor=self.owner,
            claim=original,
            correction_kind=ProgressClaimCorrectionKind.REPLACEMENT,
            reason="Replace certified quantity with corrected evidence",
        )
        self.assertEqual(replacement.net_amount, Decimal("48.0000"))
        replacement = self._approve_claim(replacement)
        original.refresh_from_db()
        self.assertEqual(original.status, "superseded")
        self.assertEqual(replacement.status, "approved")
        self.assertEqual(replacement.corrects_id, original.pk)
        self.assertEqual(original.net_amount, Decimal("60.0000"))

    def test_returned_correction_revision_preserves_lineage(self) -> None:
        self._configure_reporting_line()
        original = self._approve_claim(self._claim_for_approval())
        correction = create_progress_claim_correction(
            organization=self.organization,
            actor=self.owner,
            claim=original,
            correction_kind=ProgressClaimCorrectionKind.REPLACEMENT,
            reason="Correct certification evidence",
        )
        submit_progress_claim(
            organization=self.organization, actor=self.owner, claim=correction
        )
        returned = return_progress_claim(
            organization=self.organization,
            actor=self.manager,
            claim=correction,
            reason="Provide stronger correction evidence",
        )
        revision = returned.returned_revision
        self.assertEqual(returned.status, "returned")
        self.assertEqual(revision.status, "draft")
        self.assertEqual(revision.corrects_id, original.pk)
        self.assertEqual(
            revision.correction_kind, ProgressClaimCorrectionKind.REPLACEMENT
        )
        approved = self._approve_claim(revision)
        original.refresh_from_db()
        self.assertEqual(approved.status, "approved")
        self.assertEqual(original.status, "superseded")

    def test_linked_cancellation_is_zero_and_closes_active_claim(self) -> None:
        self._configure_reporting_line()
        original = self._approve_claim(self._claim_for_approval())
        cancellation = create_progress_claim_correction(
            organization=self.organization,
            actor=self.owner,
            claim=original,
            correction_kind=ProgressClaimCorrectionKind.CANCELLATION,
            reason="Cancel certification with retained evidence",
        )
        self.assertEqual(cancellation.net_amount, Decimal(0))
        self.assertFalse(cancellation.items.exists())
        cancellation = self._approve_claim(cancellation)
        original.refresh_from_db()
        self.assertEqual(original.status, "cancelled")
        self.assertEqual(cancellation.status, "approved")

    def test_approved_claim_exposes_dormant_ar_and_posting_contracts(self) -> None:
        self._configure_reporting_line()
        claim = self._approve_claim(self._claim_for_approval())
        source = resolve_progress_claim_obligation_source(
            self.organization, claim.pk, claim.revision_number, ""
        )
        self.assertEqual(source.source_kind, PROGRESS_CLAIM_SOURCE_KIND)
        self.assertEqual(source.amount, claim.net_amount)
        self.assertEqual(source.due_date, claim.due_date)
        self.assertIsNotNone(source.due_date)
        self.assertEqual(source.source_snapshot["claim_id"], str(claim.pk))
        posting = get_posting_contract(
            source_kind=PROGRESS_CLAIM_SOURCE_KIND,
            event_kind=PROGRESS_CLAIM_POSTING_EVENT_KIND,
        )
        self.assertEqual(posting.source_owner, "billing")
        self.assertFalse(posting.operational_producer)

    def test_recognized_ar_obligation_blocks_claim_correction(self) -> None:
        self._configure_reporting_line()
        claim = self._approve_claim(self._claim_for_approval())
        recognize_obligation(
            organization=self.organization,
            actor=self.owner,
            source_kind=PROGRESS_CLAIM_SOURCE_KIND,
            source_uuid=claim.pk,
            source_version=claim.revision_number,
            idempotency_key=f"CLAIM-{claim.pk}",
        )
        with self.assertRaises(ValidationError):
            create_progress_claim_correction(
                organization=self.organization,
                actor=self.owner,
                claim=claim,
                correction_kind=ProgressClaimCorrectionKind.CANCELLATION,
                reason="Blocked until AR is resolved",
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

    def test_small_tenant_submitter_is_excluded_when_fallback_approver_exists(self):
        fallback_claim = self._claim_for_approval()
        self.manager_membership.status = MembershipStatus.SUSPENDED
        self.manager_membership.save(update_fields=["status", "updated_at"])
        instance = submit_progress_claim(
            organization=self.organization,
            actor=self.owner,
            claim=fallback_claim,
        )
        item = instance.work_items.get()
        self.assertFalse(
            WorkItemCandidate.objects.filter(
                work_item=item,
                membership__user=self.owner,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            WorkItemCandidate.objects.filter(work_item=item, is_active=True)
            .exclude(membership__user=self.owner)
            .exists()
        )

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


class ProgressClaimApprovalWorkflowConcurrencyTests(TransactionTestCase):
    """The submission lock creates one shared runtime instance under retries."""

    reset_sequences = True
    serialized_rollback = True

    def setUp(self) -> None:
        ProjectBaselineWorkflowTests.setUp(self)

    def _publish_regulatory_rules(self, **kwargs):
        return ProjectBaselineWorkflowTests._publish_regulatory_rules(self, **kwargs)

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
