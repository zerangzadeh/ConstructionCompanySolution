"""Real installed Chrome evidence for explicit GRN → Inventory stock entry."""

import json
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.inventory import services as stock
from apps.inventory.models import StockTransaction
from apps.inventory.test_mvp04e import InventoryJourneyFixture
from apps.organizations.models import MembershipScopeGrant
from apps.procurement.test_mvp04b2_browser import BrowserMixin
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class InventoryBrowserTests(
    BrowserMixin, InventoryJourneyFixture, StaticLiveServerTestCase
):
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04e/browser"
    )
    login = InventoryJourneyFixture.login

    def submit(self, selector, fill=None, after=None, prefix=None, text=None):
        return {
            "formSelector": selector,
            "fill": fill or {},
            "clickSelector": selector + " button[type=submit]",
            **({"afterPath": after} if after else {}),
            **({"afterPrefix": prefix} if prefix else {}),
            **({"mustText": text} if text else {}),
        }

    def responsive(self, prefix, path, **kwargs):
        self.browser(
            self.owner,
            [
                self.case(
                    f"{prefix}-{width}",
                    path,
                    width=width,
                    mobile=width == 390,
                    **kwargs,
                )
                for width in (1440, 1024, 390)
            ],
        )

    def fetch_post(self, path, data, status=400):
        return self.inspect(
            "(async()=>{const r=await fetch("
            + json.dumps(path)
            + ",{method:'POST',headers:{'X-CSRFToken':document.cookie.split('; ').find(c=>c.startsWith('csrftoken=')).split('=')[1]},body:new URLSearchParams("
            + json.dumps(data)
            + ")});const d=new DOMParser().parseFromString(await r.text(),'text/html');return r.status==="
            + str(status)
            + " && !/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}|\\bidempotency\\b|object \\(/i.test(d.querySelector('main')?.innerText||'')})()",
            "source/retry response is expected and contains no technical identity",
        )

    def test_grn_draft_explicit_post_balance_reversal_and_source_navigation(self):
        receipt, source = self.received_source()
        before = self.financial_counts()
        grn = self.detail_url(receipt)
        create = self.stock_url(source)
        create_path = reverse("inventory:transaction_create")
        self.browser(
            self.owner,
            [
                self.case(
                    "posted-grn-contextual-inventory-entry",
                    grn,
                    steps=[
                        {
                            "clickSelector": "[data-grn-inventory]",
                            "afterPath": create_path,
                        },
                        self.inspect(
                            "['material','quantity','project','goods_receipt_item','transaction_type'].every(n=>document.querySelector('main [name='+n+']').type==='hidden')",
                            "authoritative receipt fields are fixed and require no technical entry",
                        ),
                        {"history": "back"},
                        {"history": "forward"},
                        {"reload": True, "afterPath": create_path},
                    ],
                )
            ],
        )
        self.assertFalse(StockTransaction.objects.exists())
        self.assertEqual(self.balance(), Decimal(0))
        self.responsive(
            "receipt-entry",
            create,
            mustText=["سیمان پرتلند", "عدد", "پروژه سازه نمونه", "پیش‌نویس"],
        )
        form = 'form[aria-label="ورود به انبار از رسید کالا"]'
        self.browser(
            self.owner,
            [
                self.case(
                    "incompatible-warehouse-denied",
                    create,
                    noHttpErrors=False,
                    steps=[
                        self.fetch_post(
                            create,
                            self.stock_payload(
                                source,
                                destination_warehouse=str(self.other_warehouse.pk),
                            ),
                        )
                    ],
                ),
                self.case(
                    "receipt-validation-retains-input",
                    create,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "destination_warehouse",
                                "query": self.site.name,
                                "value": str(self.site.pk),
                            }
                        },
                        self.submit(
                            form,
                            self.stock_payload(source, transaction_number=""),
                            after=create_path,
                        ),
                        self.inspect(
                            "document.querySelector('[name=notes]').value==='تحویل به انبار' && !!document.querySelector('.errorlist,[role=alert]')",
                            "valid business inputs retained after invalid header",
                        ),
                    ],
                ),
                self.case(
                    "inventory-receipt-create-draft",
                    create,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "destination_warehouse",
                                "query": self.site.name,
                                "value": str(self.site.pk),
                            }
                        },
                        self.submit(
                            form,
                            self.stock_payload(source),
                            prefix="/inventory/transactions/",
                            text="هنوز اثری بر موجودی",
                        ),
                    ],
                ),
            ],
        )
        record = StockTransaction.objects.get(transaction_number="IN-001")
        detail = self.stock_detail(record)
        self.assertEqual(record.status, "draft")
        self.assertEqual(self.balance(), Decimal(0))
        self.assertEqual(record.material_id, source.material_id)
        self.assertEqual(record.unit_of_measure_id, source.unit_of_measure_id)
        self.assertEqual(record.quantity, source.quantity)
        self.assertEqual(record.project_id, receipt.project_id)
        self.responsive(
            "inventory-draft-detail",
            detail,
            mustText=["ثبت نهایی ورود به انبار", "GRN-1"],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "draft-refresh-and-identical-retry",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        {"reload": True, "afterPath": detail},
                        self.fetch_post(create, self.stock_payload(source), 200),
                    ],
                )
            ],
        )
        self.assertEqual(StockTransaction.objects.count(), 1)
        self.assertEqual(self.balance(), Decimal(0))
        self.browser(
            self.owner,
            [
                self.case(
                    "explicit-inventory-post",
                    detail,
                    steps=[
                        self.submit(
                            'form[aria-label="ثبت نهایی گردش"]',
                            after=detail,
                            text="فقط خواندنی",
                        ),
                    ],
                )
            ],
        )
        record.refresh_from_db()
        self.assertEqual(record.status, "posted")
        self.assertEqual(self.balance(), Decimal(10))
        self.responsive(
            "inventory-posted-detail",
            detail,
            mustText=["فقط خواندنی", "موجودی فعلی انبار", "GRN-1"],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "posted-source-navigation-and-warehouse-balance",
                    detail,
                    steps=[
                        self.inspect(
                            "!document.querySelector('[data-stock-post]') && document.querySelector('[data-warehouse-balance]').textContent.includes('10')",
                            "posted receipt is immutable and real balance is ten",
                        ),
                        {"clickSelector": "[data-inventory-grn]", "afterPath": grn},
                        {"clickSelector": "[data-grn-stock]", "afterPath": detail},
                        {"history": "back"},
                        {"history": "forward"},
                    ],
                ),
                self.case(
                    "posted-equivalent-conflicting-duplicate-retries",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        self.fetch_post(create, self.stock_payload(source), 200),
                        self.fetch_post(
                            create, self.stock_payload(source, notes="تعارض")
                        ),
                        self.fetch_post(
                            create,
                            self.stock_payload(source, transaction_number="DUPLICATE"),
                        ),
                        self.fetch_post(
                            reverse("inventory:transaction_post", args=[record.pk]), {}
                        ),
                    ],
                ),
            ],
        )
        self.assertEqual(self.balance(), Decimal(10))
        self.assertEqual(StockTransaction.objects.count(), 1)
        self.assertEqual(self.financial_counts(), before)
        reverse_path = reverse("inventory:transaction_reverse", args=[record.pk])
        self.browser(
            self.owner,
            [
                self.case(
                    "valid-inventory-reversal",
                    detail,
                    steps=[
                        {
                            "clickSelector": "[data-stock-reverse]",
                            "afterPath": reverse_path,
                        },
                        self.submit(
                            'form[aria-label="برگشت گردش انبار"]',
                            {
                                "reversal_number": "REV-001",
                                "reason": "اصلاح تحویل نمونه",
                            },
                            prefix="/inventory/transactions/",
                            text="برگشت گردش",
                        ),
                    ],
                )
            ],
        )
        record.refresh_from_db()
        self.assertEqual(record.status, "reversed")
        self.assertEqual(self.balance(), Decimal(0))
        self.assertEqual(StockTransaction.objects.count(), 2)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "posted")
        self.responsive(
            "inventory-reversed-history",
            detail,
            mustText=["اصلاح تحویل نمونه", "REV-001", "فقط خواندنی"],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "reversed-retry-retains-history-and-zero-balance",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        self.fetch_post(create, self.stock_payload(source), 200),
                        self.inspect(
                            "!document.querySelector('[data-stock-reverse]') && document.querySelector('[data-warehouse-balance]').textContent.includes('0')",
                            "reversed stock is not reactivated and balance is zero",
                        ),
                    ],
                ),
                self.case(
                    "grn-void-prerequisite-after-inventory-reversal",
                    grn,
                    steps=[
                        self.inspect(
                            "!!document.querySelector('form[aria-label=\"ابطال رسید\"]')",
                            "Inventory reversal allows the existing explicit Procurement void action",
                        ),
                        {"toggleSelector": "main aside details summary"},
                        self.submit(
                            'form[aria-label="ابطال رسید"]',
                            {"reason": "ابطال پس از برگشت انبار"},
                            after=grn,
                            text="رسید باطل شده است",
                        ),
                    ],
                ),
            ],
        )
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "void")
        self.assertEqual(self.financial_counts(), before)

    def test_source_and_warehouse_forgery_unposted_permission_tenant_project_denials(
        self,
    ):
        order, line = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, line, "10")
        source = receipt.items.get()
        create = self.stock_url(source)
        self.browser(
            self.owner,
            [
                self.case(
                    "unposted-grn-line-denied", create, status=404, noHttpErrors=False
                )
            ],
        )
        self.post(receipt)
        self.browser(
            self.owner,
            [
                self.case(
                    "source-value-and-warehouse-forgery-denied",
                    create,
                    noHttpErrors=False,
                    steps=[
                        self.fetch_post(
                            create, self.stock_payload(source, quantity="11")
                        ),
                        self.fetch_post(
                            create,
                            self.stock_payload(
                                source, material=str(self.other_material.pk)
                            ),
                        ),
                        self.fetch_post(
                            create,
                            self.stock_payload(
                                source, project=str(self.other_project.pk)
                            ),
                        ),
                        self.fetch_post(
                            create,
                            self.stock_payload(
                                source, goods_receipt_item=str(self.other_project.pk)
                            ),
                        ),
                        self.fetch_post(
                            create,
                            self.stock_payload(
                                source,
                                destination_warehouse=str(self.other_warehouse.pk),
                            ),
                        ),
                    ],
                )
            ],
        )
        self.assertFalse(StockTransaction.objects.exists())
        record = self.stock_create(source)
        detail = self.stock_detail(record)
        # Exercise source isolation against an otherwise eligible unused line.
        unused_order, unused_line = self.make_order("PO-UNUSED")
        unused_receipt = self.create_receipt(unused_order, "GRN-UNUSED")
        self.add(unused_receipt, unused_line, "1")
        self.post(unused_receipt)
        unused_create = self.stock_url(unused_receipt.items.get())
        self.assertEqual(self.client.get(unused_create).status_code, 200)
        self.browser(
            self.viewer,
            [
                self.case(
                    "unauthorized-inventory-entry",
                    create,
                    status=403,
                    noHttpErrors=False,
                )
            ],
        )
        self.browser(
            self.outsider,
            [
                self.case(
                    "cross-tenant-source-denial",
                    unused_create,
                    status=404,
                    noHttpErrors=False,
                ),
                self.case(
                    "cross-tenant-inventory-detail-denial",
                    detail,
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )
        member = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        restricted = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="پروژه محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=restricted,
            reason="test",
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "cross-project-source-denial",
                    unused_create,
                    status=404,
                    noHttpErrors=False,
                ),
                self.case(
                    "cross-project-inventory-detail-denial",
                    detail,
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )

    def test_general_eligible_line_entry_list_filters_sort_and_pagination(self):
        _, source = self.received_source()
        create = reverse("inventory:transaction_create")
        self.responsive("inventory-source-selection", create, mustText=["قلم رسید"])
        self.browser(
            self.owner,
            [
                self.case(
                    "general-eligible-grn-line-search",
                    create,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "goods_receipt_item",
                                "query": "سیمان",
                                "value": str(source.pk),
                            }
                        },
                        self.submit(
                            'form[aria-label="انتخاب رسید کالا"]',
                            after=create,
                            text="رسید مبدأ و اقلام ورود",
                        ),
                    ],
                )
            ],
        )
        self.assertFalse(StockTransaction.objects.exists())
        self.stock_create(source)
        for number in range(26):
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
        path = reverse("inventory:transaction_list")
        self.responsive(
            "inventory-list", path, mustText=["سیمان پرتلند", "ورود جدید به انبار"]
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "inventory-list-search-chips-sort",
                    path + "?q=ADJ&status=draft&sort=number&direction=asc",
                    mustText=["ADJ-00"],
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('[data-filter-chip]').length>=2 || document.querySelector('main').innerText.includes('حذف')",
                            "active filters are visible",
                        )
                    ],
                ),
                self.case(
                    "inventory-list-pagination",
                    path + "?sort=number&direction=asc&page=2",
                    mustText=["IN-001"],
                ),
            ],
        )
