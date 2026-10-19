from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, FiscalYear, JournalEntry
from apps.accounts.models import User
from apps.equipment.cost_services import (
    create_cost_policy,
    create_cost_rate,
    finalize_cost_allocation,
    prepare_cost_allocation,
    prepare_cost_handoff,
    publish_cost_policy,
    reconcile_cost_handoff,
    reverse_cost_allocation,
    review_cost_handoff,
    review_cost_policy,
)
from apps.equipment.models import EquipmentAssignment, EquipmentAssignmentStatus
from apps.equipment.p8_services import record_usage
from apps.equipment.tests import EquipmentTestBase
from apps.fixed_assets.models import (
    AssetStatus,
    AssetTransactionType,
    DepreciationConvention,
    DepreciationRunStatus,
    EnvelopeStatus,
    PolicyStatus,
)
from apps.fixed_assets.services import (
    add_asset_source,
    capitalize_asset,
    create_asset_class,
    create_book_policy,
    finalize_asset_transaction,
    finalize_depreciation,
    prepare_asset,
    prepare_asset_transaction,
    prepare_handoff,
    preview_depreciation,
    publish_policy,
    reconcile_handoff,
    reverse_asset_transaction,
    reverse_depreciation,
    review_asset_source,
    review_handoff,
    review_policy,
)
from apps.organizations.models import MembershipRole, MembershipStatus
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project, ProjectCostFact, ProjectSite


