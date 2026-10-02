from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import MembershipRole, MembershipStatus
from apps.procurement.comparison_services import (
    finalize_comparison,
    finalize_sourcing_award,
    prepare_sourcing_award,
)
from apps.procurement.models import (
    PurchaseOrderChangeDecision,
    PurchaseOrderVersion,
    ServiceAcceptanceStatus,
    SourcingAwardOutcome,
)
from apps.procurement.services import (
    add_goods_receipt_item,
    create_goods_receipt,
    create_purchase_order_from_award,
    post_goods_receipt,
)
from apps.procurement.source_to_pay_services import (
    accept_service,
    add_service_acceptance_item,
    create_service_acceptance,
    decide_purchase_order_change,
    request_purchase_order_change,
)
from apps.procurement.test_p5_s11_comparison_award import P5S11FixtureMixin
from apps.procurement.tests import ProcurementFixtureMixin
from apps.subledgers.models import (
    InvoiceMatchStatus,
    MatchDiscrepancyCode,
    SupplierInvoiceLineKind,
    SupplierInvoiceStatus,
)
from apps.subledgers.services import (
    approve_match_tolerance_policy,
    decide_supplier_invoice,
    prepare_match_tolerance_policy,
    prepare_supplier_invoice,
    run_supplier_invoice_match,
    submit_supplier_invoice,
)


class P5S12S17SourceToPayTests(ProcurementFixtureMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.approver = User.objects.create_user(username="p5-s12-s17-approver")
        self.organization.memberships.create(
            user=self.approver,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )

    def _receipt(self, *, order, item, quantity: Decimal):
        receipt = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="gr-p5-1",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
            purchase_order_item=item,
            quantity=quantity,
        )
        return post_goods_receipt(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
        )

    def _approved_policy(self, *, quantity_bps: int = 0, price_bps: int = 0):
        policy = prepare_match_tolerance_policy(
            organization=self.organization,
            actor=self.owner,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            quantity_tolerance_bps=quantity_bps,
            unit_price_tolerance_bps=price_bps,
            reason="Tenant-approved matching policy",
        )
        return approve_match_tolerance_policy(
            organization=self.organization,
            actor=self.approver,
            policy=policy,
        )

    def _approved_invoice(
        self,
        *,
        po_line,
        quantity: Decimal,
        unit_price: Decimal,
        tax_amount: Decimal = Decimal(0),
        key: str = "invoice-1",
    ):
        version = prepare_supplier_invoice(
            organization=self.organization,
            actor=self.owner,
            supplier=self.supplier,
            project=self.project,
            invoice_number=key,
            invoice_date=date(2026, 9, 10),
            due_date=date(2026, 10, 10),
            lines=[
                {
                    "kind": SupplierInvoiceLineKind.GOODS,
                    "purchase_order_version_line": po_line,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "tax_amount": tax_amount,
                }
            ],
            idempotency_key=key,
        )
        submit_supplier_invoice(
            organization=self.organization,
            actor=self.owner,
            invoice_version=version,
        )
        return decide_supplier_invoice(
            organization=self.organization,
            actor=self.approver,
            invoice_version=version,
            approve=True,
            reason="AP evidence accepted",
        )

    def test_issue_versions_order_and_independent_change_supersedes(self) -> None:
        order, _ = self.create_issued_order()
        order.refresh_from_db()
        self.assertEqual(order.current_version.version_number, 1)
        line = order.current_version.lines.get()
        change = request_purchase_order_change(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            line_changes={str(line.pk): (Decimal("8.0000"), Decimal("13.00"))},
            reason="Scope reduced",
            evidence="Approved field instruction",
            idempotency_key="po-change-1",
        )
        with self.assertRaises(PermissionDenied):
            decide_purchase_order_change(
                organization=self.organization,
                actor=self.owner,
                change_request=change,
                approve=True,
                reason="Self approval denied",
            )
        decision = decide_purchase_order_change(
            organization=self.organization,
            actor=self.approver,
            change_request=change,
            approve=True,
            reason="Independently approved",
        )
        self.assertEqual(decision.decision, PurchaseOrderChangeDecision.APPROVED)
        order.refresh_from_db()
        self.assertEqual(order.current_version.version_number, 2)
        self.assertEqual(order.current_version.lines.get().quantity, Decimal("8.0000"))
        self.assertEqual(
            PurchaseOrderVersion.objects.filter(purchase_order=order).count(), 2
        )
        with self.assertRaises(ValidationError):
            order.current_version.save()

    def test_service_acceptance_is_version_pinned_and_conserved(self) -> None:
        order, _ = self.create_issued_order(quantity=Decimal("5.0000"))
        order.refresh_from_db()
        line = order.current_version.lines.get()
        acceptance = create_service_acceptance(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            acceptance_number="sa-1",
            accepted_on=date(2026, 9, 10),
        )
        add_service_acceptance_item(
            organization=self.organization,
            actor=self.member,
            acceptance=acceptance,
            purchase_order_version_line=line,
            quantity=Decimal("5.0000"),
            evidence="Signed service sheet",
        )
        accept_service(
            organization=self.organization,
            actor=self.member,
            acceptance=acceptance,
        )
        acceptance.refresh_from_db()
        self.assertEqual(acceptance.status, ServiceAcceptanceStatus.ACCEPTED)
        second = create_service_acceptance(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            acceptance_number="sa-2",
            accepted_on=date(2026, 9, 11),
        )
        add_service_acceptance_item(
            organization=self.organization,
            actor=self.member,
            acceptance=second,
            purchase_order_version_line=line,
            quantity=Decimal("0.1000"),
            evidence="Excess sheet",
        )
        with self.assertRaises(ValidationError):
            accept_service(
                organization=self.organization,
                actor=self.member,
                acceptance=second,
            )

    def test_invoice_approval_and_exact_three_way_match_are_independent(self) -> None:
        order, item = self.create_issued_order(quantity=Decimal("5.0000"))
        order.refresh_from_db()
        self._receipt(order=order, item=item, quantity=Decimal("5.0000"))
        policy = self._approved_policy()
        self.assertTrue(policy.is_approved)
        invoice = self._approved_invoice(
            po_line=order.current_version.lines.get(),
            quantity=Decimal("5.0000"),
            unit_price=Decimal("12.34"),
        )
        self.assertEqual(invoice.status, SupplierInvoiceStatus.APPROVED)
        match = run_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            invoice_version=invoice,
            idempotency_key="match-1",
        )
        self.assertEqual(match.status, InvoiceMatchStatus.MATCHED)
        self.assertEqual(match.lines.get().accepted_quantity, Decimal("5.0000"))
        self.assertFalse(hasattr(invoice, "recognition_journal"))

    def test_missing_policy_and_cross_tenant_invoice_fail_closed(self) -> None:
        order, _ = self.create_issued_order()
        order.refresh_from_db()
        line = order.current_version.lines.get()
        with self.assertRaises(PermissionDenied):
            prepare_supplier_invoice(
                organization=self.other_organization,
                actor=self.outsider,
                supplier=self.supplier,
                project=self.project,
                invoice_number="BAD-TENANT",
                invoice_date=date(2026, 9, 10),
                due_date=None,
                lines=[
                    {
                        "kind": SupplierInvoiceLineKind.GOODS,
                        "purchase_order_version_line": line,
                        "quantity": Decimal("1.0000"),
                        "unit_price": Decimal("12.34"),
                    }
                ],
                idempotency_key="bad-tenant",
            )
        invoice = self._approved_invoice(
            po_line=line,
            quantity=Decimal("1.0000"),
            unit_price=Decimal("12.34"),
        )
        with self.assertRaises(ValidationError):
            run_supplier_invoice_match(
                organization=self.organization,
                actor=self.owner,
                invoice_version=invoice,
                idempotency_key="no-policy",
            )

    def test_tolerance_classifies_but_charges_and_overbilling_block(self) -> None:
        order, item = self.create_issued_order(quantity=Decimal("10.0000"))
        order.refresh_from_db()
        self._receipt(order=order, item=item, quantity=Decimal("10.0000"))
        self._approved_policy(price_bps=100)
        line = order.current_version.lines.get()
        invoice = self._approved_invoice(
            po_line=line,
            quantity=Decimal("10.0000"),
            unit_price=Decimal("12.40"),
            tax_amount=Decimal("1.00"),
        )
        match = run_supplier_invoice_match(
            organization=self.organization,
            actor=self.owner,
            invoice_version=invoice,
            idempotency_key="charges-incomplete",
        )
        self.assertEqual(match.status, InvoiceMatchStatus.INCOMPLETE)
        self.assertTrue(
            match.lines.get()
            .discrepancies.filter(
                code=MatchDiscrepancyCode.UNSUPPORTED_CHARGES, blocking=True
            )
            .exists()
        )


