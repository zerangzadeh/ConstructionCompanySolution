from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from apps.documents.models import (
    DocumentProcessingAssessment,
    DocumentProcessingVerdict,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import get_platform_policy_spec
from apps.parties.models import BusinessParty, PartyKind, PartyRole, PartyRoleType
from apps.procurement.admissibility_services import (
    approve_quote_admissibility,
    prepare_quote_admissibility,
)
from apps.procurement.comparison_services import (
    appoint_evaluator,
    decide_commercial_exception,
    declare_evaluator_conflict,
    dispose_evaluator_conflict,
    evaluate_comparison,
    finalize_comparison,
    finalize_sourcing_award,
    prepare_comparison,
    prepare_sourcing_award,
    propose_commercial_exception,
)
from apps.procurement.models import (
    CommercialComparison,
    CommercialComparisonInput,
    CommercialComparisonStatus,
    CommercialExceptionCode,
    CommercialExceptionStatus,
    CommercialScopeType,
    RFQCommercialScope,
    SourcingAward,
    SourcingAwardOutcome,
    SourcingAwardPreparation,
)
from apps.procurement.opening_services import (
    approve_quote_opening,
    grant_quote_confidential_access,
    request_quote_opening,
)
from apps.procurement.test_p5_s08_sealed_custody import SealedCustodyFixtureMixin
from apps.procurement.test_p5_s10_admissibility import AdmissibilityFixtureMixin


class P5S11FixtureMixin(AdmissibilityFixtureMixin):
    def setUp(self):
        super().setUp()
        self._activate_self_approval_policy(allow=False)
        self.decision = self._approve_admissible()
        line = self.revision.rfq_version.lines.get()
        self.scope = RFQCommercialScope.objects.create(
            organization=self.organization,
            rfq_version=self.revision.rfq_version,
            rfq_version_line=line,
            scope_type=CommercialScopeType.LINE,
            scope_code="LINE-1",
            required_quantity=line.quantity,
            unit_of_measure=line.unit_of_measure,
            independently_awardable=True,
            allows_split_award=True,
            created_by=self.owner,
        )
        for code in (
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_EVALUATE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_EXCEPTION,
            BusinessPermissionCode.RFQ_QUOTES_FINALIZE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_DISPOSE_CONFLICT,
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
            BusinessPermissionCode.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
        ):
            self._grant(code, self.preparer)
            self._grant(code, self.approver)
        self._activate_policy(
            "rfq-comparison-self-finalization",
            allow=getattr(self, "allow_s11_self_finalization", False),
        )
        self._activate_policy("rfq-commercial-exception-self-approval", allow=False)
        self._activate_policy(
            "rfq-sourcing-award-self-finalization",
            allow=getattr(self, "allow_s11_self_finalization", False),
        )

    def _approve_admissible(self):
        from apps.procurement.admissibility_services import approve_quote_admissibility

        return approve_quote_admissibility(
            organization=self.organization,
            actor=self.approver,
            preparation=self._prepare(),
        )

    def _activate_policy(self, code, *, allow):
        spec = get_platform_policy_spec(code)
        policy = PlatformPolicy.objects.create(
            code=spec.code,
            name=spec.name,
            category=spec.category,
            sensitivity=spec.sensitivity,
            tenant_selectable=True,
            requires_source_provenance=False,
            created_by=self.owner,
            updated_by=self.owner,
        )
        now = self.revision.created_at
        version = PlatformPolicyVersion.objects.create(
            policy=policy,
            version=1,
            parameters={"allow_self_approval": allow},
            effective_from=now.date(),
            status=PolicyVersionStatus.PUBLISHED,
            source_basis=PolicySourceBasis.PRODUCT_DEFINED,
            created_by=self.owner,
            published_by=self.owner,
            published_at=now,
            reason="P5-S11 test policy",
        )
        TenantPolicySelection.objects.create(
            organization=self.organization,
            policy=policy,
            policy_version=version,
            status=TenantPolicySelectionStatus.ACTIVE,
            approved_by=self.organization.memberships.get(user=self.owner),
            approved_at=now,
            applied_by=self.organization.memberships.get(user=self.owner),
            applied_at=now,
            reason="P5-S11 test activation",
        )

    def _comparison(self, *, key="comparison-1"):
        return prepare_comparison(
            organization=self.organization,
            actor=self.preparer,
            scope=self.scope,
            assertions=[
                {
                    "quote_revision_id": self.revision.pk,
                    "offered_quantity": str(self.scope.required_quantity),
                    "unit_price": "12.50",
                    "currency": "IRR",
                    "explicit_discount": "0.50",
                    "source_locator": "page-1-line-1",
                }
            ],
            idempotency_key=key,
        )

    def _evaluated_comparison(self):
        comparison = self._comparison()
        appointment = appoint_evaluator(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            membership=self.organization.memberships.get(user=self.preparer),
        )
        evaluate_comparison(
            organization=self.organization,
            actor=self.preparer,
            appointment=appointment,
            input=comparison.inputs.get(),
            recommendation="deterministic commercial review",
            evidence="evaluation-note-1",
        )
        return comparison, appointment


class P5S11ComparisonAwardTests(P5S11FixtureMixin, TestCase):
    def test_no_award_is_explicit_has_no_allocations_and_does_not_mutate_downstream(
        self,
    ):
        from apps.accounting.models import JournalEntry
        from apps.contracts.models import Contract
        from apps.projects.models import ProjectCostFact
        from apps.subledgers.models import Obligation
        from apps.treasury.models import TreasuryMovement

        comparison, _ = self._evaluated_comparison()
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="comparison complete",
        )
        before = {
            "orders": self.organization.purchase_orders.count(),
            "contracts": Contract.objects.filter(
                organization=self.organization
            ).count(),
            "obligations": Obligation.objects.filter(
                organization=self.organization
            ).count(),
            "journals": JournalEntry.objects.filter(
                organization=self.organization
            ).count(),
            "cash": TreasuryMovement.objects.filter(
                organization=self.organization
            ).count(),
            "budget": ProjectCostFact.objects.filter(
                organization=self.organization
            ).count(),
        }
        preparation = prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome=SourcingAwardOutcome.NO_AWARD,
            allocations=[],
            reason="commercial decision not to award",
            evidence="no-award evidence",
            idempotency_key="no-award-1",
        )
        award = finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=preparation
        )
        self.assertEqual(award.outcome, SourcingAwardOutcome.NO_AWARD)
        self.assertFalse(award.allocations.exists())
        self.assertEqual(award.unawarded_quantity, self.scope.required_quantity)
        self.assertEqual(
            before,
            {
                "orders": self.organization.purchase_orders.count(),
                "contracts": Contract.objects.filter(
                    organization=self.organization
                ).count(),
                "obligations": Obligation.objects.filter(
                    organization=self.organization
                ).count(),
                "journals": JournalEntry.objects.filter(
                    organization=self.organization
                ).count(),
                "cash": TreasuryMovement.objects.filter(
                    organization=self.organization
                ).count(),
                "budget": ProjectCostFact.objects.filter(
                    organization=self.organization
                ).count(),
            },
        )
        with self.assertRaises(ValueError):
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=finalized,
                outcome=SourcingAwardOutcome.NO_AWARD,
                allocations=[
                    {
                        "comparison_input_id": finalized.inputs.get().pk,
                        "quantity": "1",
                    }
                ],
                reason="invalid no-award",
                evidence="evidence",
                idempotency_key="no-award-invalid",
            )


