"""Receipt journey, pinned quantities and independent Inventory authority."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.inventory.models import StockTransaction
from apps.inventory.services import get_stock_balance
from apps.inventory.test_cep034_receipt_contract import ReceiptContractFixture
from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement import models as m
from apps.procurement import services as s
from apps.procurement.receipt_ui import quantity_rows
from apps.projects.models import Project
from core.jalali import format_jalali


class ReceiptJourneyFixture(ReceiptContractFixture):
    def setUp(self):
        super().setUp()
        for obj, field, value in (
            (self.project, "name", "پروژه سازه نمونه"),
            (self.supplier, "display_name", "تأمین مصالح پارس"),
            (self.material, "name", "سیمان پرتلند"),
            (self.unit, "name", "عدد"),
        ):
            setattr(obj, field, value)
            obj.save(update_fields=[field])
        self.received_at = timezone.now().replace(second=0, microsecond=0)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(
            session,
            self.other_organization if actor == self.outsider else self.organization,
        )
        session.save()

    def make_order(self, number="PO-GRN", quantity="10", project=None, issued=True):
        order = s.create_purchase_order(
            organization=self.organization,
            actor=self.owner,
            project=project or self.project,
            supplier=self.supplier,
            order_number=number,
            order_date=date(2026, 11, 2),
        )
        item = s.add_purchase_order_item(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            material=self.material,
            quantity=Decimal(quantity),
            unit_price=Decimal("12.50"),
        )
        if issued:
            order = s.issue_purchase_order(
                organization=self.organization, actor=self.owner, purchase_order=order
            )
        return order, item

    def create_url(self, order=None):
        return reverse("procurement:receipt_create") + (
            f"?purchase_order={order.pk}" if order else ""
        )

    def payload(self, order, number="GRN-1", **changes):
        return {
            "purchase_order": str(order.pk),
            "receipt_number": number,
            "received_at": format_jalali(
                timezone.localtime(self.received_at), include_time=True
            ),
            "notes": "یادداشت دریافت",
            **changes,
        }

    def create_receipt(self, order, number="GRN-1"):
        self.login(self.owner)
        response = self.client.post(self.create_url(order), self.payload(order, number))
        self.assertEqual(response.status_code, 302, response.content[:1200])
        return m.GoodsReceipt.objects.get(receipt_number=number)

    def detail_url(self, receipt):
        return reverse("procurement:receipt_detail", args=[receipt.pk])

    def add(self, receipt, item, quantity, **changes):
        return self.client.post(
            reverse("procurement:receipt_item_add", args=[receipt.pk]),
            {
                "purchase_order_item": str(item.pk),
                "quantity": quantity,
                "notes": "تحویل سالم",
                **changes,
            },
        )

    def post(self, receipt):
        return self.client.post(reverse("procurement:receipt_post", args=[receipt.pk]))

    def financial_snapshot(self):
        from apps.accounting.models import JournalEntry
        from apps.projects.models import ProjectCostFact
        from apps.subledgers.models import Obligation, SupplierInvoice
        from apps.treasury.models import TreasuryMovement

        return {
            model._meta.label: model.objects.filter(
                organization=self.organization
            ).count()
            for model in (
                StockTransaction,
                SupplierInvoice,
                Obligation,
                JournalEntry,
                TreasuryMovement,
                ProjectCostFact,
            )
        } | {
            "balance": get_stock_balance(
                user=self.owner,
                organization=self.organization,
                warehouse=self.site,
                material=self.material,
            )
        }


class ReceiptJourneyTests(ReceiptJourneyFixture, TestCase):
    def test_context_general_selector_business_labels_and_ineligible_order(self):
        order, _item = self.make_order()
        draft, _ = self.make_order("PO-DRAFT", issued=False)
        self.login(self.owner)
        response = self.client.get(self.create_url(order))
        self.assertContains(response, self.supplier.display_name)
        self.assertContains(response, self.project.name)
        self.assertTrue(response.context["form"]["purchase_order"].is_hidden)
        self.assertEqual(response.context["quantity_rows"][0]["remaining"], Decimal(10))
        general = self.client.get(self.create_url())
        self.assertEqual(
            list(general.context["form"].fields["purchase_order"].queryset), [order]
        )
        lookup = self.client.get(
            reverse("procurement:receipt_choices", args=["create", "purchase_order"]),
            {"q": "پارس"},
        )
        self.assertEqual(len(lookup.json()["results"]), 1)
        self.assertIn("PO-GRN", lookup.json()["results"][0]["label"])
        self.assertContains(
            self.client.get(self.create_url(draft)), "فقط برای سفارش صادرشده"
        )
        self.assertEqual(
            self.client.post(self.create_url(draft), self.payload(draft)).status_code,
            400,
        )
        self.assertFalse(m.GoodsReceipt.objects.exists())

    def test_partial_second_full_receipt_pinning_and_no_financial_effects(self):
        order, item = self.make_order()
        before = self.financial_snapshot()
        first = self.create_receipt(order)
        self.assertEqual(first.purchase_order_version_id, order.current_version_id)
        self.assertEqual(self.add(first, item, "4").status_code, 302)
        self.assertEqual(self.post(first).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "issued")
        self.assertEqual(quantity_rows(order)[0]["remaining"], Decimal(6))
        second = self.create_receipt(order, "GRN-2")
        detail = self.client.get(self.detail_url(second))
        self.assertEqual(detail.context["quantity_rows"][0]["previous"], Decimal(4))
        self.assertEqual(self.add(second, item, "6").status_code, 302)
        self.assertEqual(self.post(second).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")
        self.assertEqual(quantity_rows(order)[0]["remaining"], Decimal(0))
        second.refresh_from_db()
        self.assertEqual(second.status, "posted")
        self.assertEqual(self.financial_snapshot(), before)
        response = self.client.get(self.detail_url(second))
        self.assertFalse(response.context["can_add_item"])
        self.assertFalse(response.context["can_post"])
        self.assertEqual(len(response.context["receipt_history"]), 2)
        self.assertContains(response, "فقط خواندنی")
        self.assertContains(
            self.client.get(self.create_url(order)), "فقط برای سفارش صادرشده"
        )

    def test_excess_wrong_order_project_tenant_duplicate_and_forged_context(self):
        order, item = self.make_order()
        other_order, wrong = self.make_order("PO-WRONG")
        other_project = Project.objects.create(
            organization=self.organization, code="LOCAL", name="پروژه دیگر"
        )
        _, wrong_project = self.make_order("PO-PROJECT", project=other_project)
        receipt = self.create_receipt(order)
        for candidate in (wrong, wrong_project):
            self.assertEqual(self.add(receipt, candidate, "1").status_code, 400)
        self.assertEqual(self.add(receipt, item, "11").status_code, 400)
        self.assertEqual(
            self.add(receipt, item, "1", project=str(other_project.pk)).status_code, 400
        )
        self.assertEqual(self.add(receipt, item, "0").status_code, 400)
        self.assertEqual(self.add(receipt, item, "1.00001").status_code, 400)
        self.assertFalse(receipt.items.exists())
        self.assertEqual(self.add(receipt, item, "4").status_code, 302)
        self.assertEqual(self.add(receipt, item, "4").status_code, 400)
        self.assertEqual(receipt.items.count(), 1)
        self.assertEqual(
            self.client.post(
                self.create_url(order), self.payload(other_order, "FORGED")
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.create_url(order),
                self.payload(order, "FORGED", supplier=str(self.supplier.pk)),
            ).status_code,
            400,
        )
        self.assertFalse(
            m.GoodsReceipt.objects.filter(receipt_number="FORGED").exists()
        )
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.detail_url(receipt)).status_code, 404)
        self.assertEqual(self.client.get(self.create_url(order)).status_code, 404)
        self.assertEqual(self.add(receipt, item, "1").status_code, 404)

    def test_post_rechecks_live_remaining_and_posted_evidence_is_immutable(self):
        order, item = self.make_order()
        first = self.create_receipt(order)
        stale = self.create_receipt(order, "GRN-STALE")
        self.assertEqual(self.add(first, item, "6").status_code, 302)
        self.assertEqual(self.add(stale, item, "6").status_code, 302)
        self.assertEqual(self.post(first).status_code, 302)
        self.assertEqual(self.post(stale).status_code, 400)
        stale.refresh_from_db()
        self.assertEqual(stale.status, "draft")
        self.assertEqual(self.add(first, item, "1").status_code, 400)
        first.refresh_from_db()
        first.notes = "changed"
        with self.assertRaises(ValidationError):
            first.save()
        line = first.items.get()
        line.quantity = Decimal(1)
        with self.assertRaises(ValidationError):
            line.save()

    def test_retry_safety_create_exact_mismatch_post_and_audit(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.assertEqual(
            self.client.post(self.create_url(order), self.payload(order)).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                self.create_url(order), self.payload(order, notes="different")
            ).status_code,
            400,
        )
        self.assertEqual(m.GoodsReceipt.objects.count(), 1)
        self.add(receipt, item, "10")
        self.assertEqual(self.post(receipt).status_code, 302)
        self.assertEqual(self.post(receipt).status_code, 400)
        self.assertEqual(
            self.client.post(self.create_url(order), self.payload(order)).status_code,
            302,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization, action=AuditAction.GOODS_RECEIPT_CREATED
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization, action=AuditAction.GOODS_RECEIPT_POSTED
            ).count(),
            1,
        )

    def test_void_reopens_completed_preserves_history_and_requires_reason(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, item, "10")
        self.post(receipt)
        url = reverse("procurement:receipt_void", args=[receipt.pk])
        self.assertEqual(self.client.post(url, {"reason": ""}).status_code, 400)
        self.assertEqual(
            self.client.post(url, {"reason": "اصلاح دریافت"}).status_code, 302
        )
        receipt.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(receipt.status, "void")
        self.assertEqual(order.status, "issued")
        self.assertEqual(receipt.items.get().quantity, Decimal(10))
        self.assertEqual(quantity_rows(order)[0]["remaining"], Decimal(10))
        self.assertContains(self.client.get(self.detail_url(receipt)), "اصلاح دریافت")
        self.assertEqual(self.client.post(url, {"reason": "again"}).status_code, 400)

    def test_inventory_handoff_qualified_nonmutating_and_void_dependency_denial(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, item, "10")
        self.post(receipt)
        before = self.financial_snapshot()
        response = self.client.get(self.detail_url(receipt))
        target = response.context["inventory_rows"][0]["url"]
        entry = self.client.get(target)
        self.assertEqual(entry.status_code, 200)
        self.assertEqual(
            entry.context["form"].initial["goods_receipt_item"], receipt.items.get().pk
        )
        self.assertEqual(entry.context["form"].initial["project"], self.project.pk)
        self.assertEqual(self.financial_snapshot(), before)
        stock = self.create_and_post(
            number="STOCK-EXPLICIT",
            transaction_type="receipt",
            quantity=Decimal(10),
            destination=self.site,
            project=self.project,
            goods_receipt_item=receipt.items.get(),
            actor=self.owner,
        )
        response = self.client.get(self.detail_url(receipt))
        self.assertTrue(response.context["void_blocked"])
        self.assertFalse(response.context["inventory_rows"])
        self.assertEqual(
            self.client.post(
                reverse("procurement:receipt_void", args=[receipt.pk]),
                {"reason": "مردود"},
            ).status_code,
            400,
        )
        stock.refresh_from_db()
        self.assertEqual(stock.status, "posted")
        self.assertEqual(self.client.get(target).status_code, 404)

    def test_permission_scope_status_csrf_and_selector_isolation(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.login(self.viewer)
        self.assertEqual(self.client.get(self.create_url()).status_code, 403)
        self.assertEqual(self.add(receipt, item, "1").status_code, 403)
        self.assertEqual(self.post(receipt).status_code, 403)
        self.login(self.owner)
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies
        self.assertEqual(
            client.post(
                self.create_url(order), self.payload(order, "CSRF")
            ).status_code,
            403,
        )
        member = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        other = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=other,
            reason="test",
        )
        self.assertEqual(self.client.get(self.detail_url(receipt)).status_code, 404)
        self.assertEqual(self.client.get(self.create_url(order)).status_code, 404)
        lookup = self.client.get(
            reverse("procurement:receipt_choices", args=["create", "purchase_order"])
        )
        self.assertEqual(lookup.json()["results"], [])

    def test_list_filters_sort_pagination_and_no_technical_labels(self):
        order, _ = self.make_order()
        for n in range(27):
            s.create_goods_receipt(
                organization=self.organization,
                actor=self.owner,
                purchase_order=order,
                receipt_number=f"GRN-{n:02}",
                received_at=self.received_at,
            )
        self.login(self.owner)
        response = self.client.get(
            reverse("procurement:receipt_list"),
            {
                "q": "GRN",
                "status": "draft",
                "project": self.project.pk,
                "sort": "number",
                "direction": "asc",
                "page": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_bar"]["result_count"], 27)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertGreaterEqual(len(response.context["filter_bar"]["chips"]), 3)
        self.assertNotContains(response, "object (")
        invalid = self.client.get(
            reverse("procurement:receipt_list"),
            {"project": self.other_project.pk, "sort": "organization__name"},
        )
        self.assertEqual(invalid.context["filter_bar"]["result_count"], 0)

    def test_decimal_remaining_and_suspended_tenant_mutation_denial(self):
        order, item = self.make_order(quantity="1.2345")
        receipt = self.create_receipt(order)
        self.assertEqual(self.add(receipt, item, "0.1234").status_code, 302)
        self.assertEqual(self.post(receipt).status_code, 302)
        self.assertEqual(quantity_rows(order)[0]["remaining"], Decimal("1.1111"))
        second = self.create_receipt(order, "GRN-DECIMAL")
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        for url, data in (
            (self.create_url(order), self.payload(order, "BLOCKED")),
            (
                reverse("procurement:receipt_item_add", args=[second.pk]),
                {"purchase_order_item": str(item.pk), "quantity": "1"},
            ),
            (reverse("procurement:receipt_post", args=[second.pk]), {}),
            (
                reverse("procurement:receipt_void", args=[receipt.pk]),
                {"reason": "مردود"},
            ),
        ):
            response = self.client.post(url, data)
            self.assertIn(response.status_code, (302, 400, 403))
            if response.status_code == 302:
                self.assertEqual(response.url, reverse("organizations:select"))
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "posted")
        self.assertFalse(second.items.exists())
        self.assertFalse(
            m.GoodsReceipt.objects.filter(receipt_number="BLOCKED").exists()
        )

    def test_inventory_entry_hidden_without_permission_or_compatible_warehouse(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, item, "4")
        self.post(receipt)
        self.login(self.viewer)
        self.assertFalse(
            self.client.get(self.detail_url(receipt)).context["inventory_rows"]
        )
        self.login(self.owner)
        self.site.is_active = False
        self.site.save(update_fields=["is_active"])
        self.central.is_active = False
        self.central.save(update_fields=["is_active"])
        self.assertFalse(
            self.client.get(self.detail_url(receipt)).context["inventory_rows"]
        )

    def test_foreign_tenant_line_is_rejected_without_source_leakage(self):
        order, _ = self.make_order()
        receipt = self.create_receipt(order)
        foreign = s.create_purchase_order(
            organization=self.other_organization,
            actor=self.outsider,
            project=self.other_project,
            supplier=self.other_supplier,
            order_number="FOREIGN",
            order_date=date(2026, 11, 2),
        )
        foreign_item = s.add_purchase_order_item(
            organization=self.other_organization,
            actor=self.outsider,
            purchase_order=foreign,
            material=self.other_material,
            quantity=Decimal(10),
            unit_price=Decimal(1),
        )
        response = self.add(receipt, foreign_item, "1")
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, self.other_material.name, status_code=400)
        self.assertFalse(receipt.items.exists())


class ReceiptDomainRegressionTests(ReceiptJourneyFixture, TestCase):
    from apps.procurement.tests import ProcurementModelTests, ProcurementServiceTests

    test_original_partial_full_receipt = (
        ProcurementServiceTests.test_receipts_complete_order_without_creating_inventory
    )
    test_original_excess_and_void = (
        ProcurementServiceTests.test_receipt_cannot_exceed_order_and_void_reopens_order
    )
    test_original_immutable_history = (
        ProcurementModelTests.test_issued_order_and_posted_receipt_details_are_immutable
    )

    def test_current_version_create_and_historical_receipt_pin_are_independent(self):
        from apps.organizations.models import MembershipRoleAssignment
        from apps.procurement.source_to_pay_services import (
            decide_purchase_order_change,
            request_purchase_order_change,
        )

        order, item = self.make_order()
        old = self.create_receipt(order)
        original_version = order.current_version
        member = self.organization.memberships.get(user=self.member)
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=member,
            role=member.role_definition,
            source="test_fixture",
            reason="Explicit independent PO change decision fixture",
        )
        change = request_purchase_order_change(
            organization=self.organization,
            actor=self.owner,
            purchase_order=order,
            line_changes={
                str(original_version.lines.get().pk): (Decimal(8), Decimal("12.50"))
            },
            reason="اصلاح مصوب مقدار",
            evidence="صورت‌جلسه نمونه",
            idempotency_key="version-test",
        )
        decide_purchase_order_change(
            organization=self.organization,
            actor=self.member,
            change_request=change,
            approve=True,
            reason="تأیید مستقل نمونه",
        )
        order.refresh_from_db()
        self.assertEqual(order.current_version.version_number, 2)
        current = self.create_receipt(order, "GRN-V2")
        self.assertEqual(old.purchase_order_version_id, original_version.pk)
        self.assertEqual(current.purchase_order_version_id, order.current_version_id)
        self.assertEqual(quantity_rows(order, receipt=old)[0]["ordered"], Decimal(10))
        self.assertEqual(
            quantity_rows(order, receipt=current)[0]["ordered"], Decimal(8)
        )
        self.assertEqual(self.add(old, item, "6").status_code, 302)
        self.assertEqual(self.post(old).status_code, 302)
        self.assertEqual(
            quantity_rows(order, receipt=current)[0]["remaining"], Decimal(2)
        )
        self.assertEqual(self.add(current, item, "2").status_code, 302)
        self.assertEqual(self.post(current).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")
        self.assertEqual(original_version.lines.get().quantity, Decimal(10))


class ReceiptConcurrencyTests(ReceiptJourneyFixture, TransactionTestCase):
    serialized_rollback = True
    from apps.billing.test_mvp03_browser import ContractBillingBrowserTests

    _fixture_teardown = ContractBillingBrowserTests._fixture_teardown

    def concurrent(self, paths):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections

        barrier = Barrier(2)

        def call(args):
            close_old_connections()
            try:
                client = Client()
                client.force_login(self.owner)
                session = client.session
                set_active_organization(session, self.organization)
                session.save()
                barrier.wait(timeout=15)
                return client.post(*args).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(call, paths))

    def test_concurrent_post_conserves_remaining(self):
        order, item = self.make_order()
        first = self.create_receipt(order)
        second = self.create_receipt(order, "GRN-2")
        self.add(first, item, "6")
        self.add(second, item, "6")
        results = self.concurrent(
            [
                (reverse("procurement:receipt_post", args=[r.pk]), {})
                for r in (first, second)
            ]
        )
        self.assertEqual(sorted(results), [302, 400])
        self.assertEqual(m.GoodsReceipt.objects.filter(status="posted").count(), 1)
        self.assertEqual(quantity_rows(order)[0]["remaining"], Decimal(4))

    def test_concurrent_create_retry_retains_one_source(self):
        order, _ = self.make_order()
        results = self.concurrent([(self.create_url(order), self.payload(order))] * 2)
        self.assertEqual(results, [302, 302])
        self.assertEqual(m.GoodsReceipt.objects.count(), 1)
