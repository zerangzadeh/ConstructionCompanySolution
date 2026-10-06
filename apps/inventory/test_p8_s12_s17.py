from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.inventory.models import (
    InventoryValuationException,
    InventoryValuationPool,
    StockTransactionType,
    TransferExceptionCode,
)
from apps.inventory.p8_services import (
    TransferLineSpec,
    accept_inventory_transfer,
    create_inventory_transfer,
    dispatch_inventory_transfer,
    finalize_transfer_valuation,
    finalize_valuation,
    mark_transfer_in_transit,
    record_missing_cost_exception,
    reverse_valuation,
    supply_cost_envelope,
    valuation_reconciliation,
)
from apps.inventory.services import reverse_stock_transaction
from apps.inventory.tests import InventoryFixtureMixin
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    OrganizationSettings,
    PlatformPolicy,
    PlatformPolicyVersion,
    PolicySourceBasis,
    PolicyVersionStatus,
    TenantPolicySelection,
    TenantPolicySelectionStatus,
)
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    get_platform_policy_spec,
    initial_accounting_policy_parameters,
)
from apps.organizations.services import set_active_organization
from apps.projects.models import ProjectCostFact


class InventoryValuationAcceptanceTests(InventoryFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        OrganizationSettings.objects.create(
            organization=self.organization, currency="IRR"
        )
        now = timezone.now()
        membership = self.organization.memberships.get(user=self.owner)
        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            spec = get_platform_policy_spec(code)
            policy = PlatformPolicy.objects.create(
                code=code,
                name=spec.name,
                category=spec.category,
                sensitivity=spec.sensitivity,
                tenant_selectable=spec.tenant_selectable,
                requires_source_provenance=False,
                created_by=self.owner,
                updated_by=self.owner,
            )
            version = PlatformPolicyVersion.objects.create(
                policy=policy,
                version=1,
                parameters=initial_accounting_policy_parameters(code),
                effective_from=timezone.localdate(),
                status=PolicyVersionStatus.PUBLISHED,
                source_basis=PolicySourceBasis.PRODUCT_DEFINED,
                created_by=self.owner,
                published_by=self.owner,
                published_at=now,
                reason="P8 assurance monetary policy",
            )
            TenantPolicySelection.objects.create(
                organization=self.organization,
                policy=policy,
                policy_version=version,
                status=TenantPolicySelectionStatus.ACTIVE,
                approved_by=membership,
                approved_at=now,
                applied_by=membership,
                applied_at=now,
                reason="P8 assurance monetary policy",
            )
        self.transfer_reviewer = User.objects.create_user(
            username="inventory-transfer-reviewer"
        )
        self.organization.memberships.create(
            user=self.transfer_reviewer,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def test_reconciliation_detects_unvalued_posted_movement_and_is_read_only(self):
        movement = self.create_and_post(
            number="P8-VAL-UNVALUED",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(2),
            destination=self.central,
        )
        before = self.organization.stock_transactions.count()
        report = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertIn(str(movement.pk), report["movements_without_valuation"])
        self.assertEqual(before, self.organization.stock_transactions.count())

    def test_missing_cost_exception_is_persistent_and_visible(self):
        movement = self.create_and_post(
            number="P8-VAL-EXCEPTION",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(2),
            destination=self.central,
        )
        exception = record_missing_cost_exception(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=movement,
            reason="missing authorized source",
        )
        report = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertIn(str(exception.pk), report["unresolved_exceptions"])
        self.assertTrue(
            InventoryValuationException.objects.filter(pk=exception.pk).exists()
        )

    def test_rtl_workbench_is_reachable(self):
        self.client.force_login(self.owner)
        set_active_organization(self.client.session, self.organization)
        response = self.client.get(reverse("inventory:valuation_workbench"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ارزش میانگین موزون متحرک")

    def test_wac_issue_reversal_restores_quantity_value_and_lineage(self):
        receipt = self.create_and_post(
            number="P8-WAC-IN",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(10),
            destination=self.central,
            actor=self.owner,
        )
        receipt_value = finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=receipt,
            source_reference="OPENING-APPROVED",
            source_version="1",
            unit_cost=Decimal(7),
            idempotency_key="P8-WAC-IN",
        )
        issue = self.create_and_post(
            number="P8-WAC-OUT",
            transaction_type=StockTransactionType.ADJUSTMENT_OUT,
            quantity=Decimal(4),
            source=self.central,
            actor=self.owner,
        )
        issue_value = finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            source_reference="WAC-POOL",
            source_version="1",
            unit_cost=Decimal(0),
            idempotency_key="P8-WAC-OUT",
        )
        reversal = reverse_stock_transaction(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=issue,
            reversal_number="P8-WAC-OUT-REV",
            reason="assurance correction",
        )
        reversal_value = reverse_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=reversal,
            idempotency_key="P8-WAC-OUT-REV",
        )

        pool = InventoryValuationPool.objects.get(
            organization=self.organization, material=self.material
        )
        self.assertEqual(
            (receipt_value.value_amount, issue_value.value_amount),
            (Decimal(70), Decimal(28)),
        )
        self.assertEqual((pool.quantity, pool.value_amount), (Decimal(10), Decimal(70)))
        self.assertEqual(reversal_value.reversal_of, issue_value)
        self.assertEqual(reversal_value.value_amount, issue_value.value_amount)

    def test_internal_transfer_carries_wac_without_pool_gain_or_loss(self):
        opening = self.create_and_post(
            number="P8-TRANSFER-OPEN",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(10),
            destination=self.central,
            actor=self.owner,
        )
        finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=opening,
            source_reference="OPENING-APPROVED",
            source_version="1",
            unit_cost=Decimal(10),
            idempotency_key="P8-TRANSFER-OPEN",
        )
        transfer = create_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            transfer_number="P8-VALUED-MOVE",
            source_warehouse=self.central,
            destination_warehouse=self.site,
            lines=[TransferLineSpec(self.material, Decimal(4))],
        )
        dispatch_inventory_transfer(
            organization=self.organization,
            actor=self.owner,
            inventory_transfer=transfer,
        )
        mark_transfer_in_transit(
            organization=self.organization,
            actor=self.owner,
            inventory_transfer=transfer,
        )
        accept_inventory_transfer(
            organization=self.organization,
            actor=self.transfer_reviewer,
            inventory_transfer=transfer,
            outcomes={
                transfer.lines.get().pk: (
                    Decimal(4),
                    TransferExceptionCode.NONE,
                    "",
                )
            },
        )
        with self.assertRaises(ValueError):
            finalize_valuation(
                organization=self.organization,
                actor=self.owner,
                stock_transaction=transfer.lines.get().dispatch_transaction,
                source_reference="WRONG-TRANSFER-PATH",
                source_version="1",
                unit_cost=Decimal(0),
                idempotency_key="WRONG-TRANSFER-PATH",
            )
        dispatch_value, receipt_value = finalize_transfer_valuation(
            organization=self.organization,
            actor=self.owner,
            line=transfer.lines.get(),
            idempotency_key="P8-VALUED-MOVE",
        )

        pool = InventoryValuationPool.objects.get(
            organization=self.organization, material=self.material
        )
        self.assertEqual(
            (pool.quantity, pool.value_amount), (Decimal(10), Decimal(100))
        )
        self.assertEqual(dispatch_value.value_amount, Decimal(40))
        self.assertEqual(receipt_value.value_amount, dispatch_value.value_amount)
        report = valuation_reconciliation(
            organization=self.organization, actor=self.owner
        )
        self.assertEqual(report["transfer_mismatches"], [])
        self.assertEqual(report["pool_mismatches"], [])
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(ProjectCostFact.objects.exists())

    def test_one_proposal_per_source_and_consumer_prevents_double_count(self):
        movement = self.create_and_post(
            number="P8-DOUBLE-COUNT",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(2),
            destination=self.central,
            actor=self.owner,
        )
        event = finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=movement,
            source_reference="APPROVED-SOURCE",
            source_version="1",
            unit_cost=Decimal(5),
            idempotency_key="P8-DOUBLE-COUNT",
        )
        supply_cost_envelope(
            organization=self.organization,
            actor=self.owner,
            valuation_event=event,
            consumer="accounting",
            idempotency_key="P8-ACCOUNTING-1",
        )
        with self.assertRaises(ValueError):
            supply_cost_envelope(
                organization=self.organization,
                actor=self.owner,
                valuation_event=event,
                consumer="accounting",
                idempotency_key="P8-ACCOUNTING-2",
            )
