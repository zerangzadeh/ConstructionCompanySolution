"""Create form acceptance: real Chrome, existing services and scope boundaries."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.organizations.models import Organization
from apps.parties.models import BusinessParty
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractCreateReferenceTests(JourneyFixture, TestCase):
    def setUp(self):
        self.make_fixture(persian=True)
        self.login(self.owner)
        self.url = reverse("contracts:create")

    def payload(self, **overrides):
        return {
            "project": str(self.project.pk),
            "party": str(self.party.pk),
            "contract_number": "REF-CREATE",
            "title": "قرارداد اجرای سازه",
            "direction": "receivable",
            "contract_type": "client",
            "status": "draft",
            "contract_value": "125000000.25",
            "signed_at": "۱۴۰۵/۰۶/۲۳",
            "start_date": "۱۴۰۵/۰۷/۰۱",
            "end_date": "۱۴۰۵/۱۲/۲۵",
            "notes": "یادداشت قرارداد",
            **overrides,
        }

    def test_valid_create_retains_every_existing_value_and_redirect(self):
        response = self.client.post(self.url, self.payload())
        contract = Contract.objects.get(contract_number="REF-CREATE")
        self.assertRedirects(response, reverse("contracts:detail", args=[contract.pk]))
        self.assertEqual(contract.organization, self.organization)
        self.assertEqual(contract.project, self.project)
        self.assertEqual(contract.party, self.party)
        self.assertEqual(contract.counterparty_name, self.party.display_name)
        self.assertEqual(contract.title, "قرارداد اجرای سازه")
        self.assertEqual(contract.direction, "receivable")
        self.assertEqual(contract.contract_type, "client")
        self.assertEqual(contract.contract_value, Decimal("125000000.25"))
        self.assertEqual(contract.signed_at, date(2026, 9, 14))
        self.assertEqual(contract.start_date, date(2026, 9, 23))
        self.assertEqual(contract.end_date, date(2027, 3, 16))
        self.assertEqual(contract.status, "draft")
        self.assertEqual(contract.notes, "یادداشت قرارداد")

    def test_required_errors_are_associated_and_no_write_occurs(self):
        count = Contract.objects.count()
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        for name in (
            "project",
            "party",
            "contract_number",
            "title",
            "status",
            "contract_value",
        ):
            self.assertIn(name, response.context["form"].errors)
            self.assertContains(response, f'id="id_{name}-errors"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertEqual(Contract.objects.count(), count)

    def test_invalid_amount_dates_and_order_preserve_existing_validation(self):
        for overrides, expected in (
            ({"contract_value": "1.234"}, "contract_value"),
            ({"signed_at": "۱۴۰۵/۱۳/۰۱"}, "signed_at"),
            ({"end_date": "۱۴۰۵/۰۶/۰۱"}, "__all__"),
            ({"status": "not-a-status"}, "status"),
        ):
            with self.subTest(overrides=overrides):
                response = self.client.post(self.url, self.payload(**overrides))
                self.assertIn(expected, response.context["form"].errors)
        self.assertFalse(Contract.objects.filter(contract_number="REF-CREATE").exists())

    def test_all_fields_and_cancel_context_retained(self):
        response = self.client.get(self.url)
        form = response.context["form"]
        self.assertEqual(len(form.fields), 12)
        for name in form.fields:
            self.assertContains(response, f'name="{name}"', count=1)
        self.assertEqual(response.context["cancel_url"], reverse("contracts:list"))
        response = self.client.get(self.url, {"project": self.project.pk})
        self.assertEqual(
            response.context["cancel_url"],
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.assertTrue(response.context["form"]["project"].is_hidden)

    def test_foreign_tenant_project_and_party_are_rejected_on_general_post(self):
        other = Organization.objects.create(name="Other tenant", slug="create-other")
        project = Project.objects.create(
            organization=other, code="OTHER", name="Other project"
        )
        party = BusinessParty.objects.create(
            organization=other, party_kind="company", display_name="Other party"
        )
        count = Contract.objects.count()
        for field, record in (("project", project), ("party", party)):
            with self.subTest(field=field):
                response = self.client.post(
                    self.url, self.payload(**{field: str(record.pk)})
                )
                self.assertIn(field, response.context["form"].errors)
                self.assertNotContains(
                    response, record.name if field == "project" else record.display_name
                )
        self.assertEqual(Contract.objects.count(), count)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractCreateReferenceBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/contract-create-reference/browser"
    )

    def test_responsive_layout_errors_controls_create_and_cancel(self):
        self.make_fixture(persian=True)
        self.organization.name = "گروه عمران افق تهران"
        self.organization.save(update_fields=["name"])
        self.project.name = "بازسازی کارخانه نوآوران"
        self.project.save(update_fields=["name"])
        self.party.display_name = "شرکت پیمانکار نمونه"
        self.party.save(update_fields=["display_name"])
        create = reverse("contracts:create")
        scoped = create + f"?project={self.project.pk}"
        common = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        scenarios = []
        for width in (1440, 1024, 390):
            columns = 1 if width == 390 else 2
            dates = 1 if width == 390 else 3
            control_height = 44 if width == 390 else 38
            scenarios.append(
                {
                    **common,
                    "name": f"create-{width}",
                    "path": scoped,
                    "width": width,
                    "height": 1086 if width == 1440 else 900,
                    "mobile": width == 390,
                    "viewportScreenshot": width == 390,
                    "bottomScreenshot": width < 1440,
                    "steps": [
                        inspect(
                            f"""(() => {{
                    const grid=document.querySelector('.erp-form-grid--two');
                    const dates=document.querySelector('.erp-form-grid--three');
                    const footer=document.querySelector('.erp-form-footer').getBoundingClientRect();
                    return document.querySelectorAll('.erp-form-section').length===5 &&
                        getComputedStyle(grid).gridTemplateColumns.split(' ').length==={columns} &&
                        getComputedStyle(dates).gridTemplateColumns.split(' ').length==={dates} &&
                        footer.bottom<=innerHeight && footer.top>=0 &&
                        document.querySelectorAll('.erp-form-footer button').length===1 &&
                        document.querySelectorAll('[data-jalali-date]').length===3 &&
                        !!document.querySelector('[data-money-enhanced]') &&
                        [...document.querySelectorAll('main input,main textarea,.erp-form-footer a,.erp-form-footer button')]
                          .filter(e=>e.type!=='hidden' && !e.closest('.ts-control'))
                          .every(e=>e.getBoundingClientRect().height>={control_height});
                }})()""",
                            "five sections, responsive grids, shared widgets, compact desktop/touch mobile controls and accessible sticky actions",
                        )
                    ],
                }
            )
        self.browser(self.owner, scenarios)
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "required-errors-390",
                    "path": create,
                    "mobile": True,
                    "steps": [
                        {
                            "clickSelector": ".erp-form-footer button",
                            "afterPath": create,
                            "mustText": "این فیلد لازم است",
                        },
                        inspect(
                            "document.querySelectorAll('.erp-form-field--invalid').length===4 && ['project','party','contract_number','title'].every(name=>document.querySelector('[name='+name+']').closest('.erp-form-field--invalid')) && [...document.querySelectorAll('.erp-field-error')].every(e=>!!e.id && e.closest('.erp-form-field')) && document.querySelector('[name=status]').value==='draft' && document.querySelector('[name=contract_value]').value==='۰.۰۰'",
                            "required errors remain adjacent; existing draft and zero amount defaults stay valid",
                        ),
                    ],
                }
            ],
        )
        values = {
            "contract_number": "BROWSER-REF-CREATE",
            "title": "قرارداد مرجع اجرای سازه",
            "direction": "receivable",
            "contract_type": "client",
            "status": "draft",
            "contract_value": "125000000.25",
            "signed_at": "۱۴۰۵/۰۶/۲۳",
            "start_date": "۱۴۰۵/۰۷/۰۱",
            "end_date": "۱۴۰۵/۱۲/۲۵",
            "notes": "یادداشت قرارداد مرورگر",
        }
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "search-calendar-amount",
                    "path": scoped,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "party",
                                "query": "پیمانکار",
                                "value": str(self.party.pk),
                            },
                            "keyboard": True,
                        },
                        {
                            "fill": values,
                            "inspect": "document.querySelector('[name=contract_value]').value==='۱۲۵,۰۰۰,۰۰۰.۲۵'",
                            "description": "existing money formatting retains decimal Rial amount",
                        },
                        {"toggleSelector": "[name=signed_at] + .erp-jalali-trigger"},
                        inspect(
                            "!!document.querySelector('.erp-jalali-popover:not([hidden])')",
                            "existing Jalali calendar opens",
                        ),
                        {
                            "toggleSelector": ".erp-jalali-popover:not([hidden]) [data-day='24']"
                        },
                        inspect(
                            "document.querySelector('[name=signed_at]').value==='۱۴۰۵/۰۶/۲۴' && !document.querySelector('.erp-jalali-popover:not([hidden])')",
                            "calendar selection updates the existing field and closes",
                        ),
                        inspect(
                            "(() => {const f=document.querySelector('[name=title]');f.focus();return document.activeElement===f && getComputedStyle(f).borderColor==='rgb(21, 99, 214)' && getComputedStyle(f).boxShadow!=='none';})()",
                            "visible input focus retains the approved primary ring",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "invalid-amount-1024",
                    "path": scoped,
                    "width": 1024,
                    "steps": [
                        {
                            "fill": {
                                **values,
                                "party": str(self.party.pk),
                                "contract_value": "1.234",
                            },
                            "clickSelector": ".erp-form-footer button",
                            "afterPath": create,
                            "mustText": "اعشار",
                        },
                        inspect(
                            "document.querySelector('[name=contract_value]').getAttribute('aria-invalid')==='true' && !!document.querySelector('#id_contract_value-errors') && document.querySelector('[name=title]').value==='قرارداد مرجع اجرای سازه'",
                            "invalid decimal precision is rejected without losing submitted fields",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "invalid-date-order",
                    "path": scoped,
                    "steps": [
                        {
                            "fill": {
                                **values,
                                "party": str(self.party.pk),
                                "end_date": "۱۴۰۵/۰۶/۰۱",
                            },
                            "clickSelector": ".erp-form-footer button",
                            "afterPath": create,
                            "mustText": "تاریخ پایان قرارداد نمی‌تواند پیش از تاریخ شروع باشد.",
                        },
                    ],
                },
                {
                    **common,
                    "name": "valid-create",
                    "path": scoped,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "party",
                                "query": "پیمانکار",
                                "value": str(self.party.pk),
                            }
                        },
                        {
                            "fill": values,
                            "clickSelector": ".erp-form-footer button",
                            "afterPrefix": "/contracts/",
                            "mustText": "قرارداد مرجع اجرای سازه",
                        },
                        inspect(
                            "!document.querySelector('.erp-create-form')",
                            "valid creation reaches the existing Contract Detail",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "cancel-context-390",
                    "path": scoped,
                    "mobile": True,
                    "steps": [
                        {
                            "clickSelector": ".erp-form-footer a",
                            "afterPath": reverse(
                                "projects:detail", args=[self.project.pk]
                            ),
                        }
                    ],
                },
            ],
        )
        contract = Contract.objects.get(contract_number="BROWSER-REF-CREATE")
        self.assertEqual(contract.contract_value, Decimal("125000000.25"))
        self.assertEqual(contract.project, self.project)
        self.assertEqual(contract.party, self.party)
        self.assertEqual(contract.signed_at, date(2026, 9, 14))
        self.assertEqual(contract.direction, "receivable")
        self.assertEqual(contract.contract_type, "client")
        self.assertEqual(contract.status, "draft")
        self.assertEqual(contract.notes, values["notes"])
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "general-context-and-cancel",
                    "path": create,
                    "steps": [
                        {
                            "fill": {"project": str(self.project.pk)},
                            "inspect": "document.querySelector('[data-create-project-context]').textContent.includes('بازسازی کارخانه نوآوران')",
                            "description": "general project selector updates the read-only summary",
                        },
                        {
                            "clickSelector": ".erp-form-footer a",
                            "afterPath": reverse("contracts:list"),
                        },
                    ],
                }
            ],
        )
        self.assertEqual(
            Contract.objects.filter(contract_number="BROWSER-REF-CREATE").count(), 1
        )
