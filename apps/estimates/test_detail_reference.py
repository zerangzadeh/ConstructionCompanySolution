"""Estimate Detail visual/state acceptance on synthetic isolated PostgreSQL data."""

from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.models import Estimate
from apps.estimates.services import (
    EMPTY_ESTIMATE_APPROVAL_MESSAGE,
    add_estimate_item,
    approve_estimate,
    create_estimate,
)
from apps.estimates.test_mvp03_estimate_ux import seed_estimate_workflow
from apps.materials.models import UnitCategory, UnitOfMeasure
from apps.organizations.models import Organization
from apps.projects.models import Project
from apps.projects.test_command_center import scoped_reader


class EstimateDetailFixture(JourneyFixture):
    def ready(self):
        self.make_fixture(persian=True)
        seed_estimate_workflow()
        # Keep the page's pre-existing currency source; explicitly label this fixture.
        self.organization.currency = "IRR"
        self.organization.save(update_fields=["currency"])
        self.project.name = "بازسازی کارخانه توانگران"
        self.project.save()
        self.owner.first_name, self.owner.last_name = "علی", "نمونه"
        self.owner.save()
        self.login(self.owner)
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="ED-KG",
            name="کیلوگرم",
            symbol="kg",
            category=UnitCategory.WEIGHT,
        )
        self.volume_unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="ED-M3",
            name="مترمکعب",
            symbol="m3",
            category=UnitCategory.VOLUME,
        )
        self.count_unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="ED-N",
            name="عدد",
            symbol="n",
            category=UnitCategory.COUNT,
        )
        self.draft = self.make_estimate("DRAFT", rich=True)
        self.empty = self.make_estimate("EMPTY", empty=True)
        self.linked = self.make_estimate("LINKED", contract=self.contract)
        self.approved = self.make_estimate("APPROVED")
        approve_estimate(estimate=self.approved, actor=self.owner)
        self.approved.refresh_from_db()
        # Existing historical states have no transition endpoint on this page.
        # Only isolated fixtures synthesize them; application data is never changed.
        self.revised = self.make_estimate("REVISED")
        self.archived = self.make_estimate("ARCHIVED")
        for estimate, state in ((self.revised, "revised"), (self.archived, "archived")):
            Estimate.objects.filter(pk=estimate.pk).update(status=state)
            estimate.refresh_from_db()

    def make_estimate(self, number, *, rich=False, empty=False, contract=None):
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            contract=contract,
            actor=self.owner,
            estimate_number="EST-" + number,
            title="برآورد خرید مصالح",
            notes="مقادیر بر پایه نیاز اجرایی پروژه تهیه شده است.",
        )
        rows = (
            [
                ("سیمان تیپ ۲ پاکتی ۵۰ کیلویی", "5000", "1244", self.unit),
                ("ماسه شسته", "12", "3500000", self.volume_unit),
                ("شن نخودی", "8", "3100000", self.volume_unit),
                ("آجر فشاری", "3000", "2400", self.count_unit),
                ("میلگرد آجدار AIII قطر ۱۴", "1500", "6000", self.unit),
            ]
            if rich
            else [("مصالح اجرایی", "2.5", "125000.25", self.unit)]
        )
        if not empty:
            for description, quantity, price, unit in rows:
                add_estimate_item(
                    estimate=estimate,
                    actor=self.owner,
                    description=description,
                    quantity=Decimal(quantity),
                    unit_price=Decimal(price),
                    unit_of_measure=unit,
                    unit=unit.symbol,
                )
        estimate.refresh_from_db()
        return estimate

    def url(self, estimate):
        return reverse("estimates:detail", args=[estimate.pk])

    def reader(self):
        return scoped_reader(
            self.organization,
            self.project,
            ["estimates.view"],
            username="estimate-detail-reader",
        )[0]


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateDetailReferenceTests(EstimateDetailFixture, TestCase):
    def setUp(self):
        self.ready()

    def test_real_totals_current_revision_metadata_and_existing_navigation(self):
        self.assertEqual(self.draft.total_amount, Decimal("89220000.00"))
        response = self.client.get(self.url(self.draft))
        for text in ("89,220,000", "تاریخ ایجاد", "علی نمونه", "اقلام برآورد"):
            self.assertContains(response, text)
        self.assertContains(response, 'id="estimate-item-editor"')
        self.assertNotContains(response, "ایجاد قرارداد")
        self.assertNotContains(response, "ویرایش ردیف")
        self.assertContains(response, "ریال")
        linked = self.client.get(self.url(self.linked))
        self.assertContains(
            linked, reverse("contracts:detail", args=[self.contract.pk])
        )
        self.assertNotContains(linked, "این برآورد به قراردادی متصل نشده است.")

    def test_states_keep_empty_approval_and_history_read_only(self):
        response = self.client.get(self.url(self.empty))
        self.assertContains(response, EMPTY_ESTIMATE_APPROVAL_MESSAGE)
        self.assertNotContains(
            response,
            'action="' + reverse("estimates:approve", args=[self.empty.pk]) + '"',
        )
        for estimate in (self.approved, self.revised, self.archived):
            with self.subTest(state=estimate.status):
                response = self.client.get(self.url(estimate))
                self.assertNotContains(response, 'id="estimate-item-editor"')
                self.assertNotContains(
                    response,
                    'action="' + reverse("estimates:approve", args=[estimate.pk]) + '"',
                )
                self.assertContains(response, estimate.get_status_display())
                self.assertContains(response, "مصالح اجرایی")

    def test_reader_no_controls_or_privileged_links_and_cross_scope_denied(self):
        reader = self.reader()
        self.login(reader)
        for estimate in (self.draft, self.linked):
            response = self.client.get(self.url(estimate))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'id="estimate-item-editor"')
            self.assertNotContains(
                response,
                'href="' + reverse("projects:detail", args=[self.project.pk]) + '"',
            )
            self.assertNotContains(
                response,
                'href="' + reverse("contracts:detail", args=[self.contract.pk]),
            )
        self.assertEqual(self.client.post(self.url(self.draft), {}).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("estimates:approve", args=[self.draft.pk])
            ).status_code,
            403,
        )
        other_org = Organization.objects.create(name="Tenant fixture", slug="ed-other")
        other_project = Project.objects.create(
            organization=other_org, code="OTHER", name="Other"
        )
        other = Estimate.objects.create(
            organization=other_org,
            project=other_project,
            estimate_number="OTHER",
            title="Hidden",
        )
        self.assertEqual(self.client.get(self.url(other)).status_code, 404)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateDetailReferenceBrowserTests(
    EstimateDetailFixture, StaticLiveServerTestCase
):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/estimate-detail-reference/browser"
    )

    def test_chrome_state_matrix_and_real_interactions(self):
        self.ready()

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        base = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }
        layout_check = inspect(
            "document.querySelectorAll('.ed-kpi').length===4 && document.querySelectorAll('.ed-table thead th').length===7 && !!document.querySelector('.ed-items-total') && !document.querySelector('.ed-table tbody button,.ed-table tbody summary') && getComputedStyle(document.querySelector('.ed-panel')).backgroundColor==='rgb(255, 255, 255)'",
            "four compact KPIs, seven columns, total footer, no invented row actions and loaded tokens",
        )
        for mobile in (True, False):
            scenarios = []
            for name, estimate in (
                ("draft", self.draft),
                ("empty", self.empty),
                ("approved", self.approved),
                ("revised", self.revised),
                ("archived", self.archived),
                ("linked", self.linked),
            ):
                editable = estimate.status == "draft"
                can_approve = editable and estimate != self.empty
                checks = [
                    layout_check,
                    inspect(
                        f"!!document.querySelector('#estimate-item-editor')==={str(editable).lower()} && !!document.querySelector('.ed-actions form')==={str(can_approve).lower()}",
                        "state and nonempty approval controls",
                    ),
                    inspect(
                        f"!!document.querySelector('.ed-contract-note')==={str(not estimate.contract_id).lower()}",
                        "linked contract indication is accurate",
                    ),
                ]
                if mobile:
                    checks.append(
                        inspect(
                            "(() => {const w=document.querySelector('.ed-table-wrap');w.scrollLeft=-w.scrollWidth;const moved=w.scrollLeft<0;w.scrollLeft=0;return w.scrollWidth>w.clientWidth && moved && document.querySelector('.ed-items-total').getBoundingClientRect().left>=0 && document.querySelector('.ed-items-total').getBoundingClientRect().right<=innerWidth;})()",
                            "all seven columns reachable by local scrolling; total footer stays within mobile viewport",
                        )
                    )
                else:
                    checks.append(
                        inspect(
                            "document.querySelector('.ed-kpi').getBoundingClientRect().height<110 && getComputedStyle(document.querySelector('.ed-summary')).gridTemplateColumns.split(' ').length===4",
                            "compact four-column summary on desktop; table/footer reviewed in screenshot",
                        )
                    )
                scenarios.append(
                    {
                        **base,
                        "name": name + ("-390" if mobile else "-1440"),
                        "path": self.url(estimate),
                        "mobile": mobile,
                        "steps": checks,
                    }
                )
            self.browser(self.owner, scenarios)

        # Native details remain operable with JavaScript disabled.
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "native-no-js",
                    "path": self.url(self.draft),
                    "noJS": True,
                    "steps": [
                        {"toggleSelector": "#estimate-item-editor > summary"},
                        inspect(
                            "document.querySelector('#estimate-item-editor').open",
                            "native item disclosure works without JavaScript",
                        ),
                    ],
                }
            ],
        )

        self.browser(
            self.reader(),
            [
                {
                    **base,
                    "name": "restricted-"
                    + estimate.estimate_number.lower()
                    + "-"
                    + str(width),
                    "path": self.url(estimate),
                    "mobile": width == 390,
                    "steps": [
                        inspect(
                            '!document.querySelector(\'#estimate-item-editor,.ed-actions form,.ed-menu a[href^="/projects/"],.ed-menu a[href^="/contracts/"]\')',
                            "reader sees no mutation controls or unauthorized project/contract links",
                        )
                    ],
                }
                for width in (1440, 390)
                for estimate in (self.draft, self.linked)
            ],
        )

        context = f"?project_id={self.project.pk}"
        detail = self.url(self.draft)
        approval = reverse("estimates:approve", args=[self.draft.pk]) + context
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "menu-1672",
                    "width": 1672,
                    "height": 941,
                    "path": detail,
                    "steps": [
                        {"toggleSelector": ".ed-menu > summary"},
                        inspect(
                            "document.querySelector('.ed-menu').open && document.querySelector('.ed-menu-links').getBoundingClientRect().left>=0",
                            "secondary menu opens inside viewport",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "validation-error-390",
                    "mobile": True,
                    "path": detail + context,
                    "steps": [
                        {"toggleSelector": "#estimate-item-editor > summary"},
                        {
                            "submit": True,
                            "formSelector": ".ed-item-form",
                            "afterPath": detail,
                        },
                        inspect(
                            "document.querySelector('#estimate-item-editor').open && !!document.querySelector('.ed-item-form .erp-field-error,.ed-item-form .text-red-600,.ed-item-form .text-red-700,[aria-invalid=true]')",
                            "invalid submission keeps editor open with errors",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "append-390",
                    "mobile": True,
                    "path": detail + context,
                    "steps": [
                        {"toggleSelector": "#estimate-item-editor > summary"},
                        {
                            "searchChoice": {
                                "name": "unit_of_measure",
                                "query": "کیلو",
                                "value": str(self.unit.pk),
                            }
                        },
                        {
                            "fill": {
                                "description": "ردیف افزوده از مرورگر",
                                "quantity": "2.5",
                                "unit_price": "1000",
                            },
                            "submit": True,
                            "formSelector": ".ed-item-form",
                            "afterPath": detail,
                            "mustText": "ردیف افزوده از مرورگر",
                        },
                        inspect(
                            "new URLSearchParams(location.search).has('project_id') && document.querySelectorAll('.ed-table tbody tr').length===6",
                            "real append preserves project context and totals",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "approve-1440",
                    "path": detail + context,
                    "steps": [
                        {
                            "clickSelector": f'form[action="{approval}"] button',
                            "afterPath": detail,
                            "mustText": "این برآورد تأیید شده",
                        },
                        inspect(
                            "!document.querySelector('#estimate-item-editor,.ed-actions form') && new URLSearchParams(location.search).has('project_id')",
                            "real approval becomes read-only and preserves project context",
                        ),
                    ],
                },
            ],
        )
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "approved")
        self.assertEqual(self.draft.current_revision.items.count(), 6)
        self.assertEqual(self.draft.total_amount, Decimal("89222500.00"))
