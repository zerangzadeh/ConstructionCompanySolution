"""GRN → Inventory receipt journey and independent stock authority checks."""

from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditAction, AuditEvent
from apps.inventory import services as stock
from apps.inventory.models import StockTransaction
from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement import services as purchasing
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.projects.models import Project
from core.jalali import format_jalali


class InventoryJourneyFixture(ReceiptJourneyFixture):
    def received_source(self, number="GRN-1", quantity="10"):
        order, item = self.make_order(quantity=quantity)
        receipt = self.create_receipt(order, number)
        self.assertEqual(self.add(receipt, item, quantity).status_code, 302)
        self.assertEqual(self.post(receipt).status_code, 302)
        receipt.refresh_from_db()
        return receipt, receipt.items.get()

    def stock_url(self, source):
        return (
            reverse("inventory:transaction_create") + f"?goods_receipt_item={source.pk}"
        )

    def stock_payload(self, source, **changes):
        return {
            "goods_receipt_item": str(source.pk),
            "transaction_number": "IN-001",
            "transaction_type": "receipt",
            "material": str(source.material_id),
            "project": str(source.goods_receipt.project_id),
            "quantity": str(source.quantity),
            "destination_warehouse": str(self.site.pk),
            "occurred_at": format_jalali(
                timezone.localtime(self.received_at), include_time=True
            ),
            "reference": source.goods_receipt.receipt_number,
            "notes": "تحویل به انبار",
            **changes,
        }

    def stock_create(self, source, **changes):
        response = self.client.post(
            self.stock_url(source), self.stock_payload(source, **changes)
        )
        self.assertEqual(response.status_code, 302, response.content[:1000])
        return StockTransaction.objects.get(
            transaction_number=changes.get("transaction_number", "IN-001")
        )

    def stock_detail(self, record):
        return reverse("inventory:transaction_detail", args=[record.pk])

    def stock_post(self, record):
        return self.client.post(reverse("inventory:transaction_post", args=[record.pk]))

    def stock_reverse(self, record, **changes):
        return self.client.post(
            reverse("inventory:transaction_reverse", args=[record.pk]),
            {"reversal_number": "REV-001", "reason": "اصلاح تحویل انبار", **changes},
        )

    def balance(self):
        return stock.get_stock_balance(
            user=self.owner,
            organization=self.organization,
            warehouse=self.site,
            material=self.material,
        )

    def financial_counts(self):
        return {
            k: v
            for k, v in self.financial_snapshot().items()
            if k not in ("balance", "inventory.StockTransaction")
        }


