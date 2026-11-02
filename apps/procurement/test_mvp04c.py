"""MVP-04C source consumption and PO presentation contract checks."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement import comparison_services as commercial
from apps.procurement import models as m
from apps.procurement.test_p5_s11_comparison_award import P5S11FixtureMixin
from apps.projects.models import Project
from core.jalali import format_jalali


class OrderJourneyFixture(P5S11FixtureMixin):
    def setUp(self):
        super().setUp()
        self.rfq = self.revision.envelope.rfq
        for code in (
            P.PURCHASE_ORDERS_CREATE,
            P.PURCHASE_ORDERS_VIEW,
            P.PURCHASE_ORDERS_ISSUE,
            P.PURCHASE_ORDER_ITEMS_ADD,
            P.GOODS_RECEIPTS_CREATE,
        ):
            self._grant(code, self.preparer)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def award(self, quantity="4"):
        comparison, _ = self._evaluated_comparison()
        finalized = commercial.finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="مقایسه کامل",
        )
        prepared = commercial.prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=finalized,
            outcome="awarded",
            allocations=[
                {
                    "comparison_input_id": str(finalized.inputs.get().pk),
                    "quantity": quantity,
                }
            ],
            reason="انتخاب مصوب",
            evidence="صورت‌جلسه کمیته",
            idempotency_key="source-award",
        )
        return commercial.finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=prepared
        )

    def source_url(self, award, supplier=None):
        return (
            reverse("procurement:order_from_award", args=[award.pk])
            + f"?supplier={(supplier or self.supplier).pk}"
        )

    def payload(self, source, number="PO-SOURCE", **changes):
        return {
            "award": str(source.pk),
            "supplier": str(self.supplier.pk),
            "project": str(self.project.pk),
            "allocations": [str(a.pk) for a in source.allocations.all()],
            "order_number": number,
            "order_date": format_jalali(date(2026, 11, 2)),
            "notes": "یادداشت سفارش",
            **changes,
        }

    def sourced_order(self, award=None, **changes):
        award = award or self.award()
        self.login(self.preparer)
        response = self.client.post(
            self.source_url(award), self.payload(award, **changes)
        )
        self.assertEqual(
            response.status_code,
            302,
            response.context["form"].errors
            if response.status_code == 400
            else response.content[:500],
        )
        return m.PurchaseOrder.objects.get(order_number="PO-SOURCE")


class AwardPOJourneyTests(OrderJourneyFixture, TestCase):
    def test_contextual_entry_conserved_partial_award_retry_and_no_downstream(self):
        award = self.award("4")
        self.login(self.preparer)
        self.assertFalse(m.PurchaseOrder.objects.exists())
        workspace = self.client.get(
            reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        )
        self.assertContains(workspace, "data-award-po")
        response = self.client.get(self.source_url(award))
        self.assertEqual(response.status_code, 200)
        for name in ("award", "supplier", "project"):
            self.assertTrue(response.context["form"][name].is_hidden)
        order = self.sourced_order(award)
        line = order.items.get()
        self.assertEqual(line.quantity, Decimal(4))
        self.assertEqual(line.unit_price, Decimal("12.50"))
        self.assertEqual(line.source_award_allocation_id, award.allocations.get().pk)
        self.assertEqual(order.project_id, self.project.pk)
        self.assertEqual(order.supplier_id, self.supplier.pk)
        self.assertEqual(order.source_award_id, award.pk)
        self.assertEqual(order.status, "draft")
        self.assertEqual(
            self.client.post(self.source_url(award), self.payload(award)).status_code,
            302,
        )
        self.assertEqual(m.PurchaseOrder.objects.count(), 1)
        self.assertEqual(
            self.client.post(
                self.source_url(award), self.payload(award, order_number="PO-OTHER")
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                self.source_url(award), self.payload(award, notes="changed")
            ).status_code,
            400,
        )
        self.assertFalse(m.GoodsReceipt.objects.exists())
        from apps.accounting.models import JournalEntry
        from apps.projects.models import ProjectCostFact
        from apps.treasury.models import TreasuryMovement

        for model in (JournalEntry, TreasuryMovement, ProjectCostFact):
            self.assertFalse(
                model.objects.filter(organization=self.organization).exists()
            )

    def test_forged_supplier_project_allocation_excess_and_direct_bypass_denied(self):
        award = self.award()
        self.login(self.preparer)
        for changes in (
            {"supplier": str(self.other_supplier.pk)},
            {"project": str(self.other_project.pk)},
            {"award": str(uuid4())},
            {"allocations": [str(uuid4())]},
            {"quantity": "100"},
        ):
            response = self.client.post(
                self.source_url(award), self.payload(award, **changes)
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(m.PurchaseOrder.objects.exists())
        self.assertEqual(
            self.client.get(self.source_url(award, self.other_supplier)).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("procurement:order_create"), self.payload(award)
            ).status_code,
            403,
        )

    def test_issue_frozen_version_source_and_contextual_grn_entry_only(self):
        order = self.sourced_order()
        detail = reverse("procurement:order_detail", args=[order.pk])
        self.assertEqual(
            self.client.post(
                reverse("procurement:order_issue", args=[order.pk])
            ).status_code,
            302,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "issued")
        self.assertEqual(order.current_version.source_award_id, order.source_award_id)
        line = order.current_version.lines.get()
        self.assertEqual(
            line.award_allocation_id, order.items.get().source_award_allocation_id
        )
        self.assertEqual(
            self.client.post(
                reverse("procurement:order_issue", args=[order.pk])
            ).status_code,
            400,
        )
        self.assertEqual(order.versions.count(), 1)
        response = self.client.get(detail)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-po-issue")
        self.assertContains(response, "data-po-grn")
        self.assertFalse(response.context["can_add_item"])
        receipt = self.client.get(
            reverse("procurement:receipt_create") + f"?purchase_order={order.pk}"
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertTrue(receipt.context["form"]["purchase_order"].is_hidden)
        self.assertFalse(m.GoodsReceipt.objects.exists())
        forged = self.client.post(
            reverse("procurement:receipt_create") + f"?purchase_order={order.pk}",
            {
                "purchase_order": str(uuid4()),
                "receipt_number": "NO-GRN",
                "received_at": format_jalali(timezone.now(), include_time=True),
            },
        )
        self.assertIn(forged.status_code, (200, 400))
        self.assertFalse(m.GoodsReceipt.objects.exists())

    def test_sourced_draft_cannot_accept_unsourced_direct_rows(self):
        order = self.sourced_order()
        response = self.client.post(
            reverse("procurement:order_item_add", args=[order.pk]),
            {"material": str(self.material.pk), "quantity": "50", "unit_price": "1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(order.items.count(), 1)

    def test_legacy_direct_create_line_issue_and_business_labels(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("procurement:order_create"),
            {
                "project": str(self.project.pk),
                "supplier": str(self.supplier.pk),
                "order_number": "PO-DIRECT",
                "order_date": format_jalali(date(2026, 11, 2)),
                "notes": "مستقیم",
            },
        )
        self.assertEqual(response.status_code, 302)
        order = m.PurchaseOrder.objects.get()
        self.assertIsNone(order.source_award_id)
        add_url = reverse("procurement:order_item_add", args=[order.pk])
        response = self.client.post(
            add_url,
            {"material": str(self.material.pk), "quantity": "2", "unit_price": "20"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.post(
                reverse("procurement:order_issue", args=[order.pk])
            ).status_code,
            302,
        )
        self.assertContains(self.client.get(response.url), "ثبت مستقیم / سابقه")
        self.assertEqual(order.items.get().line_total, Decimal("40.00"))

    def test_list_real_filters_chips_sort_pagination_and_retention(self):
        self.login(self.owner)
        for index in range(27):
            m.PurchaseOrder.objects.create(
                organization=self.organization,
                project=self.project,
                supplier=self.supplier,
                order_number=f"PO-LIST-{index:02}",
                order_date=date(2026, 11, 2),
                created_by=self.owner,
                updated_by=self.owner,
            )
        url = reverse("procurement:order_list")
        response = self.client.get(
            url,
            {"q": "PO-LIST", "status": "draft", "sort": "number", "direction": "asc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 27)
        self.assertContains(response, "data-filter-chip")
        self.assertEqual(self.client.get(url, {"page": "2"}).status_code, 200)
        response = self.client.post(
            reverse("procurement:order_create"),
            {
                "project": str(self.project.pk),
                "supplier": str(self.supplier.pk),
                "order_number": "RETAIN",
                "notes": "اطلاعات حفظ‌شده",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.context["form"]["notes"].value(), "اطلاعات حفظ‌شده")

    def test_create_and_issue_have_no_receiving_inventory_or_financial_side_effect(
        self,
    ):
        from apps.accounting.models import JournalEntry
        from apps.inventory.models import StockTransaction
        from apps.projects.models import ProjectCostFact
        from apps.subledgers.models import Obligation, SupplierInvoice
        from apps.treasury.models import TreasuryMovement

        models = (
            m.GoodsReceipt,
            StockTransaction,
            Obligation,
            SupplierInvoice,
            JournalEntry,
            TreasuryMovement,
            ProjectCostFact,
        )
        before = {
            model: model.objects.filter(organization=self.organization).count()
            for model in models
        }
        order = self.sourced_order()
        self.assertEqual(
            self.client.post(
                reverse("procurement:order_issue", args=[order.pk])
            ).status_code,
            302,
        )
        for model in models:
            self.assertEqual(
                model.objects.filter(organization=self.organization).count(),
                before[model],
            )

    def test_source_post_remains_csrf_protected(self):
        from django.test import Client

        award = self.award()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.preparer)
        session = client.session
        set_active_organization(session, self.organization)
        session.save()
        self.assertEqual(
            client.post(self.source_url(award), self.payload(award)).status_code, 403
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())

    def test_unauthorized_tenant_and_project_denial(self):
        award = self.award()
        self.login(self.viewer)
        self.assertEqual(self.client.get(self.source_url(award)).status_code, 403)
        self.login(self.outsider)
        session = self.client.session
        set_active_organization(session, self.other_organization)
        session.save()
        self.assertEqual(self.client.get(self.source_url(award)).status_code, 404)
        self.login(self.owner)
        self.assertEqual(
            self.client.get(
                reverse("procurement:order_from_award", args=[self.other_project.pk])
            ).status_code,
            404,
        )
        member = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="پروژه محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=project,
            reason="test",
        )
        self.assertEqual(self.client.get(self.source_url(award)).status_code, 404)


class AwardConsumptionConcurrencyTests(OrderJourneyFixture, TransactionTestCase):
    serialized_rollback = True
    from apps.billing import test_mvp03_browser as _chrome_fixture

    _fixture_teardown = _chrome_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_two_explicit_orders_cannot_consume_the_same_allocation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections
        from django.test import Client

        award = self.award()
        barrier = Barrier(2)

        def submit(number):
            close_old_connections()
            try:
                client = Client()
                client.force_login(self.preparer)
                session = client.session
                set_active_organization(session, self.organization)
                session.save()
                barrier.wait(timeout=15)
                return client.post(
                    self.source_url(award), self.payload(award, number=number)
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ["PO-CONCURRENT-A", "PO-CONCURRENT-B"]))
        self.assertEqual(sorted(results), [302, 400])
        self.assertEqual(m.PurchaseOrder.objects.count(), 1)
        self.assertEqual(
            m.PurchaseOrderItem.objects.get().quantity, award.allocations.get().quantity
        )
