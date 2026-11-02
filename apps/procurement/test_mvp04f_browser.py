"""Principal full PR → stock journey through installed Chrome, no seeded stages."""

import json
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import StockTransaction
from apps.organizations.models import MembershipScopeGrant
from apps.procurement import models as m
from apps.procurement.test_mvp04b2_browser import BrowserMixin
from apps.procurement.test_mvp04f import ConnectedJourneyFixture
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConnectedBrowserTests(
    BrowserMixin, ConnectedJourneyFixture, StaticLiveServerTestCase
):
    browser_evidence_directory = ConnectedJourneyFixture.evidence_root / "browser"
    login = ConnectedJourneyFixture.login

    def case(self, name, path, **kwargs):
        result = super().case(name, path, **kwargs)
        result["steps"].append(
            self.inspect(
                "!/(?:\\b(?:draft|submitted|approved|no_award|awarded|posted|reversed|idempotency|fingerprint|candidacy)\\b|(?:rfqs|purchase_orders|goods_receipts|stock_transactions)\\.|object \\()/i.test(document.querySelector('main')?.innerText||'')",
                "business-language status, references and authorization messages",
            )
        )
        return result

    def act(
        self,
        actor,
        path,
        fields=None,
        *,
        selector=None,
        button=None,
        upload=False,
        name=None,
        expected=302,
    ):
        self.sequence += 1
        fields = dict(fields or {})
        fields.pop("operation", None)  # Real clicked scope button sends its own value.
        checked = {
            key: fields.pop(key)
            for key in ("supplier_ids", "allocations")
            if isinstance(fields.get(key), list)
        }
        steps, entry = [], path
        if name == "contextual-pr-to-rfq":
            entry = reverse("procurement:request_detail", args=[self.pr.pk])
            steps.append(
                {"clickSelector": "[data-pr-rfq]", "afterPath": urlsplit(path).path}
            )
            steps.append(
                self.inspect(
                    "document.querySelector('[name=purchase_request_id]').type==='hidden'",
                    "PR inherited server-side",
                )
            )
        elif name == "award-to-po":
            entry = reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
            steps.append(
                {"clickSelector": "[data-award-po]", "afterPath": urlsplit(path).path}
            )
        elif name == "po-to-grn":
            order = parse_qs(urlsplit(path).query)["purchase_order"][0]
            entry = reverse("procurement:order_detail", args=[order])
            steps.append(
                {"clickSelector": "[data-po-grn]", "afterPath": urlsplit(path).path}
            )
        elif name == "grn-to-inventory-draft":
            source = m.GoodsReceiptItem.objects.get(
                pk=parse_qs(urlsplit(path).query)["goods_receipt_item"][0]
            )
            entry = reverse(
                "procurement:receipt_detail", args=[source.goods_receipt_id]
            )
            steps.append(
                {
                    "clickSelector": "[data-grn-inventory]",
                    "afterPath": urlsplit(path).path,
                }
            )
        if name == "approve-pr":
            steps.append(
                {"toggleSelector": "section[aria-label='وضعیت بررسی'] details summary"}
            )
        if name == "close-rfq":
            steps.append(
                {"toggleSelector": 'details:has(form[action$="/close/"]) summary'}
            )
        if upload:
            field = "upload" if "attach_evidence" in path else "source_file"
            steps.append(
                {
                    "upload": {
                        "selector": f"main [name={field}]",
                        "path": str(self.source_path),
                    }
                }
            )
        for field, values in checked.items():
            steps.append(
                self.inspect(
                    "(()=>{const f=document.querySelector("
                    + json.dumps(selector)
                    + ");let found=0;f.querySelectorAll('[name="
                    + field
                    + "]').forEach(i=>{i.checked="
                    + json.dumps(values)
                    + ".includes(i.value);if(i.checked)found++});return found==="
                    + str(len(values))
                    + "})()",
                    "select the intended supplier/allocation through its rendered business choices",
                )
            )
        retry = name in {
            "select-suppliers-and-issue",
            "finalize_award",
            "award-to-po",
            "po-to-grn",
            "grn-to-inventory-draft",
        }
        if retry:
            steps.append(
                {
                    "formSelector": selector,
                    "fill": fields,
                    "inspect": "(()=>{const f=document.querySelector("
                    + json.dumps(selector)
                    + ");sessionStorage.setItem('mvp04f-replay',JSON.stringify({url:f.action,data:[...new FormData(f)]}));return true})()",
                    "description": "retain the browser's own managed submission for exact retry",
                }
            )
            fields = {}
        steps.append(
            {
                "formSelector": selector,
                "fill": fields,
                "clickSelector": button or selector + ' button[type="submit"]',
                "afterPrefix": "/",
            }
        )
        if retry:
            steps.append(
                self.inspect(
                    "(async()=>{const p=JSON.parse(sessionStorage.getItem('mvp04f-replay'));const r=await fetch(p.url,{method:'POST',body:new URLSearchParams(p.data)});return r.status===200})()",
                    "identical browser submission reuses its legitimate existing result",
                )
            )
        self.browser(
            actor,
            [
                self.case(
                    f"{self.sequence:02}-{name}",
                    entry,
                    width=1440,
                    steps=steps,
                    status=200 if expected == 302 else expected,
                    noHttpErrors=expected == 302,
                )
            ],
        )

    def responsive(self, name, path, **kwargs):
        self.browser(
            self.owner,
            [
                self.case(
                    f"{name}-{width}", path, width=width, mobile=width == 390, **kwargs
                )
                for width in (1440, 1024, 390)
            ],
        )

    def denied_post(self, path, data, expected=400):
        return self.inspect(
            "(async()=>{const r=await fetch("
            + json.dumps(path)
            + ",{method:'POST',headers:{'X-CSRFToken':document.cookie.split('; ').find(c=>c.startsWith('csrftoken=')).split('=')[1]},body:new URLSearchParams("
            + json.dumps(data)
            + ")});return r.status==="
            + str(expected)
            + "})()",
            "server denies forged or repeated transition",
        )

    def test_full_new_pr_to_partial_receipts_stock_and_reversal(self):
        self.begin()
        self.open_quotes_and_compare(revise=True)
        award = self.award(["6"])
        self.assertEqual(award.unawarded_quantity, Decimal(4))
        workspace = reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        self.responsive(
            "award-decision", workspace, mustText=["تصمیم نهایی", "مقدار انتخاب‌نشده"]
        )
        order = self.order_from(award, self.supplier)
        self.assertEqual(order.items.get().quantity, Decimal(6))
        first_receipt, first_stock = self.receive_into_stock(order, "2", 1)
        order.refresh_from_db()
        self.assertEqual(order.status, "issued")
        self.assertEqual(self.balance(), Decimal(2))
        second_receipt, second_stock = self.receive_into_stock(order, "4", 2)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")
        self.assertEqual(self.balance(), Decimal(6))
        self.prove_lineage(
            award,
            [order],
            [first_receipt, second_receipt],
            [first_stock, second_stock],
            "canonical",
        )
        # Repeated explicit Issue/Post do not create duplicate versions or facts.
        self.browser(
            self.owner,
            [
                self.case(
                    "critical-repeat-and-refresh",
                    self.stock_detail(second_stock),
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            reverse("procurement:order_issue", args=[order.pk]), {}
                        ),
                        self.denied_post(
                            reverse(
                                "procurement:receipt_post", args=[second_receipt.pk]
                            ),
                            {},
                        ),
                        self.denied_post(
                            reverse(
                                "inventory:transaction_post", args=[second_stock.pk]
                            ),
                            {},
                        ),
                        {"reload": True},
                        {
                            "clickSelector": "[data-inventory-grn]",
                            "afterPath": self.detail_url(second_receipt),
                        },
                        {"history": "back"},
                        {"history": "forward"},
                        {"history": "back"},
                    ],
                )
            ],
        )
        self.assertEqual(order.versions.count(), 1)
        self.assertEqual(self.rfq.versions.count(), 1)
        self.assertEqual(m.SourcingAward.objects.count(), 1)
        self.assertEqual(m.PurchaseOrder.objects.count(), 1)
        self.assertEqual(m.GoodsReceipt.objects.count(), 2)
        self.assertEqual(StockTransaction.objects.count(), 2)
        for record in (first_stock, second_stock):
            self.act(
                self.owner,
                reverse("inventory:transaction_reverse", args=[record.pk]),
                {
                    "reversal_number": f"REV-{record.transaction_number}",
                    "reason": "برگشت تحویل نمونه با حفظ اصل",
                },
                selector='form[aria-label="برگشت گردش انبار"]',
                name="explicit-reversal",
            )
            record.refresh_from_db()
            self.assertEqual(record.status, "reversed")
        self.assertEqual(self.balance(), Decimal(0))
        first_receipt.refresh_from_db()
        second_receipt.refresh_from_db()
        self.assertEqual(first_receipt.status, "posted")
        self.assertEqual(second_receipt.status, "posted")
        self.financial_checkpoint("both-reversals-no-automatic-grn-void")
        (self.evidence_root / "canonical-reversal.json").write_text(
            json.dumps(
                {
                    "balance_before_reversal": "6",
                    "balance_after_reversal": "0",
                    "originals_retained": True,
                    "stock_records": StockTransaction.objects.count(),
                    "grn_statuses": [first_receipt.status, second_receipt.status],
                    "financial_checkpoints": self.financial_checkpoints,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        pages = {
            "pr-list": reverse("procurement:request_list"),
            "pr-detail": reverse("procurement:request_detail", args=[self.pr.pk]),
            "rfq-create": reverse("procurement:rfq_create")
            + f"?purchase_request={self.pr.pk}",
            "rfq-detail": reverse("procurement:rfq_detail", args=[self.rfq.pk]),
            "buyer-workspace": workspace,
            "po-list": reverse("procurement:order_list"),
            "po-detail": reverse("procurement:order_detail", args=[order.pk]),
            "grn-list": reverse("procurement:receipt_list"),
            "grn-detail": self.detail_url(second_receipt),
            "inventory-list": reverse("inventory:transaction_list"),
            "inventory-detail": self.stock_detail(second_stock),
        }
        for name, path in pages.items():
            self.responsive(name, path)
        self.browser(
            self.owner,
            [
                self.case(
                    "forward-lineage-navigation",
                    pages["pr-detail"],
                    steps=[
                        {
                            "clickSelector": "[data-pr-existing-rfq]",
                            "afterPath": pages["rfq-detail"],
                        },
                        {"clickHref": workspace, "afterPath": workspace},
                        {
                            "clickSelector": "[data-award-existing-po]",
                            "afterPath": pages["po-detail"],
                        },
                        {
                            "clickSelector": "[data-po-existing-grn]",
                            "afterPrefix": "/procurement/receipts/",
                        },
                        {
                            "clickSelector": "[data-grn-stock]",
                            "afterPrefix": "/inventory/transactions/",
                        },
                    ],
                )
            ],
        )
        # Data lineage and rendered links must agree across principal pages.
        self.login(self.owner)
        for page, target in (
            (
                self.detail_url(second_receipt),
                reverse("procurement:order_detail", args=[order.pk]),
            ),
            (self.stock_detail(second_stock), self.detail_url(second_receipt)),
            (reverse("procurement:order_detail", args=[order.pk]), workspace),
        ):
            self.assertContains(self.client.get(page), target)
        self.browser(
            self.viewer,
            [
                self.case(
                    "unauthorized-source-create",
                    reverse("procurement:receipt_create"),
                    status=403,
                    noHttpErrors=False,
                )
            ],
        )
        self.browser(
            self.outsider,
            [
                self.case(
                    "wrong-tenant-stock",
                    self.stock_detail(second_stock),
                    status=404,
                    noHttpErrors=False,
                )
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
            reason="MVP-04F fixture scope",
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "wrong-project-grn",
                    self.detail_url(second_receipt),
                    status=404,
                    noHttpErrors=False,
                )
            ],
        )
