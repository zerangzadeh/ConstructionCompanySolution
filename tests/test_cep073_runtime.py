"""Bounded, synthetic current-build Reporting source/refresh runtime scenario."""

from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounting.models import JournalEntry
from apps.inventory.models import (
    InventoryValuationPool,
    StockTransaction,
    StockTransactionType,
)
from apps.inventory.p8_services import finalize_valuation
from apps.inventory.test_p8_s12_s17 import InventoryValuationAcceptanceTests
from apps.materials.models import Material
from apps.organizations.models import (
    BusinessPermission,
    BusinessPermissionCode,
    MembershipRoleAssignment,
    OrganizationRole,
)
from apps.reporting.services import refresh_metric


class CurrentReportingRuntimeTests(InventoryValuationAcceptanceTests):
    def test_populated_refresh_queries_reconcile_without_source_writeback(self):
        membership = self.organization.memberships.get(user=self.owner)
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="cep073-reporting",
            name="Synthetic reporting",
        )
        role.permissions.set(
            BusinessPermission.objects.filter(
                code__in=(
                    BusinessPermissionCode.REPORTING_METRIC_REFRESH_RUN,
                    BusinessPermissionCode.REPORTING_METRIC_RESULT_VIEW,
                    BusinessPermissionCode.REPORTING_PORTFOLIO_VIEW,
                    BusinessPermissionCode.INVENTORY_VALUATION_VIEW,
                )
            )
        )
        receipt = self.create_and_post(
            number="CEP073-SYNTHETIC-IN",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(10),
            destination=self.central,
            actor=self.owner,
        )
        finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=receipt,
            source_reference="CEP073-SYNTHETIC-ONLY",
            source_version="1",
            unit_cost=Decimal(7),
            idempotency_key="CEP073-SYNTHETIC-IN",
        )
        template = InventoryValuationPool.objects.get(organization=self.organization)
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="CEP073 explicit test-only permission; existing organization scope",
        )
        query_counts = []
        for size in (1, 17):
            if size > 1:
                for number in range(1, size):
                    material = Material.objects.create(
                        organization=self.organization,
                        code=f"CEP073-{number}",
                        name=f"Synthetic {number}",
                        unit_of_measure=self.unit,
                    )
                    InventoryValuationPool.objects.create(
                        organization=self.organization,
                        material=material,
                        quantity=template.quantity,
                        value_amount=template.value_amount,
                        average_cost=template.average_cost,
                        currency=template.currency,
                        monetary_precision_version=template.monetary_precision_version,
                        rounding_policy_version=template.rounding_policy_version,
                    )
                InventoryValuationPool.objects.create(
                    organization=self.other_organization,
                    material=self.other_material,
                    quantity=Decimal(999),
                    value_amount=Decimal(999),
                    average_cost=Decimal(1),
                    currency=template.currency,
                    monetary_precision_version=template.monetary_precision_version,
                    rounding_policy_version=template.rounding_policy_version,
                )
            sources = (InventoryValuationPool, StockTransaction, JournalEntry)
            before = {
                m._meta.label: list(m.objects.order_by("pk").values()) for m in sources
            }
            key = f"cep073-refresh-{size}"
            with CaptureQueriesContext(connection) as queries:
                result = refresh_metric(
                    organization=self.organization,
                    actor=self.owner,
                    metric_code="inventory_quantity_value",
                    idempotency_key=key,
                )
            source_queries = [
                q
                for q in queries
                if 'FROM "inventory_inventoryvaluationpool"' in q["sql"]
            ]
            query_counts.append(len(source_queries))
            self.assertEqual(result.value["quantity"], f"{size * 10}.0000")
            self.assertEqual(result.value["value_amount"], f"{size * 70}.0000")
            self.assertEqual(result.coverage["source_count"], size)
            self.assertEqual(
                result.source_manifest["ids"], sorted(result.source_manifest["ids"])
            )
            self.assertEqual(
                set(result.source_manifest["ids"]),
                set(
                    map(
                        str,
                        InventoryValuationPool.objects.filter(
                            organization=self.organization
                        ).values_list("pk", flat=True),
                    )
                ),
            )
            repeated = refresh_metric(
                organization=self.organization,
                actor=self.owner,
                metric_code="inventory_quantity_value",
                idempotency_key=key,
            )
            self.assertEqual(repeated.pk, result.pk)
            self.assertEqual(
                before,
                {
                    m._meta.label: list(m.objects.order_by("pk").values())
                    for m in sources
                },
            )
        self.assertEqual(query_counts, [3, 3])
