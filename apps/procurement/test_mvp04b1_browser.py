"""Installed Chrome RFQ preparation, issue, responsive and isolation evidence."""

from pathlib import Path
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.organizations.models import MembershipScopeGrant
from apps.projects.models import Project
from core.jalali import format_jalali

from .models import PurchaseRequest, RequestForQuotation
from .test_mvp04b_scope import CommercialScopeFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RFQPreparationBrowserTests(CommercialScopeFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04b-ux/preparation-browser"
    )

    def setUp(self):
        super().setUp()
        for row, name in (
            (self.organization, "شرکت ساختمانی نمونه"),
            (self.project, "پروژه سازه نمونه"),
            (self.material, "سیمان پرتلند"),
            (self.unit, "کیسه"),
        ):
            row.name = name
            row.save(update_fields=["name"])
        self.supplier.display_name = "تأمین مصالح پارس"
        self.supplier.save(update_fields=["display_name"])

    def case(self, name, path, **kwargs):
        kwargs["steps"] = [
            *kwargs.get("steps", []),
            self.inspect(
                "!/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}|\\b[a-f0-9]{64}\\b/i.test(document.querySelector('main')?.innerText || '')",
                "no visible UUID or hash",
            ),
        ]
        return {
            "name": name,
            "path": path,
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
            "absentText": [
                "UUID",
                "RFQCommercialScope",
                "object (",
                "کلید یکتا",
                "rfqs.change",
                "پیشنهادهای مهروموم‌شده",
            ],
            **kwargs,
        }

    def inspect(self, expr, description):
        return {"inspect": expr, "description": description}

    def test_end_to_end_rfq_preparation_issue_and_responsive_history(self):
        fixture = self.draft_rfq(items=2, selected=0)
        pr = fixture.purchase_request
        listing = reverse("procurement:rfq_list")
        create = reverse("procurement:rfq_create")
        contextual = create + f"?purchase_request={pr.pk}"
        self.browser(
            self.owner,
            [
                self.case(
                    f"list-{w}",
                    listing,
                    width=w,
                    mobile=w == 390,
                    mustText=["استعلام جدید", "RFQ-SCOPE"],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "list-filter-sort-chips",
                    listing + "?q=RFQ-SCOPE&status=draft&sort=number&direction=asc",
                    mustText=["RFQ-SCOPE"],
                    steps=[
                        self.inspect(
                            "document.querySelectorAll('[data-filter-chip]').length===2 && document.querySelectorAll('main tbody tr').length===1",
                            "filtered result and business summary",
                        )
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    f"contextual-create-{w}",
                    reverse("procurement:request_detail", args=[pr.pk]),
                    width=w,
                    mobile=w == 390,
                    steps=[
                        {"clickSelector": "[data-pr-rfq]", "afterPath": create},
                        self.inspect(
                            f"document.querySelector('[name=purchase_request_id]').type==='hidden' && document.querySelector('[name=purchase_request_id]').value==='{pr.pk}' && !/[a-f0-9]{{8}}-[a-f0-9]{{4}}-/i.test(document.querySelector('main').innerText)",
                            "trusted PR/project preserved without manual UUID",
                        ),
                    ],
                )
                for w in (1440, 1024, 390)
            ],
        )
        dates = {
            "closing_at": format_jalali(fixture.closing_at, include_time=True),
            "earliest_opening_at": format_jalali(
                fixture.earliest_opening_at, include_time=True
            ),
        }
        self.browser(
            self.owner,
            [
                self.case(
                    "create-retains-validation",
                    contextual,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {
                                **dates,
                                "rfq_number": "",
                                "title": "عنوان حفظ‌شده",
                                "terms": "شرایط حفظ‌شده",
                            },
                            "formSelector": 'form[aria-label="استعلام جدید"]',
                            "clickSelector": "main button[type=submit]",
                            "afterPath": create,
                        },
                        self.inspect(
                            "document.querySelector('[name=title]').value==='عنوان حفظ‌شده' && document.querySelector('[name=terms]').value==='شرایط حفظ‌شده' && !!document.querySelector('[role=alert]')",
                            "inline errors retain business values",
                        ),
                    ],
                ),
                self.case(
                    "create-contextual-draft",
                    contextual,
                    steps=[
                        {
                            "fill": {
                                **dates,
                                "rfq_number": "CHROME-RFQ",
                                "title": "خرید سیمان پروژه",
                                "terms": "شرایط نمونه خرید",
                            },
                            "formSelector": 'form[aria-label="استعلام جدید"]',
                            "clickSelector": "main button[type=submit]",
                            "afterPrefix": "/procurement/rfqs/",
                            "mustText": "ابتدا اقلام استعلام",
                        }
                    ],
                ),
            ],
        )
        rfq = RequestForQuotation.objects.get(rfq_number="CHROME-RFQ")
        self.assertEqual(rfq.purchase_request_id, pr.pk)
        self.assertEqual(rfq.project_id, self.project.pk)
        detail = reverse("procurement:rfq_detail", args=[rfq.pk])
        line = reverse("procurement:rfq_line_add", args=[rfq.pk])
        submit = reverse("procurement:rfq_submit", args=[rfq.pk])
        issue = reverse("procurement:rfq_issue", args=[rfq.pk])
        scope = reverse("procurement:rfq_scope_define", args=[rfq.pk])
        self.browser(
            self.owner,
            [
                self.case(
                    f"draft-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    mustText=["انتخاب اقلام از درخواست خرید"],
                    steps=[
                        self.inspect(
                            "!document.querySelector('form[aria-label=\"صدور استعلام\"]')",
                            "draft hides issue",
                        )
                    ],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "line-invalid-retains-selection",
                    detail,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {"toggleSelector": ".rfq-config__line-add > summary"},
                        {
                            "searchChoice": {
                                "name": "purchase_request_item_id",
                                "query": "سیمان",
                                "value": str(self.source[0].pk),
                            }
                        },
                        {
                            "fill": {"quantity": "11", "description": "شرح قلم حفظ‌شده"},
                            "formSelector": f'form[action="{line}"]',
                            "clickSelector": f'form[action="{line}"] button[type=submit]',
                            "afterPath": line,
                        },
                        self.inspect(
                            f"document.querySelector('[name=purchase_request_item_id]').value==='{self.source[0].pk}' && document.querySelector('[name=description]').value==='شرح قلم حفظ‌شده'",
                            "quantity error retains eligible PR-line choice",
                        ),
                    ],
                ),
                self.case(
                    "line-select-add",
                    detail,
                    steps=[
                        {"toggleSelector": ".rfq-config__line-add > summary"},
                        {
                            "searchChoice": {
                                "name": "purchase_request_item_id",
                                "query": "سیمان",
                                "value": str(self.source[0].pk),
                            }
                        },
                        {
                            "fill": {"quantity": "7", "description": "سیمان فونداسیون"},
                            "formSelector": f'form[action="{line}"]',
                            "clickSelector": f'form[action="{line}"] button[type=submit]',
                            "afterPath": detail,
                            "mustText": "سیمان فونداسیون",
                        },
                    ],
                ),
            ],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "explicit-scope-and-submit",
                    detail,
                    steps=[
                        {"clickSelector": "[data-scope-define]", "afterPath": scope},
                        {
                            "fill": {
                                "scope_type": "line",
                                "scope_code": "خرید سیمان",
                                "select_0": True,
                                "member_0": "7",
                                "independently_awardable": "yes",
                                "allows_split_award": "no",
                                "allows_alternates": "no",
                            },
                            "formSelector": 'form[aria-label="تنظیم گروه خرید"]',
                            "clickSelector": "button[value=append]",
                            "afterPath": scope,
                            "mustText": "تنظیمات نسخه جاری",
                        },
                        {"reload": True, "afterPath": scope},
                        {"clickHref": detail, "afterPath": detail},
                        {
                            "clickSelector": f'form[action="{submit}"] button[type=submit]',
                            "afterPath": detail,
                            "mustText": "تأمین‌کنندگان دعوت‌شونده",
                        },
                        self.inspect(
                            "!document.querySelector('form[aria-label=\"افزودن قلم استعلام\"]') && !!document.querySelector('form[aria-label=\"صدور استعلام\"]')",
                            "submitted state offers suppliers and issue",
                        ),
                    ],
                )
            ],
        )
        self.browser(
            self.owner,
            [
                self.case(
                    f"supplier-selection-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    mustText=["تأمین مصالح پارس"],
                    steps=[
                        self.inspect(
                            "document.querySelector('[name=idempotency_key]').type==='hidden' && [...document.querySelectorAll('main input:not([type=hidden]),main textarea')].every(e=>!['idempotency_key','supplier_ids'].includes(e.name)||e.type==='checkbox')",
                            "supplier choices business labelled; retry key internal",
                        )
                    ],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "issue-supplier-required",
                    detail,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "clickSelector": f'form[action="{issue}"] button[type=submit]',
                            "afterPath": issue,
                        }
                    ],
                ),
                self.case(
                    "issue-key-error-retains-supplier",
                    detail,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {"supplier_ids": True, "idempotency_key": ""},
                            "formSelector": f'form[action="{issue}"]',
                            "clickSelector": f'form[action="{issue}"] button[type=submit]',
                            "afterPath": issue,
                        },
                        self.inspect(
                            "document.querySelector('[name=supplier_ids]').checked && document.body.innerText.includes('اطلاعات فرم معتبر نیست')",
                            "invalid managed field fails closed and retains supplier selection",
                        ),
                    ],
                ),
                self.case(
                    "issue-freezes-scope-and-invitations",
                    detail,
                    steps=[
                        {
                            "fill": {"supplier_ids": True},
                            "formSelector": f'form[action="{issue}"]',
                            "clickSelector": f'form[action="{issue}"] button[type=submit]',
                            "afterPath": detail,
                            "mustText": "تنظیمات نسخه جاری",
                        }
                    ],
                ),
            ],
        )
        rfq.refresh_from_db()
        self.assertEqual(rfq.status, "issued")
        first = rfq.versions.get()
        self.assertEqual(first.lines.get().quantity, 7)
        self.assertEqual(first.commercial_scopes.get().required_quantity, 7)
        self.assertEqual(first.invitations.get().supplier_id, self.supplier.pk)
        self.browser(
            self.owner,
            [
                self.case(
                    f"issued-readonly-{w}",
                    detail,
                    width=w,
                    mobile=w == 390,
                    mustText=["تنظیمات نسخه جاری", "تأمین مصالح پارس"],
                    steps=[
                        self.inspect(
                            "!document.querySelector('form[aria-label=\"افزودن قلم استعلام\"]') && !document.querySelector('form[aria-label=\"صدور استعلام\"]')",
                            "issued content frozen and no preparation mutation",
                        ),
                        {"toggleSelector": "header .erp-list-row-menu summary"},
                    ],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "addendum-navigation-back-refresh",
                    detail,
                    steps=[
                        {"toggleSelector": "header .erp-list-row-menu summary"},
                        {
                            "clickHref": reverse(
                                "procurement:rfq_addendum", args=[rfq.pk]
                            ),
                            "afterPath": reverse(
                                "procurement:rfq_addendum", args=[rfq.pk]
                            ),
                        },
                        {"history": "back"},
                        {"reload": True, "afterPath": detail},
                        self.inspect(
                            "document.body.innerText.includes('تنظیمات نسخه جاری')",
                            "Back and refresh preserve issued version",
                        ),
                    ],
                )
            ],
        )
        self.assertEqual(rfq.versions.count(), 1)
        self.browser(
            self.owner,
            [
                self.case(
                    f"general-create-{w}",
                    create,
                    width=w,
                    mobile=w == 390,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "purchase_request_id",
                                "query": "PR-SCOPE",
                                "value": str(pr.pk),
                            }
                        },
                        self.inspect(
                            f"document.querySelector('[name=purchase_request_id]').value==='{pr.pk}'",
                            "searchable approved PR selector",
                        ),
                    ],
                )
                for w in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "general-create-save",
                    create,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "purchase_request_id",
                                "query": "PR-SCOPE",
                                "value": str(pr.pk),
                            }
                        },
                        {
                            "fill": {
                                **dates,
                                "rfq_number": "GENERAL-RFQ",
                                "title": "استعلام عمومی",
                            },
                            "formSelector": 'form[aria-label="استعلام جدید"]',
                            "clickSelector": "main button[type=submit]",
                            "afterPrefix": "/procurement/rfqs/",
                            "mustText": "استعلام عمومی",
                        },
                    ],
                )
            ],
        )
        general = RequestForQuotation.objects.get(rfq_number="GENERAL-RFQ")
        self.assertEqual(general.purchase_request_id, pr.pk)

    def test_browser_denials_and_forged_context(self):
        rfq = self.draft_rfq()
        detail = reverse("procurement:rfq_detail", args=[rfq.pk])
        create = reverse("procurement:rfq_create")
        contextual = create + f"?purchase_request={rfq.purchase_request_id}"
        foreign_pr = PurchaseRequest.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            request_number="OTHER-PR",
            title="درخواست شرکت دیگر",
            status="approved",
            created_by=self.outsider,
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "forged-hidden-pr-rejected",
                    contextual,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {
                                "purchase_request_id": str(uuid4()),
                                "rfq_number": "FORGED",
                                "title": "عنوان حفظ‌شده",
                                "closing_at": format_jalali(
                                    rfq.closing_at, include_time=True
                                ),
                                "earliest_opening_at": format_jalali(
                                    rfq.earliest_opening_at, include_time=True
                                ),
                            },
                            "formSelector": 'form[aria-label="استعلام جدید"]',
                            "clickSelector": "main button[type=submit]",
                            "afterPath": create,
                            "mustText": "هم‌خوان نیست",
                        }
                    ],
                ),
                self.case(
                    "foreign-tenant-reference",
                    create + f"?purchase_request={foreign_pr.pk}",
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )
        self.assertFalse(
            RequestForQuotation.objects.filter(rfq_number="FORGED").exists()
        )
        self.login(self.viewer)
        self.browser(
            self.viewer,
            [
                self.case(
                    "viewer-readonly",
                    detail,
                    steps=[
                        self.inspect(
                            "!document.querySelector('main form[method=post]') && !document.querySelector('[data-scope-define]')",
                            "viewer sees no mutation actions",
                        )
                    ],
                ),
                self.case(
                    "viewer-create-denied", create, status=403, noHttpErrors=False
                ),
                self.case(
                    "viewer-scope-denied",
                    reverse("procurement:rfq_scope_define", args=[rfq.pk]),
                    status=403,
                    noHttpErrors=False,
                ),
            ],
        )
        membership = self.organization.memberships.get(user=self.owner)
        MembershipScopeGrant.objects.filter(membership=membership).update(
            revoked_at=timezone.now()
        )
        project = Project.objects.create(
            organization=self.organization, code="OTHER-SCOPE", name="پروژه محدود دیگر"
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=project,
            reason="browser fixture",
        )
        self.browser(
            self.owner,
            [
                self.case(
                    "wrong-project-detail", detail, status=404, noHttpErrors=False
                ),
                self.case(
                    "wrong-project-contextual-create",
                    contextual,
                    status=404,
                    noHttpErrors=False,
                ),
            ],
        )