class P8CostAndFixedAssetTests(EquipmentTestBase, TestCase):
    def setUp(self):
        super().setUp()
        self.reviewer = User.objects.create_user(username="p8-cost-reviewer")
        self.approver = User.objects.create_user(username="p8-asset-approver")
        for user in (self.reviewer, self.approver):
            self.organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.ACTIVE,
            )
        self.equipment = self.make_equipment()
        self.deployment = EquipmentAssignment.objects.create(
            organization=self.organization,
            equipment=self.equipment,
            project=self.project,
            site=self.site,
            start_date=self.today - timedelta(days=30),
            status=EquipmentAssignmentStatus.ACTIVE,
            created_by=self.owner,
            updated_by=self.owner,
        )

    def _published_cost_policy(self):
        policy = create_cost_policy(
            organization=self.organization,
            actor=self.owner,
            code="INTERNAL-HOUR",
            version=1,
            effective_from=self.today - timedelta(days=30),
            monetary_policy_code="accounting-money-precision",
            monetary_policy_version="v1",
            decimal_places=0,
        )
        create_cost_rate(
            organization=self.organization,
            actor=self.owner,
            policy=policy,
            equipment=self.equipment,
            rate_amount=Decimal(1000),
            component_snapshot={"base_internal": "1000"},
            effective_from=self.today - timedelta(days=30),
        )
        review_cost_policy(
            organization=self.organization, actor=self.reviewer, policy=policy
        )
        return publish_cost_policy(
            organization=self.organization, actor=self.reviewer, policy=policy
        )

    def _published_asset_policies(self, convention=DepreciationConvention.FULL_MONTH):
        asset_class = create_asset_class(
            organization=self.organization,
            actor=self.owner,
            code="MACH",
            name="Machinery",
            version=1,
            effective_from=date(2026, 1, 1),
            account_mapping_reference="MAP-ASSET-01",
            capitalization_policy_reference="CAP-01",
        )
        book = create_book_policy(
            organization=self.organization,
            actor=self.owner,
            code="BOOK",
            version=1,
            effective_from=date(2026, 1, 1),
            monetary_policy_code="accounting-money-precision",
            monetary_policy_version="v1",
            convention=convention,
            decimal_places=0,
        )
        for policy in (asset_class, book):
            review_policy(
                organization=self.organization, actor=self.reviewer, policy=policy
            )
            publish_policy(
                organization=self.organization, actor=self.reviewer, policy=policy
            )
            policy.refresh_from_db()
            self.assertEqual(policy.status, PolicyStatus.PUBLISHED)
        return asset_class, book

    def _capitalized_asset(
        self,
        *,
        ready_for_use_date=date(2026, 1, 1),
        convention=DepreciationConvention.FULL_MONTH,
        useful_life_months=10,
        residual_value=Decimal(0),
        capitalization_basis=Decimal(10000),
    ):
        asset_class, book = self._published_asset_policies(convention)
        asset = prepare_asset(
            organization=self.organization,
            actor=self.owner,
            asset_number="FA-0001",
            name="Excavator financial identity",
            asset_class=asset_class,
            book_policy=book,
            ready_for_use_date=ready_for_use_date,
            useful_life_months=useful_life_months,
            residual_value=residual_value,
            capitalization_basis=capitalization_basis,
            evidence_reference="DMS-ASSET-1",
            project=self.project,
            site=self.site,
        )
        source = add_asset_source(
            organization=self.organization,
            actor=self.owner,
            asset=asset,
            source_family="acquisition",
            source_public_id="ACQ-1",
            source_version="1",
            source_date=date(2026, 1, 1),
            amount=capitalization_basis,
            evidence_reference="DMS-ACQ-1",
        )
        review_asset_source(
            organization=self.organization, actor=self.reviewer, source=source
        )
        capitalization = capitalize_asset(
            organization=self.organization,
            actor=self.approver,
            asset=asset,
            source=source,
            occurrence_key="CAP-FA-0001",
        )
        capitalization_retry = capitalize_asset(
            organization=self.organization,
            actor=self.approver,
            asset=asset,
            source=source,
            occurrence_key="CAP-FA-0001",
        )
        self.assertEqual(capitalization_retry.pk, capitalization.pk)
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        return asset, book

    def test_equipment_cost_is_conserved_proposal_with_no_actual_or_journal(self):
        self._published_cost_policy()
        usage = record_usage(
            organization=self.organization,
            actor=self.owner,
            equipment=self.equipment,
            deployment=self.deployment,
            started_at=timezone.now() - timedelta(hours=2),
            ended_at=timezone.now(),
            runtime_hours=Decimal(2),
            source_key="USAGE-COST-1",
        )
        allocation = prepare_cost_allocation(
            organization=self.organization,
            actor=self.owner,
            usage=usage,
            source_key="ALLOC-1",
        )
        allocation_retry = prepare_cost_allocation(
            organization=self.organization,
            actor=self.owner,
            usage=usage,
            source_key="ALLOC-1",
        )
        self.assertEqual(allocation_retry.pk, allocation.pk)
        self.assertEqual(allocation.amount, Decimal(2000))
        with self.assertRaises(ValueError):
            finalize_cost_allocation(
                organization=self.organization, actor=self.owner, allocation=allocation
            )
        finalize_cost_allocation(
            organization=self.organization,
            actor=self.reviewer,
            allocation=allocation,
        )
        envelope = prepare_cost_handoff(
            organization=self.organization,
            actor=self.owner,
            allocation=allocation,
            occurrence_key="EQ-PC-1",
        )
        review_cost_handoff(
            organization=self.organization, actor=self.reviewer, envelope=envelope
        )
        reconcile_cost_handoff(
            organization=self.organization,
            actor=self.approver,
            envelope=envelope,
            consumer_reference="PC-ACK-1",
            reconciliation_note="Proposal-only tie-out",
        )
        reversal = reverse_cost_allocation(
            organization=self.organization,
            actor=self.approver,
            allocation=allocation,
            reason="Correction",
        )
        envelope.refresh_from_db()
        self.assertEqual(envelope.status, "reconciled")
        self.assertEqual(reversal.amount, Decimal(-2000))
        self.assertEqual(allocation.amount + reversal.amount, Decimal(0))
        self.assertEqual(envelope.source_amount, allocation.amount)
        with self.assertRaises(ValueError):
            prepare_cost_handoff(
                organization=self.organization,
                actor=self.owner,
                allocation=allocation,
                occurrence_key="EQ-PC-DUPLICATE",
            )
        self.assertFalse(ProjectCostFact.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())

    def test_daily_prorata_depreciation_uses_ready_for_use_days(self):
        asset, book = self._capitalized_asset(
            ready_for_use_date=date(2026, 1, 16),
            convention=DepreciationConvention.DAILY_PRORATA,
        )
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY26",
            name="FY 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=period,
            occurrence_key="DEP-2026-01-PRORATA",
        )
        self.assertEqual(run.lines.get(asset=asset).depreciation_amount, Decimal(516))

    def test_straight_line_run_reversal_and_proposal_create_no_gl_or_actual(self):
        asset, book = self._capitalized_asset()
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY26",
            name="FY 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=period,
            occurrence_key="DEP-2026-01",
        )
        run_retry = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=period,
            occurrence_key="DEP-2026-01",
        )
        self.assertEqual(run_retry.pk, run.pk)
        self.assertEqual(run.lines.get(asset=asset).depreciation_amount, Decimal(1000))
        with self.assertRaises(ValueError):
            finalize_depreciation(
                organization=self.organization, actor=self.owner, run=run
            )
        finalize_depreciation(
            organization=self.organization, actor=self.reviewer, run=run
        )
        line = run.lines.get(asset=asset)
        envelope = prepare_handoff(
            organization=self.organization,
            actor=self.owner,
            consumer="accounting",
            occurrence_key="FA-GL-PROP-1",
            depreciation_line=line,
        )
        with self.assertRaises(ValueError):
            prepare_handoff(
                organization=self.organization,
                actor=self.owner,
                consumer="accounting",
                occurrence_key="FA-GL-PROP-DUPLICATE",
                depreciation_line=line,
            )
        review_handoff(
            organization=self.organization, actor=self.reviewer, envelope=envelope
        )
        evidence = reconcile_handoff(
            organization=self.organization,
            actor=self.approver,
            envelope=envelope,
            consumer_reference="GL-ACK-1",
            consumer_amount=Decimal(1000),
            disposition="Proposal evidence tied out",
        )
        reversal = reverse_depreciation(
            organization=self.organization,
            actor=self.approver,
            run=run,
            occurrence_key="DEP-2026-01-REV",
            reason="Reviewed correction",
        )
        envelope.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(envelope.status, EnvelopeStatus.RECONCILED)
        self.assertEqual(evidence.difference, Decimal(0))
        self.assertEqual(run.status, DepreciationRunStatus.REVERSED)
        self.assertEqual(
            reversal.lines.get(asset=asset).depreciation_amount, Decimal(-1000)
        )
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_impairment_uses_review_and_linked_reversal(self):
        asset, _book = self._capitalized_asset()
        impairment = prepare_asset_transaction(
            organization=self.organization,
            actor=self.owner,
            asset=asset,
            transaction_type=AssetTransactionType.IMPAIRMENT,
            occurred_on=date(2026, 2, 1),
            amount=Decimal(500),
            occurrence_key="IMP-1",
            reason="Reviewed impairment evidence",
        )
        finalize_asset_transaction(
            organization=self.organization,
            actor=self.reviewer,
            transaction_record=impairment,
        )
        reversal = reverse_asset_transaction(
            organization=self.organization,
            actor=self.approver,
            transaction_record=impairment,
            occurrence_key="IMP-1-REV",
            reason="Corrected evidence",
        )
        impairment.refresh_from_db()
        self.assertEqual(impairment.status, "reversed")
        self.assertEqual(reversal.reversal_of, impairment)

    def test_transfer_is_prospective_and_disposal_stops_depreciation(self):
        asset, book = self._capitalized_asset()
        target_project = Project.objects.create(
            organization=self.organization, code="EQ-PROJ-2", name="Target Project"
        )
        target_site = ProjectSite.objects.create(
            organization=self.organization,
            project=target_project,
            code="TARGET",
            name="Target Site",
        )
        transfer = prepare_asset_transaction(
            organization=self.organization,
            actor=self.owner,
            asset=asset,
            transaction_type=AssetTransactionType.TRANSFER,
            occurred_on=date(2026, 2, 1),
            amount=Decimal(0),
            occurrence_key="TRANSFER-1",
            reason="Reviewed destination change",
            target_project=target_project,
            target_site=target_site,
        )
        finalize_asset_transaction(
            organization=self.organization,
            actor=self.reviewer,
            transaction_record=transfer,
        )
        asset.refresh_from_db()
        self.assertEqual(asset.project, target_project)
        self.assertEqual(asset.site, target_site)
        reverse_asset_transaction(
            organization=self.organization,
            actor=self.approver,
            transaction_record=transfer,
            occurrence_key="TRANSFER-1-REV",
            reason="Reviewed transfer correction",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.project, self.project)
        self.assertEqual(asset.site, self.site)

        disposal = prepare_asset_transaction(
            organization=self.organization,
            actor=self.owner,
            asset=asset,
            transaction_type=AssetTransactionType.DISPOSAL,
            occurred_on=date(2026, 2, 15),
            amount=Decimal(0),
            occurrence_key="DISPOSAL-1",
            reason="Reviewed retirement evidence",
        )
        finalize_asset_transaction(
            organization=self.organization,
            actor=self.reviewer,
            transaction_record=disposal,
        )
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY26",
            name="FY 2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=2,
            name="February",
            starts_on=date(2026, 2, 1),
            ends_on=date(2026, 2, 28),
        )
        run = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=period,
            occurrence_key="DEP-DISPOSED",
        )
        self.assertFalse(run.lines.exists())
        reverse_asset_transaction(
            organization=self.organization,
            actor=self.approver,
            transaction_record=disposal,
            occurrence_key="DISPOSAL-1-REV",
            reason="Reviewed disposal correction",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        march = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=3,
            name="March",
            starts_on=date(2026, 3, 1),
            ends_on=date(2026, 3, 31),
        )
        resumed = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=march,
            occurrence_key="DEP-DISPOSAL-REVERSED",
        )
        self.assertTrue(resumed.lines.exists())
        self.assertFalse(JournalEntry.objects.exists())

    def test_depreciation_assigns_rounding_residual_in_final_life_period(self):
        asset, book = self._capitalized_asset(
            useful_life_months=3,
            capitalization_basis=Decimal(100),
        )
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY-ROUND",
            name="Rounding year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        amounts = []
        for number, starts_on, ends_on in (
            (1, date(2026, 1, 1), date(2026, 1, 31)),
            (2, date(2026, 2, 1), date(2026, 2, 28)),
            (3, date(2026, 3, 1), date(2026, 3, 31)),
        ):
            period = FiscalPeriod.objects.create(
                organization=self.organization,
                fiscal_year=year,
                number=number,
                name=f"Period {number}",
                starts_on=starts_on,
                ends_on=ends_on,
            )
            run = preview_depreciation(
                organization=self.organization,
                actor=self.owner,
                book_policy=book,
                fiscal_period=period,
                occurrence_key=f"DEP-ROUND-{number}",
            )
            amounts.append(run.lines.get(asset=asset).depreciation_amount)
            finalize_depreciation(
                organization=self.organization, actor=self.reviewer, run=run
            )

        self.assertEqual(amounts, [Decimal(33), Decimal(33), Decimal(34)])
        self.assertEqual(sum(amounts), asset.capitalization_basis)
        self.assertEqual(run.lines.get(asset=asset).carrying_value_after, Decimal(0))

    def test_depreciation_rejects_backdated_period_after_later_finalization(self):
        _asset, book = self._capitalized_asset()
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY-SEQUENCE",
            name="Sequence year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        january = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        february = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=2,
            name="February",
            starts_on=date(2026, 2, 1),
            ends_on=date(2026, 2, 28),
        )
        later = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=february,
            occurrence_key="DEP-SEQUENCE-2",
        )
        finalize_depreciation(
            organization=self.organization, actor=self.reviewer, run=later
        )
        with self.assertRaises(ValueError):
            preview_depreciation(
                organization=self.organization,
                actor=self.owner,
                book_policy=book,
                fiscal_period=january,
                occurrence_key="DEP-SEQUENCE-1",
            )

    def test_future_impairment_is_not_applied_to_prior_period(self):
        asset, book = self._capitalized_asset()
        impairment = prepare_asset_transaction(
            organization=self.organization,
            actor=self.owner,
            asset=asset,
            transaction_type=AssetTransactionType.IMPAIRMENT,
            occurred_on=date(2026, 2, 1),
            amount=Decimal(500),
            occurrence_key="IMP-FUTURE",
            reason="Future impairment evidence",
        )
        finalize_asset_transaction(
            organization=self.organization,
            actor=self.reviewer,
            transaction_record=impairment,
        )
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY-CUTOFF",
            name="Cutoff year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        january = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=january,
            occurrence_key="DEP-CUTOFF-1",
        )
        line = run.lines.get(asset=asset)
        self.assertEqual(line.depreciation_amount, Decimal(1000))
        self.assertEqual(line.carrying_value_after, Decimal(9000))

    def test_depreciation_does_not_start_before_capitalization_date(self):
        _asset, book = self._capitalized_asset(
            ready_for_use_date=date(2026, 2, 15),
            useful_life_months=1,
            capitalization_basis=Decimal(100),
        )
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="FY-READY",
            name="Ready-for-use year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        january = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="January",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        run = preview_depreciation(
            organization=self.organization,
            actor=self.owner,
            book_policy=book,
            fiscal_period=january,
            occurrence_key="DEP-READY-JAN",
        )
        self.assertFalse(run.lines.exists())

    def test_cross_tenant_source_and_asset_access_fail_closed(self):
        asset, _book = self._capitalized_asset()
        with self.assertRaises(PermissionDenied):
            prepare_asset(
                organization=self.other_organization,
                actor=self.other_owner,
                asset_number="CROSS",
                name="Cross",
                asset_class=asset.asset_class,
                book_policy=asset.book_policy,
                ready_for_use_date=date(2026, 1, 1),
                useful_life_months=12,
                residual_value=Decimal(0),
                capitalization_basis=Decimal(1),
                evidence_reference="X",
            )

    def test_fixed_asset_workbench_is_tenant_permission_scoped(self):
        self.client.force_login(self.viewer)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get("/fixed-assets/")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get("/fixed-assets/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ثبت دفتر کل در حوزهٔ حسابداری")
