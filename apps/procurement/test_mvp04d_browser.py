"""Installed Chrome evidence for the bounded PO → GRN journey."""

import json
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import MembershipScopeGrant
from apps.procurement import models as m
from apps.procurement import services as s
from apps.procurement.test_mvp04b2_browser import BrowserMixin
from apps.procurement.test_mvp04d import ReceiptJourneyFixture
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReceiptBrowserTests(
    BrowserMixin, ReceiptJourneyFixture, StaticLiveServerTestCase
):
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04d/browser"
    )

    # BrowserMixin's login assumes a richer sourcing fixture; use this GRN fixture.
    login = ReceiptJourneyFixture.login

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

    def denied_post(self, path, data, status=400):
        return self.inspect(
            "(async()=>{const r=await fetch("
            + json.dumps(path)
            + ",{method:'POST',headers:{'X-CSRFToken':document.cookie.split('; ').find(c=>c.startsWith('csrftoken=')).split('=')[1]},body:new URLSearchParams("
            + json.dumps(data)
            + ")});const d=new DOMParser().parseFromString(await r.text(),'text/html');return r.status==="
            + str(status)
            + " && !/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}/i.test(d.querySelector('main')?.innerText||'')})()",
            "business denial without technical identity leakage",
        )

    def test_contextual_partial_second_full_receipt_and_inventory_entry(self):
        order, item = self.make_order()
        po_path = reverse("procurement:order_detail", args=[order.pk])
        create_path = reverse("procurement:receipt_create")
        context_path = self.create_url(order)
        before = self.financial_snapshot()
        self.responsive(
            "context-create",
            context_path,
            mustText=["تأمین مصالح پارس", "پروژه سازه نمونه", "سیمان پرتلند"],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "issued-po-contextual-create",
                    po_path,
                    steps=[
                        {"clickSelector": "[data-po-grn]", "afterPath": create_path},
                        self.inspect(
                            "document.querySelector('main [name=purchase_order]').type==='hidden' && !document.querySelector('main [name=project]') && !document.querySelector('main [name=supplier]')",
                            "fixed server PO and inherited project/supplier",
                        ),
                        self.submit(
                            'form[aria-label="رسید کالای جدید"]',
                            self.payload(order),
                            prefix="/procurement/receipts/",
                            text="افزودن قلم دریافت",
                        ),
                    ],
                )
            ],
        )
        receipt = m.GoodsReceipt.objects.get(receipt_number="GRN-1")
        detail = self.detail_url(receipt)
        self.responsive(
            "draft-detail", detail, mustText=["باقی‌مانده", "عدد", "افزودن قلم دریافت"]
        )
        line_form = 'form[aria-label="افزودن قلم رسید"]'
        self.browser(
            self.owner,
            [
                self.case(
                    "excess-receipt-denied",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            reverse("procurement:receipt_item_add", args=[receipt.pk]),
                            {"purchase_order_item": str(item.pk), "quantity": "11"},
                        ),
                    ],
                ),
                self.case(
                    "partial-line-entry",
                    detail,
                    steps=[
                        self.inspect(
                            "[...document.querySelector('[name=purchase_order_item]').options].some(o=>o.textContent.includes('سیمان پرتلند')&&o.textContent.includes('عدد'))",
                            "business-labelled PO line",
                        ),
                        self.submit(
                            line_form,
                            {"purchase_order_item": str(item.pk), "quantity": "4"},
                            after=detail,
                        ),
                    ],
                ),
                self.case(
                    "duplicate-line-retry-denied",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            reverse("procurement:receipt_item_add", args=[receipt.pk]),
                            {"purchase_order_item": str(item.pk), "quantity": "4"},
                        )
                    ],
                ),
                self.case(
                    "partial-post-grn",
                    detail,
                    steps=[
                        self.submit(
                            'form[aria-label="ثبت نهایی رسید"]',
                            after=detail,
                            text="فقط خواندنی",
                        ),
                    ],
                ),
            ],
        )
        receipt.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(receipt.status, "posted")
        self.assertEqual(order.status, "issued")
        self.assertEqual(self.financial_snapshot(), before)
        self.responsive(
            "posted-detail", detail, mustText=["فقط خواندنی", "ثبت ورود به انبار"]
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "posted-immutable-retry-refresh",
                    detail,
                    noHttpErrors=False,
                    steps=[
                        self.inspect(
                            "!document.querySelector('main form[aria-label=\"افزودن قلم رسید\"]') && !document.querySelector('main form[aria-label=\"ثبت نهایی رسید\"]')",
                            "posted evidence has no direct editing or repost controls",
                        ),
                        self.denied_post(
                            reverse("procurement:receipt_post", args=[receipt.pk]), {}
                        ),
                        {"reload": True, "afterPath": detail},
                    ],
                ),
                self.case(
                    "posted-grn-inventory-context",
                    detail,
                    steps=[
                        {
                            "clickSelector": "[data-grn-inventory]",
                            "afterPath": reverse("inventory:transaction_create"),
                        },
                        self.inspect(
                            f"document.querySelector('[name=goods_receipt_item]').value==='{receipt.items.get().pk}' && document.querySelector('[name=project]').value==='{self.project.pk}' && document.querySelector('[name=quantity]').value==='4.0000'",
                            "existing Inventory form inherits receipt line, project and exact quantity",
                        ),
                        {"history": "back"},
                        {"history": "forward"},
                        {"history": "back"},
                    ],
                ),
            ],
        )
        self.assertEqual(self.financial_snapshot(), before)
        self.responsive("general-create", create_path)
        self.browser(
            self.owner,
            [
                self.case(
                    "general-eligible-po-search-and-second-grn",
                    create_path,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "purchase_order",
                                "query": "تأمین مصالح",
                                "value": str(order.pk),
                            }
                        },
                        self.submit(
                            'form[aria-label="رسید کالای جدید"]',
                            self.payload(order, "GRN-2"),
                            prefix="/procurement/receipts/",
                            text="افزودن قلم دریافت",
                        ),
                    ],
                )
            ],
        )
        second = m.GoodsReceipt.objects.get(receipt_number="GRN-2")
        second_detail = self.detail_url(second)
        response = self.client.get(second_detail)
        self.assertEqual(response.context["quantity_rows"][0]["remaining"], Decimal(6))
        self.assertEqual(response.context["quantity_rows"][0]["previous"], Decimal(4))
        self.browser(
            self.owner,
            [
                self.case(
                    "second-receipt-exact-remaining-full-post",
                    second_detail,
                    steps=[
                        self.inspect(
                            "document.querySelector('[name=purchase_order_item]').textContent.includes('6.0000')",
                            "remaining quantity is exactly six",
                        ),
                        self.submit(
                            line_form,
                            {"purchase_order_item": str(item.pk), "quantity": "6"},
                            after=second_detail,
                        ),
                        self.submit(
                            'form[aria-label="ثبت نهایی رسید"]',
                            after=second_detail,
                            text="فقط خواندنی",
                        ),
                    ],
                )
            ],
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")
        self.assertEqual(self.financial_snapshot(), before)
        self.browser(
            self.owner,
            [
                self.case(
                    "completed-po-no-receipt-action",
                    po_path,
                    steps=[
                        self.inspect(
                            "!document.querySelector('[data-po-grn]')",
                            "completed PO has no new receiving action",
                        )
                    ],
                ),
                self.case(
                    "completed-po-business-explanation",
                    context_path,
                    mustText=["فقط برای سفارش صادرشده"],
                ),
            ],
        )

    def test_void_dependency_denial_valid_void_and_isolation(self):
        order, item = self.make_order()
        receipt = self.create_receipt(order)
        self.add(receipt, item, "10")
        self.post(receipt)
        detail = self.detail_url(receipt)
        stock = self.create_and_post(
            number="STOCK-EXPLICIT",
            transaction_type="receipt",
            quantity=Decimal(10),
            destination=self.site,
            project=self.project,
            goods_receipt_item=receipt.items.get(),
            actor=self.owner,
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "void-denied-inventory-dependency",
                    detail,
                    noHttpErrors=False,
                    mustText=["دریافت‌های نهایی‌شده انبار را برگشت دهید"],
                    steps=[
                        self.denied_post(
                            reverse("procurement:receipt_void", args=[receipt.pk]),
                            {"reason": "مردود"},
                        ),
                    ],
                )
            ],
        )
        stock.refresh_from_db()
        self.assertEqual(stock.status, "posted")
        other_order, wrong_item = self.make_order("PO-OTHER")
        valid = self.create_receipt(other_order, "GRN-VOID")
        self.add(valid, wrong_item, "4")
        self.post(valid)
        valid_detail = self.detail_url(valid)
        self.browser(
            self.owner,
            [
                self.case(
                    "valid-void-with-business-reason",
                    valid_detail,
                    steps=[
                        {"toggleSelector": "main aside details summary"},
                        self.submit(
                            'form[aria-label="ابطال رسید"]',
                            {"reason": "اصلاح رسید نمونه"},
                            after=valid_detail,
                            text="رسید باطل شده است",
                        ),
                    ],
                )
            ],
        )
        valid.refresh_from_db()
        self.assertEqual(valid.status, "void")
        draft = self.create_receipt(other_order, "GRN-DENIAL")
        draft_detail = self.detail_url(draft)
        self.browser(
            self.owner,
            [
                self.case(
                    "wrong-po-line-denial",
                    draft_detail,
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            reverse("procurement:receipt_item_add", args=[draft.pk]),
                            {"purchase_order_item": str(item.pk), "quantity": "1"},
                        )
                    ],
                ),
                self.case(
                    "forged-project-context-denial",
                    self.create_url(other_order),
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            self.create_url(other_order),
                            self.payload(
                                other_order,
                                "FORGED",
                                project=str(self.other_project.pk),
                            ),
                        )
                    ],
                ),
            ],
        )
        self.browser(
            self.viewer,
            [
                self.case(
                    "unauthorized-receipt-create",
                    self.create_url(),
                    status=403,
                    noHttpErrors=False,
                )
            ],
        )
        self.browser(
            self.outsider,
            [
                self.case(
                    "cross-tenant-receipt-denial",
                    detail,
                    status=404,
                    noHttpErrors=False,
                ),
                self.case(
                    "cross-tenant-po-denial",
                    self.create_url(order),
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        restricted = Project.objects.create(
            organization=self.organization, code="RESTRICT", name="پروژه محدود"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=restricted,
            reason="test",
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "cross-project-receipt-denial",
                    detail,
                    status=404,
                    noHttpErrors=False,
                ),
                self.case(
                    "cross-project-po-denial",
                    self.create_url(order),
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )

    def test_list_filters_pagination_create_retention_and_retry(self):
        order, _ = self.make_order()
        for number in range(27):
            s.create_goods_receipt(
                organization=self.organization,
                actor=self.owner,
                purchase_order=order,
                receipt_number=f"LIST-{number:02}",
                received_at=self.received_at,
            )
        list_path = reverse("procurement:receipt_list")
        self.responsive(
            "receipt-list", list_path, mustText=["تأمین مصالح پارس", "رسید کالای جدید"]
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "list-filter-sort-active-chips",
                    list_path + "?q=LIST&status=draft&sort=number&direction=asc",
                    mustText=["LIST-00"],
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('[data-filter-chip]').length>=2 || document.querySelector('main').innerText.includes('حذف')",
                            "active search/status filters are visible",
                        )
                    ],
                ),
                self.case(
                    "list-pagination-second-page",
                    list_path + "?q=LIST&sort=number&direction=asc&page=2",
                    mustText=["LIST-25"],
                ),
                self.case(
                    "create-validation-retains-input",
                    self.create_url(order),
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.submit(
                            'form[aria-label="رسید کالای جدید"]',
                            self.payload(order, ""),
                            after=reverse("procurement:receipt_create"),
                        ),
                        self.inspect(
                            "document.querySelector('[name=notes]').value==='یادداشت دریافت' && !!document.querySelector('.errorlist,[role=alert]')",
                            "valid entered values survive validation",
                        ),
                    ],
                ),
                self.case(
                    "header-create-and-exact-retry",
                    self.create_url(order),
                    steps=[
                        self.submit(
                            'form[aria-label="رسید کالای جدید"]',
                            self.payload(order, "RETRY"),
                            prefix="/procurement/receipts/",
                            text="افزودن قلم دریافت",
                        ),
                        {"reload": True},
                        self.inspect(
                            "(async()=>{let r=await fetch("
                            + json.dumps(self.create_url(order))
                            + ",{method:'POST',headers:{'X-CSRFToken':document.cookie.split('; ').find(c=>c.startsWith('csrftoken=')).split('=')[1]},body:new URLSearchParams("
                            + json.dumps(self.payload(order, "RETRY"))
                            + ")});return r.status===200 && r.url.includes('/receipts/')})()",
                            "exact header retry returns the existing draft",
                        ),
                    ],
                ),
            ],
        )
        self.assertEqual(
            m.GoodsReceipt.objects.filter(receipt_number="RETRY").count(), 1
        )