class P5S11SelfFinalizationPolicyTests(P5S11FixtureMixin, TestCase):
    allow_s11_self_finalization = True

    def test_tenant_policy_explicitly_allows_s11_comparison_and_award_self_finalization(
        self,
    ):
        comparison, _ = self._evaluated_comparison()
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            reason="tenant policy permits self finalization",
        )
        preparation = prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome=SourcingAwardOutcome.AWARDED,
            allocations=[
                {
                    "comparison_input_id": finalized.inputs.get().pk,
                    "quantity": str(self.scope.required_quantity),
                }
            ],
            reason="tenant policy permits self award finalization",
            evidence="explicit tenant policy evidence",
            idempotency_key="self-finalization-enabled",
        )
        award = finalize_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            preparation=preparation,
        )
        self.assertEqual(finalized.finalized_by_id, self.preparer.pk)
        self.assertEqual(award.finalized_by_id, self.preparer.pk)


class P5S11TwoRevisionFixtureMixin(SealedCustodyFixtureMixin):
    """Two genuinely closed/opened/admitted revisions for comparison-only tests."""

    def setUp(self):
        super().setUp()
        self.preparer = self._make_actor("s11-two-preparer")
        self.approver = self._make_actor("s11-two-approver")
        self.supplier_two = BusinessParty.objects.create(
            organization=self.organization,
            display_name="Supplier two",
            party_kind=PartyKind.COMPANY,
        )
        PartyRole.objects.create(
            organization=self.organization,
            party=self.supplier_two,
            role=PartyRoleType.SUPPLIER,
        )
        revisions, self.manifest = self._closed_revision(
            suppliers=[self.supplier, self.supplier_two]
        )
        self.revision_one, self.revision_two = revisions
        self.revision = self.revision_one
        self._grant(BusinessPermissionCode.RFQS_CUSTODY_SEALED_EVIDENCE)
        for sequence, revision in enumerate(revisions, 1):
            self._accept_original(revision, key=f"two-original-{sequence}")
            for item in revision.evidence_items.select_related("document_version"):
                DocumentProcessingAssessment.objects.create(
                    organization=self.organization,
                    version=item.document_version,
                    sequence=1,
                    verdict=DocumentProcessingVerdict.CLEAN,
                    input_sha256=item.canonical_sha256,
                    adapter_code="s11-two-scanner",
                    adapter_version="1",
                    recorded_by=self.owner,
                )
        self._grant(BusinessPermissionCode.RFQ_QUOTES_OPEN)
        self._grant(BusinessPermissionCode.RFQ_QUOTES_APPROVE_OPEN, self.approver)
        self._grant(BusinessPermissionCode.RFQ_QUOTES_MANAGE_CONFIDENTIAL_ACCESS)
        for code in (
            BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_ADMISSIBILITY,
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_EVALUATE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_FINALIZE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_PREPARE_SOURCING_AWARD,
        ):
            self._grant(code, self.preparer)
        for code in (
            BusinessPermissionCode.RFQ_QUOTES_VIEW_CONFIDENTIAL,
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_ADMISSIBILITY,
            BusinessPermissionCode.RFQ_QUOTES_APPROVE_EXCEPTION,
            BusinessPermissionCode.RFQ_QUOTES_FINALIZE_COMPARISON,
            BusinessPermissionCode.RFQ_QUOTES_DISPOSE_CONFLICT,
            BusinessPermissionCode.RFQ_QUOTES_FINALIZE_SOURCING_AWARD,
        ):
            self._grant(code, self.approver)
        self._activate_policy("rfq-admissibility-self-approval", allow=False)
        self._activate_policy("rfq-comparison-self-finalization", allow=False)
        self._activate_policy("rfq-commercial-exception-self-approval", allow=False)
        self._activate_policy("rfq-sourcing-award-self-finalization", allow=False)
        for sequence, revision in enumerate(revisions, 1):
            with patch(
                "apps.procurement.opening_services.timezone.now",
                return_value=revision.rfq_version.earliest_opening_at
                + timedelta(seconds=1),
            ):
                opening = request_quote_opening(
                    organization=self.organization,
                    actor=self.owner,
                    quote_revision=revision,
                    reason="two-revision opening",
                    idempotency_key=f"two-open-{sequence}",
                )
                approve_quote_opening(
                    organization=self.organization,
                    actor=self.approver,
                    opening_request=opening,
                )
            for actor in (self.preparer, self.approver):
                grant_quote_confidential_access(
                    organization=self.organization,
                    actor=self.owner,
                    quote_revision=revision,
                    membership=self.organization.memberships.get(user=actor),
                    reason="two-revision review",
                    idempotency_key=f"two-grant-{sequence}-{actor.pk}",
                )
            prep = prepare_quote_admissibility(
                organization=self.organization,
                actor=self.preparer,
                quote_revision=revision,
                state="admissible",
                reason_code="requirements_met",
                rationale="two-revision admissible basis",
                idempotency_key=f"two-admissibility-{sequence}",
            )
            approve_quote_admissibility(
                organization=self.organization, actor=self.approver, preparation=prep
            )
        self.decision = self.revision_one.admissibility_decisions.latest("created_at")
        line = self.revision_one.rfq_version.lines.get()
        self.scope = RFQCommercialScope.objects.create(
            organization=self.organization,
            rfq_version=self.revision_one.rfq_version,
            rfq_version_line=line,
            scope_type=CommercialScopeType.LINE,
            scope_code="TWO-LINE",
            required_quantity=line.quantity,
            unit_of_measure=line.unit_of_measure,
            independently_awardable=True,
            allows_split_award=True,
            created_by=self.owner,
        )

    def _make_actor(self, username):
        from apps.accounts.models import User
        from apps.organizations.models import MembershipRole, MembershipStatus

        actor = User.objects.create_user(username=username, password="x")
        self.organization.memberships.create(
            user=actor,
            role=MembershipRole.TENANT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
        return actor

    def _activate_policy(self, code, *, allow):
        P5S11FixtureMixin._activate_policy(self, code, allow=allow)

    def _two_comparison(self, *, key="two-comparison", tied=False, scope=None):
        scope = scope or self.scope
        return prepare_comparison(
            organization=self.organization,
            actor=self.preparer,
            scope=scope,
            assertions=[
                {
                    "quote_revision_id": self.revision_one.pk,
                    "offered_quantity": str(scope.required_quantity),
                    "unit_price": "10",
                    "currency": "IRR",
                    "source_locator": "supplier-one",
                },
                {
                    "quote_revision_id": self.revision_two.pk,
                    "offered_quantity": str(scope.required_quantity),
                    "unit_price": "10" if tied else "11",
                    "currency": "IRR",
                    "source_locator": "supplier-two",
                },
            ],
            idempotency_key=key,
        )

    def _comparison(self, *, key="comparison-1"):
        return P5S11FixtureMixin._comparison(self, key=key)

    def _evaluated_comparison(self):
        return P5S11FixtureMixin._evaluated_comparison(self)


class P5S11TieAndSplitTests(P5S11TwoRevisionFixtureMixin, TestCase):
    def _finalized(self, *, tied=False, scope=None, key="two-comparison"):
        comparison = self._two_comparison(tied=tied, scope=scope, key=key)
        appointment = appoint_evaluator(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            membership=self.organization.memberships.get(user=self.preparer),
        )
        for item in comparison.inputs.all():
            evaluate_comparison(
                organization=self.organization,
                actor=self.preparer,
                appointment=appointment,
                input=item,
                recommendation="evaluated",
                evidence=f"evidence-{item.pk}",
            )
        return finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="two revision finalization",
        )

    def test_tie_requires_explicit_resolution_and_split_award_retains_exact_revisions(
        self,
    ):
        finalized = self._finalized(tied=True)
        self.assertEqual(
            finalized.status, CommercialComparisonStatus.TIE_REVIEW_REQUIRED
        )
        allocations = [
            {
                "comparison_input_id": item.pk,
                "quantity": str(self.scope.required_quantity / 2),
            }
            for item in finalized.inputs.order_by("created_at")
        ]
        with self.assertRaises(PermissionDenied):
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=finalized,
                outcome=SourcingAwardOutcome.AWARDED,
                allocations=allocations,
                reason="silent tie",
                evidence="evidence",
                idempotency_key="tie-silent",
            )
        preparation = prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome=SourcingAwardOutcome.AWARDED,
            allocations=allocations,
            reason="authorized tie resolution",
            evidence="tie-resolution-evidence",
            tie_resolution=True,
            idempotency_key="tie-resolved",
        )
        award = finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=preparation
        )
        self.assertEqual(award.allocations.count(), 2)
        self.assertEqual(
            sum((row.quantity for row in award.allocations.all()), Decimal(0)),
            self.scope.required_quantity,
        )
        self.assertEqual(
            set(award.allocations.values_list("quote_revision_id", flat=True)),
            {self.revision_one.pk, self.revision_two.pk},
        )

    def test_split_award_is_explicit_and_allocation_inputs_are_governing(self):
        line = self.revision_one.rfq_version.lines.get()
        unsplittable = RFQCommercialScope.objects.create(
            organization=self.organization,
            rfq_version=self.revision_one.rfq_version,
            rfq_version_line=line,
            scope_type=CommercialScopeType.LINE,
            scope_code="TWO-NOSPLIT",
            required_quantity=line.quantity,
            unit_of_measure=line.unit_of_measure,
            independently_awardable=True,
            allows_split_award=False,
            created_by=self.owner,
        )
        finalized = self._finalized(scope=unsplittable, key="two-no-split")
        split = [
            {"comparison_input_id": item.pk, "quantity": "5"}
            for item in finalized.inputs.order_by("created_at")
        ]
        with self.assertRaises(PermissionDenied):
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=finalized,
                outcome=SourcingAwardOutcome.AWARDED,
                allocations=split,
                reason="unauthorized split",
                evidence="split evidence",
                idempotency_key="no-split",
            )

        governing = self._finalized(key="two-allocation")
        item = governing.inputs.order_by("created_at").first()
        assert item is not None
        for quantity, key in (("0", "zero"), ("-1", "negative"), ("11", "over")):
            with self.assertRaises(ValueError):
                prepare_sourcing_award(
                    organization=self.organization,
                    actor=self.preparer,
                    comparison=governing,
                    outcome=SourcingAwardOutcome.AWARDED,
                    allocations=[{"comparison_input_id": item.pk, "quantity": quantity}],
                    reason="invalid allocation",
                    evidence="allocation evidence",
                    idempotency_key=f"allocation-{key}",
                )
        another = self._two_comparison(key="other-comparison")
        foreign_input = another.inputs.first()
        assert foreign_input is not None
        with self.assertRaises(CommercialComparisonInput.DoesNotExist):
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=governing,
                outcome=SourcingAwardOutcome.AWARDED,
                allocations=[{"comparison_input_id": foreign_input.pk, "quantity": "1"}],
                reason="ineligible input",
                evidence="allocation evidence",
                idempotency_key="foreign-input",
            )

    def test_reproducible_asserted_input_lineage_and_immutable_finalization(self):
        comparison, _appointment = self._evaluated_comparison()
        input = comparison.inputs.get()
        self.assertEqual(
            input.normalized_amount,
            self.scope.required_quantity * Decimal("12.50") - Decimal("0.50"),
        )
        self.assertEqual(
            input.calculation_lineage["transforms"],
            "none: no FX/tax/escalation/inferred_discount/unit_conversion",
        )
        self.assertEqual(input.admissibility_decision_id, self.decision.pk)
        self.assertEqual(self._comparison().pk, comparison.pk)
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="commercial review complete",
        )
        self.assertEqual(finalized.status, CommercialComparisonStatus.FINALIZED)
        self.assertEqual(finalized.supersedes_id, comparison.pk)
        input.assertion.currency = "USD"
        with self.assertRaises(ValidationError):
            input.assertion.save()

    def test_conflict_cannot_self_clear_and_blocks_evaluation_until_disposed(self):
        comparison, appointment = self._evaluated_comparison()
        # A new comparison avoids duplicate evaluator-input evaluation.
        comparison = self._comparison(key="comparison-conflict")
        appointment = appoint_evaluator(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            membership=self.organization.memberships.get(user=self.preparer),
        )
        conflict = declare_evaluator_conflict(
            organization=self.organization,
            actor=self.preparer,
            appointment=appointment,
            evidence="supplier relationship",
        )
        with self.assertRaises(PermissionDenied):
            dispose_evaluator_conflict(
                organization=self.organization,
                actor=self.preparer,
                conflict=conflict,
                approved=True,
                reason="self clear",
            )
        with self.assertRaises(PermissionDenied):
            evaluate_comparison(
                organization=self.organization,
                actor=self.preparer,
                appointment=appointment,
                input=comparison.inputs.get(),
                recommendation="blocked",
                evidence="blocked",
            )
        dispose_evaluator_conflict(
            organization=self.organization,
            actor=self.approver,
            conflict=conflict,
            approved=True,
            reason="independent disposition",
        )
        self.assertIsNotNone(
            evaluate_comparison(
                organization=self.organization,
                actor=self.preparer,
                appointment=appointment,
                input=comparison.inputs.get(),
                recommendation="released",
                evidence="post disposition",
            )
        )

    def test_exception_closed_catalogue_and_independent_lifecycle(self):
        exception = propose_commercial_exception(
            organization=self.organization,
            actor=self.preparer,
            revision=self.revision,
            scope=self.scope,
            code=CommercialExceptionCode.DISPLAY_FORMAT_VARIANCE,
            evidence="format-only evidence",
        )
        with self.assertRaises(ValueError):
            propose_commercial_exception(
                organization=self.organization,
                actor=self.preparer,
                revision=self.revision,
                scope=self.scope,
                code="late_material_change",
                evidence="not allowed",
            )
        result = decide_commercial_exception(
            organization=self.organization,
            actor=self.approver,
            exception=exception,
            approved=True,
            reason="non-material only",
        )
        self.assertEqual(result.status, CommercialExceptionStatus.APPROVED)
        self.assertEqual(result.supersedes_id, exception.pk)

    def test_award_is_sourcing_only_conserves_quantity_and_self_finalization_is_policy_gated(
        self,
    ):
        comparison, _ = self._evaluated_comparison()
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="final",
        )
        prep = prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome=SourcingAwardOutcome.AWARDED,
            allocations=[
                {
                    "comparison_input_id": finalized.inputs.get().pk,
                    "quantity": str(self.scope.required_quantity - Decimal(1)),
                }
            ],
            reason="partial award",
            evidence="award record",
            idempotency_key="award-1",
        )
        with self.assertRaises(PermissionDenied):
            finalize_sourcing_award(
                organization=self.organization, actor=self.preparer, preparation=prep
            )
        award = finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=prep
        )
        self.assertEqual(award.unawarded_quantity, Decimal(1))
        self.assertEqual(
            award.allocations.aggregate(
                total=__import__("django.db.models", fromlist=["Sum"]).Sum("quantity")
            )["total"],
            self.scope.required_quantity - Decimal(1),
        )
        self.assertEqual(SourcingAward.objects.count(), 1)
        with self.assertRaises(ValueError):
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=finalized,
                outcome=SourcingAwardOutcome.AWARDED,
                allocations=[
                    {
                        "comparison_input_id": finalized.inputs.get().pk,
                        "quantity": str(self.scope.required_quantity + Decimal(1)),
                    }
                ],
                reason="over allocate",
                evidence="evidence",
                idempotency_key="award-over",
            )


