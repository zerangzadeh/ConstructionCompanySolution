"""Installed Chrome evidence for the bounded Award → PO journey.

Source opening/processing data are inherited synthetic test fixtures only.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import BusinessPermissionCode as P
from apps.organizations.models import MembershipScopeGrant
from apps.organizations.services import set_active_organization
from apps.procurement import comparison_services as commercial
from apps.procurement import models as m
from apps.procurement import test_mvp04b2_browser as browser_fixture
from apps.procurement import test_mvp04c as fixture
from apps.procurement.test_p5_s11_comparison_award import P5S11TwoRevisionFixtureMixin
from apps.projects.models import Project
from core.jalali import format_jalali


class BrowserMixin(browser_fixture.BrowserMixin):
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04c/browser"
    )

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(
            session,
            self.other_organization
            if actor.pk == self.outsider.pk
            else self.organization,
        )
        session.save()

    def post_step(
        self,
        fill,
        after_path=None,
        after_prefix=None,
        selector='form[aria-label="سفارش از انتخاب نهایی"]',
        must_text=None,
    ):
        return {
            "fill": fill,
            "formSelector": selector,
            "clickSelector": selector + " button[type=submit]",
            **({"afterPath": after_path} if after_path else {}),
            **({"afterPrefix": after_prefix} if after_prefix else {}),
            **({"mustText": must_text} if must_text else {}),
        }

    def source_fields(self, number="PO-BROWSER", **values):
        return {
            "allocations": True,
            "order_number": number,
            "order_date": format_jalali(date(2026, 11, 2)),
            "notes": "یادداشت حفظ‌شده",
            **values,
        }

    def denied_post(self, url, data):
        import json

        return self.inspect(
            "(async()=>{const response=await fetch("
            + json.dumps(url)
            + ",{method:'POST',headers:{'X-CSRFToken':document.cookie.split('; ').find(c=>c.startsWith('csrftoken=')).split('=')[1]},body:new URLSearchParams("
            + json.dumps(data)
            + ")});const parsed=new DOMParser().parseFromString(await response.text(),'text/html');const main=parsed.querySelector('main');return response.status===400 && !!main && !/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}|\\b[a-f0-9]{64}\\b/i.test(main.textContent)})()",
            "forged consumption denied without technical identity leakage",
        )

    def source_case(self, name, path, **kwargs):
        return self.case(name, path, **kwargs)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PurchaseOrderBrowserTests(
    BrowserMixin, fixture.OrderJourneyFixture, StaticLiveServerTestCase
):
    def test_source_to_issued_order_context_and_safety(self):
        award = self.award("4")
        self.supplier.display_name = "تأمین مصالح پارس"
        self.supplier.save(update_fields=["display_name"])
        self.project.name = "پروژه سازه نمونه"
        self.project.save(update_fields=["name"])
        self.material.name = "سیمان پرتلند"
        self.material.save(update_fields=["name"])
        source = self.source_url(award)
        source_path = source.split("?")[0]
        workspace = reverse("procurement:rfq_buyer_workspace", args=[self.rfq.pk])
        self.assertFalse(m.PurchaseOrder.objects.exists())
        self.browser(
            self.preparer,
            [
                self.case(
                    "award-contextual-po-entry",
                    workspace,
                    steps=[
                        {"clickSelector": "[data-award-po]", "afterPath": source_path},
                        self.inspect(
                            f"['award','project','supplier'].every(n=>document.querySelector('main [name='+n+']').type==='hidden') && document.querySelector('main [name=supplier]').value==='{self.supplier.pk}' && !document.querySelector('main input[name=quantity]') && !document.querySelector('main input[name=unit_price]')",
                            "server inherited source/supplier/project; no manual awarded quantities",
                        ),
                    ],
                )
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    f"source-create-{w}",
                    source,
                    width=w,
                    mobile=w == 390,
                    mustText=["تأمین مصالح پارس", "پروژه سازه نمونه", "باقی‌مانده"],
                )
                for w in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "source-validation-retention",
                    source,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.post_step(
                            self.source_fields(order_number=""), after_path=source_path
                        ),
                        self.inspect(
                            "document.querySelector('[name=notes]').value==='یادداشت حفظ‌شده' && document.querySelector('[name=allocations]').checked && !!document.querySelector('.errorlist,[role=alert]')",
                            "source choices and business inputs retained",
                        ),
                    ],
                ),
                self.case(
                    "source-excess-quantity-denied",
                    source,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.inspect(
                            "(()=>{let i=document.createElement('input');i.type='hidden';i.name='quantity';i.value='100';document.querySelector('form[aria-label=\"سفارش از انتخاب نهایی\"]').append(i);return true})()",
                            "forged quantity injection",
                        ),
                        self.post_step(
                            self.source_fields("EXCESS-DENIED"), after_path=source_path
                        ),
                    ],
                ),
                self.case(
                    "forged-supplier-denied",
                    source,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.post_step(
                            self.source_fields(
                                "FORGED-SUPPLIER", supplier=str(self.other_supplier.pk)
                            ),
                            after_path=source_path,
                        )
                    ],
                ),
                self.case(
                    "forged-project-denied",
                    source,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.post_step(
                            self.source_fields(
                                "FORGED-PROJECT", project=str(self.other_project.pk)
                            ),
                            after_path=source_path,
                        )
                    ],
                ),
                self.case(
                    "forged-allocation-denied",
                    source,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.inspect(
                            f"(()=>{{document.querySelector('main [name=allocations]').value='{self.other_project.pk}';return true}})()",
                            "out-of-source allocation injection",
                        ),
                        self.post_step(
                            self.source_fields("FORGED-ALLOCATION"),
                            after_path=source_path,
                        ),
                    ],
                ),
            ],
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())
        self.browser(
            self.preparer,
            [
                self.case(
                    "single-partial-award-po-draft",
                    source,
                    steps=[
                        self.post_step(
                            self.source_fields(),
                            after_prefix="/procurement/orders/",
                            must_text="اقلام سفارش خرید",
                        ),
                        {"reload": True},
                        {"history": "back"},
                        {"history": "forward"},
                    ],
                )
            ],
        )
        order = m.PurchaseOrder.objects.get(order_number="PO-BROWSER")
        self.assertEqual(order.items.get().quantity, Decimal(4))
        self.assertEqual(
            order.items.get().source_award_allocation_id, award.allocations.get().pk
        )
        self.assertEqual(order.status, "draft")
        self.assertFalse(m.GoodsReceipt.objects.exists())
        self.browser(
            self.preparer,
            [
                self.case(
                    "duplicate-allocation-consumption-denied",
                    source,
                    noHttpErrors=False,
                    steps=[
                        self.denied_post(
                            source,
                            {
                                "award": str(award.pk),
                                "supplier": str(self.supplier.pk),
                                "project": str(self.project.pk),
                                "allocations": str(award.allocations.get().pk),
                                "order_number": "PO-DUPLICATE",
                                "order_date": format_jalali(date(2026, 11, 2)),
                            },
                        )
                    ],
                )
            ],
        )
        self.assertEqual(m.PurchaseOrder.objects.count(), 1)
        detail = reverse("procurement:order_detail", args=[order.pk])
        self.browser(
            self.preparer,
            [
                self.case(
                    f"draft-detail-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    mustText=["از انتخاب نهایی تأمین‌کننده", "نسخه پیشنهاد"],
                    steps=[
                        self.inspect(
                            "!!document.querySelector('[data-po-issue]') && !document.querySelector('form[action$=\"/items/\"]')",
                            "sourced rows cannot be manually appended",
                        )
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "issue-po-explicit-action",
                    detail,
                    steps=[
                        {
                            "clickSelector": "[data-po-issue]",
                            "afterPath": detail,
                            "mustText": "سفارش صادر شده است",
                        }
                    ],
                )
            ],
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "issued")
        self.assertEqual(order.current_version.source_award_id, award.pk)
        self.assertEqual(
            order.current_version.lines.get().award_allocation_id,
            award.allocations.get().pk,
        )
        self.assertEqual(order.versions.count(), 1)
        self.browser(
            self.preparer,
            [
                self.case(
                    f"issued-detail-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    mustText=["نسخه‌ها و سوابق صدور", "فقط خواندنی"],
                    steps=[
                        self.inspect(
                            "!document.querySelector('[data-po-issue]') && !document.querySelector('form[action$=\"/items/\"]') && !!document.querySelector('[data-po-grn]')",
                            "issued evidence is read-only; GRN is separate navigation",
                        )
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )
        receipt = reverse("procurement:receipt_create")
        self.browser(
            self.preparer,
            [
                self.case(
                    f"issued-po-grn-entry-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    steps=[
                        {"clickSelector": "[data-po-grn]", "afterPath": receipt},
                        self.inspect(
                            f"document.querySelector('main [name=purchase_order]').type==='hidden' && document.querySelector('main [name=purchase_order]').value==='{order.pk}' && document.querySelector('main').innerText.includes('PO-BROWSER')",
                            "existing GRN Create inherits the exact issued PO",
                        ),
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )
        self.assertFalse(m.GoodsReceipt.objects.exists())
        self.browser(
            self.viewer,
            [
                self.case(
                    "unauthorized-po-create",
                    reverse("procurement:order_create"),
                    status=403,
                    noHttpErrors=False,
                ),
                self.case(
                    "unauthorized-source-entry", source, status=403, noHttpErrors=False
                ),
            ],
        )
        self.browser(
            self.outsider,
            [
                self.case(
                    "wrong-tenant-po-detail", detail, status=404, noHttpErrors=False
                ),
                self.case(
                    "wrong-tenant-award-source", source, status=404, noHttpErrors=False
                ),
            ],
        )
        member = self.organization.memberships.get(user=self.preparer)
        MembershipScopeGrant.objects.filter(membership=member).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="LIMIT", name="پروژه مجاز دیگر"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=member,
            scope_type="project",
            project=project,
            reason="scope fixture",
        )
        self.browser(
            self.preparer,
            [
                self.case(
                    "wrong-project-po-detail", detail, status=404, noHttpErrors=False
                ),
                self.case(
                    "wrong-project-source", source, status=404, noHttpErrors=False
                ),
            ],
        )

    def test_fixed_source_project_and_final_create_visuals(self):
        award = self.award()
        source = self.source_url(award)
        self.browser(
            self.preparer,
            [
                self.case(
                    f"fixed-source-create-{w}",
                    source,
                    width=w,
                    mobile=w == 390,
                    steps=[
                        self.inspect(
                            "document.querySelector('[data-inherited-context] [data-create-project-context]').textContent.trim().length>0 && !document.querySelector('main').innerText.includes('انتخاب پروژه در فرم')",
                            "the inherited project is shown in the accepted Create header",
                        )
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())

    def test_legacy_direct_flow_list_and_responsive_patterns(self):
        self.supplier.display_name = "بازرگانی سازه پارس"
        self.supplier.save(update_fields=["display_name"])
        self.material.name = "سیمان تیپ دو"
        self.material.save(update_fields=["name"])
        create = reverse("procurement:order_create")
        self.browser(
            self.owner,
            [
                self.case(
                    f"legacy-create-{w}",
                    create,
                    width=w,
                    mobile=w == 390,
                    mustText=["سفارش خرید جدید", "ثبت مستقیم"],
                )
                for w in (1440, 1024, 390)
            ],
        )
        fields = {
            "project": str(self.project.pk),
            "supplier": str(self.supplier.pk),
            "order_number": "PO-DIRECT-BROWSER",
            "order_date": format_jalali(date(2026, 11, 2)),
            "notes": "سفارش مستقیم",
        }
        self.browser(
            self.owner,
            [
                self.case(
                    "legacy-create-retention",
                    create,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        self.post_step(
                            {**fields, "order_date": ""},
                            after_path=create,
                            selector='form[aria-label="سفارش خرید جدید"]',
                        ),
                        self.inspect(
                            "document.querySelector('main [name=notes]').value==='سفارش مستقیم' && !!document.querySelector('.errorlist,[role=alert]')",
                            "legacy values retained",
                        ),
                    ],
                ),
                self.case(
                    "legacy-create-draft",
                    create,
                    steps=[
                        self.post_step(
                            fields,
                            after_prefix="/procurement/orders/",
                            must_text="اقلام سفارش خرید",
                            selector='form[aria-label="سفارش خرید جدید"]',
                        )
                    ],
                ),
            ],
        )
        order = m.PurchaseOrder.objects.get(order_number="PO-DIRECT-BROWSER")
        self.assertIsNone(order.source_award_id)
        detail = reverse("procurement:order_detail", args=[order.pk])
        self.browser(
            self.owner,
            [
                self.case(
                    "legacy-line-entry-and-issue",
                    detail,
                    steps=[
                        self.post_step(
                            {
                                "material": str(self.material.pk),
                                "quantity": "2",
                                "unit_price": "20",
                            },
                            after_path=detail,
                            selector='form[action$="/items/"]',
                        ),
                        {
                            "clickSelector": "[data-po-issue]",
                            "afterPath": detail,
                            "mustText": "سفارش صادر شده است",
                        },
                    ],
                )
            ],
        )
        order.refresh_from_db()
        self.assertEqual(order.status, "issued")
        self.assertIsNone(order.current_version.source_award_id)
        m.PurchaseOrder.objects.bulk_create(
            [
                m.PurchaseOrder(
                    organization=self.organization,
                    project=self.project,
                    supplier=self.supplier,
                    order_number=f"PO-LIST-{i:02}",
                    order_date=date(2026, 11, 2),
                    created_by=self.owner,
                    updated_by=self.owner,
                )
                for i in range(30)
            ]
        )
        listing = reverse("procurement:order_list")
        self.browser(
            self.owner,
            [
                self.case(
                    f"po-list-{w}",
                    listing,
                    width=w,
                    mobile=w == 390,
                    mustText=["سفارش خرید جدید", "ثبت مستقیم / سابقه"],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "list-filter-sort-chips",
                    listing + "?q=PO-LIST&status=draft&sort=number&direction=asc",
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('[data-filter-chip]').length===2 && document.querySelector('main tbody tr').innerText.includes('PO-LIST-00')",
                            "real search/status chips and allowlisted sort",
                        )
                    ],
                ),
                self.case(
                    "list-pagination-second-page",
                    listing + "?q=PO-LIST&sort=number&direction=asc",
                    steps=[
                        {
                            "clickSelector": 'main a[href*="page=2"]',
                            "afterPath": listing,
                        }
                    ],
                ),
            ],
        )
        self.assertFalse(m.GoodsReceipt.objects.exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SplitAwardPOBrowserTests(
    BrowserMixin, P5S11TwoRevisionFixtureMixin, StaticLiveServerTestCase
):
    def test_split_award_keeps_supplier_specific_drafts_and_remaining_allocations(self):
        self.rfq = self.revision.envelope.rfq
        for code in (
            P.PURCHASE_ORDERS_CREATE,
            P.PURCHASE_ORDERS_VIEW,
            P.PURCHASE_ORDERS_ISSUE,
        ):
            self._grant(code, self.preparer)
        comparison = self._two_comparison()
        appointment = commercial.appoint_evaluator(
            organization=self.organization,
            actor=self.preparer,
            comparison=comparison,
            membership=self.organization.memberships.get(user=self.preparer),
        )
        for item in comparison.inputs.all():
            commercial.evaluate_comparison(
                organization=self.organization,
                actor=self.preparer,
                appointment=appointment,
                input=item,
                recommendation="بررسی مصوب",
                evidence="شاهد بررسی",
            )
        final = commercial.finalize_comparison(
            organization=self.organization,
            actor=self.approver,
            comparison=comparison,
            reason="نهایی",
        )
        inputs = list(final.inputs.order_by("created_at"))
        prepared = commercial.prepare_sourcing_award(
            organization=self.organization,
            actor=self.preparer,
            comparison=final,
            outcome="awarded",
            allocations=[
                {"comparison_input_id": str(item.pk), "quantity": str(q)}
                for item, q in zip(inputs, (4, 6), strict=True)
            ],
            reason="خرید چند تأمین‌کننده",
            evidence="صورت‌جلسه",
            idempotency_key="split-to-po",
        )
        award = commercial.finalize_sourcing_award(
            organization=self.organization, actor=self.approver, preparation=prepared
        )
        self.assertFalse(m.PurchaseOrder.objects.exists())
        root = reverse("procurement:order_from_award", args=[award.pk])
        self.browser(
            self.preparer,
            [
                self.case(
                    "split-supplier-selection",
                    root,
                    mustText=["تأمین‌کننده سفارش را انتخاب کنید"],
                )
            ],
        )
        for index, item in enumerate(inputs, 1):
            supplier = item.quote_revision.envelope.supplier
            url = root + f"?supplier={supplier.pk}"
            self.browser(
                self.preparer,
                [
                    self.case(
                        f"split-supplier-{index}-draft",
                        url,
                        steps=[
                            self.post_step(
                                self.source_fields(f"PO-SPLIT-{index}"),
                                after_prefix="/procurement/orders/",
                                must_text="اقلام سفارش خرید",
                            )
                        ],
                    )
                ],
            )
            order = m.PurchaseOrder.objects.get(order_number=f"PO-SPLIT-{index}")
            self.assertEqual(order.supplier_id, supplier.pk)
            self.assertEqual(
                order.items.get().quantity,
                award.allocations.get(comparison_input=item).quantity,
            )
            self.assertEqual(order.items.count(), 1)
            if index == 1:
                other = award.allocations.exclude(comparison_input=item).get()
                self.browser(
                    self.preparer,
                    [
                        self.case(
                            "split-wrong-supplier-allocation-denial",
                            url,
                            noHttpErrors=False,
                            steps=[
                                self.denied_post(
                                    url,
                                    {
                                        "award": str(award.pk),
                                        "supplier": str(supplier.pk),
                                        "project": str(self.project.pk),
                                        "allocations": str(other.pk),
                                        "order_number": "WRONG-SUPPLIER",
                                        "order_date": format_jalali(date(2026, 11, 2)),
                                    },
                                )
                            ],
                        )
                    ],
                )
        self.assertEqual(m.PurchaseOrder.objects.count(), 2)
        self.browser(
            self.preparer,
            [
                self.case(
                    "split-all-consumed-remaining-zero",
                    root,
                    steps=[
                        self.inspect(
                            "[...document.querySelectorAll('main a')].filter(a=>a.textContent.includes('ایجاد سفارش خرید')).length===0",
                            "no unconsumed allocation remains for another draft",
                        )
                    ],
                )
            ],
        )
        self.assertFalse(m.GoodsReceipt.objects.exists())
