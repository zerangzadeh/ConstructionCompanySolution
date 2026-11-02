"""Installed Chrome proof for explicit scope definition, issue and addenda."""

from datetime import timedelta
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from core.jalali import format_jalali

from .models import RequestForQuotationVersion
from .rfq_services import submit_rfq_for_issue
from .test_mvp04b_scope import CommercialScopeFixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ScopeBrowserTests(CommercialScopeFixture, StaticLiveServerTestCase):
    serialized_rollback = True
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-04b/browser"
    )

    def case(self, name, path, **kwargs):
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
                "کلید یکتای",
                "rfqs.change",
            ],
            **kwargs,
        }

    def test_explicit_scope_issue_addendum_and_responsive_denials(self):
        rfq = self.draft_rfq()
        for row, name in (
            (self.organization, "شرکت ساختمانی نمونه"),
            (self.project, "پروژه نمونه سازه"),
            (self.material, "سیمان پرتلند"),
            (self.unit, "کیسه"),
        ):
            row.name = name
            row.save(update_fields=["name"])
        scope_url = reverse("procurement:rfq_scope_define", args=[rfq.pk])
        detail_url = reverse("procurement:rfq_detail", args=[rfq.pk])
        issue_url = reverse("procurement:rfq_issue", args=[rfq.pk])
        addendum_url = reverse("procurement:rfq_addendum", args=[rfq.pk])
        submit_rfq_for_issue(organization=self.organization, actor=self.owner, rfq=rfq)
        self.browser(
            self.owner,
            [
                self.case(
                    f"scope-empty-{width}",
                    scope_url,
                    width=width,
                    mobile=width == 390,
                    mustText=["درخواست خرید تأییدشده مبنا", "سیمان پرتلند"],
                    steps=[
                        {
                            "inspect": "['scope_type','independently_awardable','allows_split_award','allows_alternates'].every(n=>document.querySelector('[name='+n+']').value==='') && !/[a-f0-9]{8}-[a-f0-9]{4}-/i.test(document.querySelector('main').innerText)",
                            "description": "no silently chosen structure or policy and no visible UUID",
                        }
                    ],
                )
                for width in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "issue-blocked-without-scope",
                    detail_url,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {"supplier_ids": True},
                            "formSelector": f"form[action='{issue_url}']",
                            "clickSelector": f"form[action='{issue_url}'] button",
                            "afterPath": issue_url,
                            "mustText": "صریحاً تعریف",
                        },
                    ],
                ),
                self.case(
                    "scope-invalid-retains-values",
                    scope_url,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": {
                                "scope_type": "line",
                                "scope_code": "خرید سیمان",
                                "member_0": "5",
                                "independently_awardable": "no",
                                "allows_split_award": "yes",
                                "allows_alternates": "no",
                            },
                            "formSelector": "form[aria-label='تعریف دامنه خرید']",
                            "clickSelector": "button[value=append]",
                            "afterPath": scope_url,
                        },
                        {
                            "inspect": "document.querySelector('[name=scope_code]').value==='خرید سیمان' && document.querySelector('[name=member_0]').value==='5' && !!document.querySelector('[role=alert]')",
                            "description": "server rule failure retains explicit business choices",
                        },
                    ],
                ),
                self.case(
                    "scope-save-explicit",
                    scope_url,
                    steps=[
                        {
                            "fill": {
                                "scope_type": "line",
                                "scope_code": "خرید سیمان",
                                "member_0": "5",
                                "independently_awardable": "yes",
                                "allows_split_award": "no",
                                "allows_alternates": "no",
                            },
                            "formSelector": "form[aria-label='تعریف دامنه خرید']",
                            "clickSelector": "button[value=append]",
                            "afterPath": scope_url,
                            "mustText": "دامنه‌های ثبت‌شده",
                        },
                    ],
                ),
                self.case(
                    "issue-pins-scope",
                    detail_url,
                    steps=[
                        {
                            "fill": {"supplier_ids": True},
                            "formSelector": f"form[action='{issue_url}']",
                            "clickSelector": f"form[action='{issue_url}'] button",
                            "afterPath": detail_url,
                            "mustText": "دامنه تثبیت‌شده",
                        },
                    ],
                ),
            ],
        )
        rfq.refresh_from_db()
        first = rfq.versions.get(version_number=1)
        self.assertEqual(first.commercial_scopes.get().required_quantity, 5)
        old_definition = first.commercial_scope_definition_id
        dates = {
            "closing_at": format_jalali(
                rfq.closing_at + timedelta(days=1), include_time=True
            ),
            "earliest_opening_at": format_jalali(
                rfq.earliest_opening_at + timedelta(days=1), include_time=True
            ),
            "terms": "اصلاح شرایط نسخه دوم",
        }
        self.browser(
            self.owner,
            [
                self.case(
                    "addendum-blocked-without-new-definition",
                    addendum_url,
                    status=400,
                    noHttpErrors=False,
                    steps=[
                        {
                            "fill": dates,
                            "formSelector": "form[aria-label='صدور الحاقیه']",
                            "clickSelector": "form[aria-label='صدور الحاقیه'] button[type=submit]",
                            "afterPath": addendum_url,
                            "mustText": "صریحاً تعریف",
                        }
                    ],
                ),
                self.case(
                    "scope-v2-save",
                    scope_url,
                    mobile=True,
                    steps=[
                        {
                            "fill": {
                                "scope_type": "line",
                                "scope_code": "خرید سیمان نسخه دوم",
                                "member_0": "2",
                                "independently_awardable": "yes",
                                "allows_split_award": "no",
                                "allows_alternates": "yes",
                            },
                            "formSelector": "form[aria-label='تعریف دامنه خرید']",
                            "clickSelector": "button[value=append]",
                            "afterPath": scope_url,
                        },
                    ],
                ),
            ]
            + [
                self.case(
                    f"addendum-{width}", addendum_url, width=width, mobile=width == 390
                )
                for width in (1440, 1024, 390)
            ]
            + [
                self.case(
                    "addendum-pins-new-scope",
                    addendum_url,
                    steps=[
                        {
                            "fill": dates,
                            "formSelector": "form[aria-label='صدور الحاقیه']",
                            "clickSelector": "form[aria-label='صدور الحاقیه'] button[type=submit]",
                            "afterPath": detail_url,
                            "mustText": "خرید سیمان نسخه دوم",
                        },
                    ],
                ),
            ],
        )
        self.assertEqual(RequestForQuotationVersion.objects.filter(rfq=rfq).count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.commercial_scope_definition_id, old_definition)
        self.assertEqual(first.commercial_scopes.get().required_quantity, 5)
        self.assertEqual(
            rfq.versions.get(version_number=2)
            .commercial_scopes.get()
            .required_quantity,
            2,
        )
        self.login(self.viewer)
        denied = self.client.get(scope_url).status_code
        self.assertIn(denied, (403, 404))
        self.browser(
            self.viewer,
            [
                self.case(
                    "viewer-scope-denied", scope_url, status=denied, noHttpErrors=False
                )
            ],
        )