class P5S11ConcurrencyTests(P5S11FixtureMixin, TransactionTestCase):
    """Exercise real PostgreSQL row locking on one immutable governing scope."""

    def _concurrently(self, callback):
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return callback()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(lambda _index: run(), range(2)))

    def test_postgresql_finalization_contention_is_idempotent_and_conserves_award_quantity(
        self,
    ):
        comparison, _ = self._evaluated_comparison()
        organization_id = self.organization.pk
        approver_id = self.approver.pk
        comparison_id = comparison.pk

        def finalize_same_comparison():
            return finalize_comparison(
                organization=type(self.organization).objects.get(pk=organization_id),
                actor=type(self.approver).objects.get(pk=approver_id),
                comparison=CommercialComparison.objects.get(pk=comparison_id),
                reason="concurrent comparison finalization",
            ).pk

        comparison_results = self._concurrently(finalize_same_comparison)
        self.assertEqual(len(set(comparison_results)), 1)
        finalized_id = comparison_results[0]
        self.assertEqual(
            CommercialComparison.objects.filter(supersedes_id=comparison_id).count(), 1
        )
        finalized = CommercialComparison.objects.get(pk=finalized_id)

        preparations = [
            prepare_sourcing_award(
                organization=self.organization,
                actor=self.preparer,
                comparison=finalized,
                outcome=SourcingAwardOutcome.AWARDED,
                allocations=[
                    {
                        "comparison_input_id": finalized.inputs.get().pk,
                        "quantity": str(self.scope.required_quantity),
                    }
                ],
                reason=f"concurrent award {number}",
                evidence="award concurrency evidence",
                idempotency_key=f"concurrent-award-{number}",
            )
            for number in (1, 2)
        ]

        preparation_ids = [preparation.pk for preparation in preparations]

        def finalize_competing_award():
            preparation_id = preparation_ids.pop()
            try:
                return finalize_sourcing_award(
                    organization=type(self.organization).objects.get(pk=organization_id),
                    actor=type(self.approver).objects.get(pk=approver_id),
                    preparation=SourcingAwardPreparation.objects.get(pk=preparation_id),
                ).pk
            except ValueError:
                return "ValueError"

        award_results = self._concurrently(finalize_competing_award)
        successful = [result for result in award_results if result != "ValueError"]
        self.assertEqual(len(successful), 1)
        self.assertEqual(award_results.count("ValueError"), 1)
        self.assertEqual(SourcingAward.objects.filter(comparison=finalized).count(), 1)
        award = SourcingAward.objects.get(pk=successful[0])
        self.assertEqual(
            sum((row.quantity for row in award.allocations.all()), Decimal(0)),
            self.scope.required_quantity,
        )
        retry = finalize_sourcing_award(
            organization=self.organization,
            actor=self.approver,
            preparation=award.preparation,
        )
        self.assertEqual(retry.pk, award.pk)