class P5S12AwardConsumptionTests(P5S11FixtureMixin, TestCase):
    def test_final_award_requires_explicit_conserved_po_consumption(self) -> None:
        comparison, _ = self._evaluated_comparison()
        finalized = finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="comparison complete",
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
            reason="selected supplier",
            evidence="award evidence",
            idempotency_key="s12-award",
        )
        award = finalize_sourcing_award(
            organization=self.organization,
            actor=self.approver,
            preparation=preparation,
        )
        self.assertFalse(self.organization.purchase_orders.exists())
        allocation = award.allocations.get()
        order = create_purchase_order_from_award(
            organization=self.organization,
            actor=self.owner,
            award=award,
            allocation_ids=[str(allocation.pk)],
            order_number="PO-S12-AWARD",
            order_date=date(2026, 10, 2),
        )
        item = order.items.get()
        self.assertEqual(order.source_award_id, award.pk)
        self.assertEqual(item.source_award_allocation_id, allocation.pk)
        self.assertEqual(item.quantity, allocation.quantity)
        with self.assertRaises(ValueError):
            create_purchase_order_from_award(
                organization=self.organization,
                actor=self.owner,
                award=award,
                allocation_ids=[str(allocation.pk)],
                order_number="PO-S12-DUPLICATE",
                order_date=date(2026, 10, 2),
            )