class InventoryJourneyTests(InventoryJourneyFixture, TestCase):
    def test_context_source_values_compatible_warehouses_and_navigation_is_readonly(
        self,
    ):
        _receipt, source = self.received_source()
        other = Project.objects.create(
            organization=self.organization, code="OTHER-LOCAL", name="پروژه دیگر"
        )
        wrong = stock.create_warehouse(
            organization=self.organization,
            actor=self.owner,
            code="WRONG",
            name="انبار نامرتبط",
            project=other,
        )
        response = self.client.get(self.stock_url(source))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "سیمان پرتلند")
        self.assertContains(response, "پروژه سازه نمونه")
        for name in (
            "goods_receipt_item",
            "material",
            "project",
            "quantity",
            "transaction_type",
        ):
            self.assertTrue(response.context["form"][name].is_hidden)
        self.assertNotIn(
            wrong, response.context["form"].fields["destination_warehouse"].queryset
        )
        self.assertIn(
            self.site, response.context["form"].fields["destination_warehouse"].queryset
        )
        self.assertIn(
            self.central,
            response.context["form"].fields["destination_warehouse"].queryset,
        )
        self.assertFalse(StockTransaction.objects.exists())
        self.assertEqual(self.balance(), Decimal(0))
        picker = self.client.get(reverse("inventory:transaction_create"))
        self.assertEqual(
            list(picker.context["form"].fields["goods_receipt_item"].queryset), [source]
        )
        lookup = self.client.get(
            reverse("inventory:journey_choices", args=["source", "goods_receipt_item"]),
            {"q": "GRN-1"},
        )
        self.assertIn("سیمان", lookup.json()["results"][0]["label"])

    def test_draft_post_balance_reciprocal_source_and_no_financial_effect(self):
        before = self.financial_counts()
        receipt, source = self.received_source(quantity="1.2345")
        self.assertEqual(self.financial_counts(), before)
        record = self.stock_create(source)
        self.assertEqual(record.status, "draft")
        self.assertEqual(self.balance(), Decimal(0))
        for field in ("material_id", "unit_of_measure_id", "quantity"):
            self.assertEqual(getattr(record, field), getattr(source, field))
        self.assertEqual(record.project_id, receipt.project_id)
        self.assertEqual(record.goods_receipt_item_id, source.pk)
        self.assertEqual(self.stock_post(record).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, "posted")
        self.assertEqual(self.balance(), Decimal("1.2345"))
        detail = self.client.get(self.stock_detail(record))
        self.assertFalse(detail.context["can_post"])
        self.assertContains(detail, "data-inventory-grn")
        self.assertEqual(
            detail.context["balance_rows"][0]["quantity"], Decimal("1.2345")
        )
        self.assertContains(self.client.get(self.detail_url(receipt)), "data-grn-stock")
        self.assertEqual(self.financial_counts(), before)
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.STOCK_TRANSACTION_CREATED,
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(
                organization=self.organization,
                action=AuditAction.STOCK_TRANSACTION_POSTED,
            ).count(),
            1,
        )

    def test_equivalent_retries_draft_posted_reversed_and_conflicts(self):
        _receipt, source = self.received_source()
        record = self.stock_create(source)
        for changes in (
            {"notes": "different"},
            {"transaction_number": "DUPLICATE"},
            {"destination_warehouse": str(self.central.pk)},
            {"occurred_at": "1405/08/12 12:00"},
        ):
            self.assertEqual(
                self.client.post(
                    self.stock_url(source), self.stock_payload(source, **changes)
                ).status_code,
                400,
            )
        for state in ("draft", "posted", "reversed"):
            self.assertEqual(
                self.client.post(
                    self.stock_url(source), self.stock_payload(source)
                ).status_code,
                302,
            )
            self.assertEqual(
                StockTransaction.objects.filter(goods_receipt_item=source).count(), 1
            )
            record.refresh_from_db()
            self.assertEqual(record.status, state)
            if state == "draft":
                self.stock_post(record)
            elif state == "posted":
                self.stock_reverse(record)
        self.assertEqual(self.balance(), Decimal(0))
        self.assertEqual(StockTransaction.objects.count(), 2)
        self.assertEqual(self.client.get(self.stock_url(source)).status_code, 404)

    def test_forged_source_values_and_warehouse_denied_retains_valid_input(self):
        _receipt, source = self.received_source()
        for name, value in (
            ("quantity", "9"),
            ("material", str(self.other_material.pk)),
            ("project", str(self.other_project.pk)),
            ("unit_of_measure", str(self.other_unit.pk)),
            ("goods_receipt_item", str(uuid4())),
            ("transaction_type", "adjustment_in"),
            ("source_warehouse", str(self.site.pk)),
            ("destination_warehouse", str(self.other_warehouse.pk)),
            ("material", "not-an-identifier"),
        ):
            response = self.client.post(
                self.stock_url(source), self.stock_payload(source, **{name: value})
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(
                response.context["form"]["transaction_number"].value(), "IN-001"
            )
            self.assertEqual(
                response.context["form"]["notes"].value(), "تحویل به انبار"
            )
            self.assertNotContains(response, "UUID", status_code=400)
        self.assertFalse(StockTransaction.objects.exists())
        self.assertEqual(self.balance(), Decimal(0))

    def test_valid_reversal_history_balance_and_grn_void_is_separate(self):
        receipt, source = self.received_source()
        record = self.stock_create(source)
        self.stock_post(record)
        before = self.financial_counts()
        self.assertEqual(
            self.client.post(
                reverse("procurement:receipt_void", args=[receipt.pk]),
                {"reason": "مردود"},
            ).status_code,
            400,
        )
        self.assertEqual(self.stock_reverse(record, reason="").status_code, 400)
        self.assertEqual(self.stock_reverse(record).status_code, 302)
        record.refresh_from_db()
        reversal = record.reversal
        self.assertEqual(record.status, "reversed")
        self.assertEqual(reversal.status, "posted")
        self.assertEqual(reversal.quantity, record.quantity)
        self.assertEqual(reversal.source_warehouse_id, record.destination_warehouse_id)
        self.assertEqual(self.balance(), Decimal(0))
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "posted")
        detail = self.client.get(self.stock_detail(reversal))
        self.assertEqual(detail.context["source_item"], source)
        self.assertFalse(detail.context["can_reverse"])
        self.assertContains(
            self.client.get(self.stock_detail(record)), "data-stock-reversal"
        )
        self.assertEqual(self.stock_reverse(record).status_code, 400)
        self.assertEqual(self.stock_post(record).status_code, 400)
        record.quantity = Decimal(1)
        with self.assertRaises(ValidationError):
            record.save()
        self.assertEqual(self.financial_counts(), before)
        self.assertTrue(self.client.get(self.detail_url(receipt)).context["can_void"])
        self.assertEqual(
            self.client.post(
                reverse("procurement:receipt_void", args=[receipt.pk]),
                {"reason": "ابطال پس از برگشت"},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                self.stock_url(source), self.stock_payload(source)
            ).status_code,
            404,
        )
        self.assertEqual(StockTransaction.objects.count(), 2)

    def test_reversal_denied_when_stock_has_been_consumed(self):
        _, source = self.received_source()
        record = self.stock_create(source)
        self.stock_post(record)
        self.create_and_post(
            number="OUT-1",
            transaction_type="issue",
            quantity=Decimal(8),
            source=self.site,
            project=self.project,
            actor=self.owner,
        )
        self.assertEqual(self.balance(), Decimal(2))
        response = self.stock_reverse(record)
        self.assertEqual(response.status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.status, "posted")
        self.assertFalse(StockTransaction.objects.filter(reversal_of=record).exists())
        self.assertEqual(self.balance(), Decimal(2))

    def test_permissions_tenant_project_and_csrf(self):
        _receipt, source = self.received_source()
        record = self.stock_create(source)
        self.login(self.viewer)
        self.assertEqual(self.client.get(self.stock_url(source)).status_code, 403)
        self.assertEqual(self.stock_post(record).status_code, 403)
        self.assertEqual(self.stock_reverse(record).status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.stock_url(source)).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.stock_url(source), self.stock_payload(source)
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(self.stock_detail(record)).status_code, 404)
        self.login(self.owner)
        csrf = Client(enforce_csrf_checks=True)
        csrf.cookies = self.client.cookies
        self.assertEqual(
            csrf.post(self.stock_url(source), self.stock_payload(source)).status_code,
            403,
        )
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=project,
            reason="test",
        )
        self.assertEqual(self.client.get(self.stock_detail(record)).status_code, 404)
        self.assertEqual(self.stock_post(record).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.stock_url(source), self.stock_payload(source)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "inventory:journey_choices", args=["source", "goods_receipt_item"]
                )
            ).json()["results"],
            [],
        )

    def test_unposted_void_sources_and_incompatible_warehouse_fail_closed(self):
        order, line = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, line, "10")
        source = receipt.items.get()
        self.assertEqual(self.client.get(self.stock_url(source)).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.stock_url(source), self.stock_payload(source)
            ).status_code,
            404,
        )
        self.post(receipt)
        project = Project.objects.create(
            organization=self.organization, code="LOCAL", name="پروژه دیگر"
        )
        warehouse = stock.create_warehouse(
            organization=self.organization,
            actor=self.owner,
            project=project,
            name="انبار دیگر",
            code="LOCAL",
        )
        response = self.client.post(
            self.stock_url(source),
            self.stock_payload(source, destination_warehouse=str(warehouse.pk)),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(StockTransaction.objects.exists())
        purchasing.void_goods_receipt(
            organization=self.organization,
            actor=self.owner,
            goods_receipt=receipt,
            reason="ابطال نمونه",
        )
        self.assertEqual(self.client.get(self.stock_url(source)).status_code, 404)

    def test_list_filters_chips_sort_pagination_and_other_flow_preserved(self):
        self.login(self.owner)
        for number in range(27):
            stock.create_stock_transaction(
                organization=self.organization,
                actor=self.owner,
                transaction_number=f"ADJ-{number:02}",
                transaction_type="adjustment_in",
                destination_warehouse=self.site,
                material=self.material,
                unit_of_measure=self.unit,
                project=self.project,
                quantity=Decimal(1),
                occurred_at=self.received_at,
            )
        response = self.client.get(
            reverse("inventory:transaction_list"),
            {
                "q": "ADJ",
                "status": "draft",
                "warehouse": self.site.pk,
                "sort": "number",
                "direction": "asc",
                "page": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_bar"]["result_count"], 27)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertGreaterEqual(len(response.context["filter_bar"]["chips"]), 3)
        self.assertEqual(
            self.client.get(
                reverse("inventory:transaction_list"),
                {"project": self.other_project.pk},
            ).context["filter_bar"]["result_count"],
            0,
        )
        response = self.client.post(
            reverse("inventory:transaction_create") + "?mode=other",
            {
                "transaction_type": "adjustment_in",
                "transaction_number": "OTHER-FLOW",
                "material": self.material.pk,
                "quantity": "2",
                "project": self.project.pk,
                "destination_warehouse": self.site.pk,
                "occurred_at": format_jalali(
                    timezone.localtime(self.received_at), include_time=True
                ),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            StockTransaction.objects.get(transaction_number="OTHER-FLOW").status,
            "draft",
        )
        self.assertEqual(self.balance(), Decimal(0))


class InventoryJourneyConcurrencyTests(InventoryJourneyFixture, TransactionTestCase):
    serialized_rollback = True
    from apps.billing.test_mvp03_browser import ContractBillingBrowserTests

    _fixture_teardown = ContractBillingBrowserTests._fixture_teardown

    def test_concurrent_identical_http_acceptance_retains_one_draft(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections

        _, source = self.received_source()
        barrier = Barrier(2)

        def submit(_):
            close_old_connections()
            try:
                client = Client()
                client.force_login(self.owner)
                session = client.session
                set_active_organization(session, self.organization)
                session.save()
                barrier.wait(timeout=15)
                return client.post(
                    self.stock_url(source), self.stock_payload(source)
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, range(2)))
        self.assertEqual(results, [302, 302])
        self.assertEqual(
            StockTransaction.objects.filter(goods_receipt_item=source).count(), 1
        )
        self.assertEqual(self.balance(), Decimal(0))
