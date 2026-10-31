"""Desktop/mobile Chrome verification against a disposable PostgreSQL test DB."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.models import Estimate
from apps.estimates.services import EMPTY_ESTIMATE_APPROVAL_MESSAGE, create_estimate
from apps.estimates.test_mvp03_estimate_ux import seed_estimate_workflow
from apps.estimates.workflow import request_estimate_approval
from apps.materials.models import UnitOfMeasure
from apps.projects.models import Project, ProjectSite


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateUXBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/estimate-ux-remediation/browser"
    )

    def test_project_context_items_and_approval_desktop_mobile(self):
        self.make_fixture(persian=True)
        seed_estimate_workflow()
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        sibling = Project.objects.create(
            organization=self.organization, code="EUX-ACTIVE", name="پروژه فعال دیگر"
        )
        self.login(self.owner)
        session = self.client.session
        session["active_project_id"] = str(sibling.pk)
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=sibling,
            code="EUX-ACTIVE-S",
            name="کارگاه فعال دیگر",
        )
        session["active_site_id"] = str(site.pk)
        session.save()
        before = dict(self.client.session)
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EUX-M",
            name="متر اجرایی",
            symbol="m",
            category="length",
        )
        context = f"?project_id={self.project.pk}"
        project = reverse("projects:detail", args=[self.project.pk])
        listing = reverse("estimates:list") + context
        create = reverse("estimates:create") + context
        context_check = {
            "inspect": f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
            "description": "local Project context remains in the URL",
        }
        current_check = {
            "inspect": "(() => {const n=document.querySelector('main nav[aria-label=\"مسیر صفحه\"]'); return n.querySelectorAll('[aria-current=page]').length===1 && n.querySelector('[aria-current=page]').tagName==='SPAN' && n.lastElementChild===n.querySelector('[aria-current=page]');})()",
            "description": "the final breadcrumb is the sole non-link current page",
        }
        for mobile in (False, True):
            suffix = "mobile" if mobile else "desktop"
            estimate = create_estimate(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                estimate_number="EUX-BROWSER-" + suffix,
                title="برآورد اجرایی " + suffix,
            )
            instance = request_estimate_approval(estimate=estimate, actor=self.owner)
            detail = reverse("estimates:detail", args=[estimate.pk])
            scoped_detail = detail + context
            approve = reverse("estimates:approve", args=[estimate.pk]) + context

            def scenario(name, path, *, suffix=suffix, mobile=mobile, **kwargs):
                return {
                    "name": "EUX-" + suffix + "-" + name,
                    "path": path,
                    "mobile": mobile,
                    "status": 200,
                    "screenshot": True,
                    **kwargs,
                }

            scenarios = [
                scenario(
                    "roundtrip",
                    project,
                    steps=[
                        {"clickHref": listing, "afterPath": reverse("estimates:list")},
                        context_check,
                        {"clickHref": scoped_detail, "afterPath": detail},
                        context_check,
                        current_check,
                        {
                            "clickSelector": f'main nav[aria-label="مسیر صفحه"] a[href="{listing}"]',
                            "afterPath": reverse("estimates:list"),
                        },
                        context_check,
                    ],
                    mustLinks=[create, scoped_detail],
                ),
                scenario(
                    "create-form",
                    project,
                    steps=[
                        {"clickHref": create, "afterPath": reverse("estimates:create")},
                        context_check,
                        {
                            "inspect": f"document.querySelector('input[type=hidden][name=project]').value==='{self.project.pk}' && !document.querySelector('select[name=project]') && document.querySelector('textarea[name=notes]').rows===3 && document.querySelector('[name=contract]').closest('.erp-form-field').querySelector('label').innerText.includes('اختیاری') && document.querySelector('[name=phase]').closest('.erp-form-field').querySelector('label').innerText.includes('اختیاری')",
                            "description": "inherited project, optional fields and compact notes",
                        },
                        current_check,
                    ],
                    mustLinks=[listing],
                ),
                scenario(
                    "create-submit",
                    create,
                    steps=[
                        {"submit": True, "afterPath": reverse("estimates:create")},
                        context_check,
                        {
                            "fill": {
                                "estimate_number": "EUX-CREATED-" + suffix,
                                "title": "برآورد تازه پروژه",
                            },
                            "submit": True,
                            "afterPrefix": "/estimates/",
                            "mustText": "برآورد تازه پروژه",
                        },
                        context_check,
                        current_check,
                    ],
                    mustLinks=[listing],
                    mustText=[EMPTY_ESTIMATE_APPROVAL_MESSAGE],
                ),
                scenario(
                    "empty",
                    scoped_detail,
                    mustText=[EMPTY_ESTIMATE_APPROVAL_MESSAGE],
                    steps=[
                        {
                            "inspect": f"!document.querySelector('form[action=\"{approve}\"]') && !document.querySelector('[name=sort_order]') && !document.querySelector('main').innerText.includes('ترتیب نمایش')",
                            "description": "empty estimate cannot be approved and item order is absent",
                        },
                        current_check,
                    ],
                ),
            ]
            self.browser(self.owner, scenarios)
            # Keep batches bounded; each submission uses the existing real item form.
            item_scenarios = []
            for index in (1, 2):
                item_scenarios.append(
                    scenario(
                        "item-" + str(index),
                        scoped_detail,
                        steps=[
                            {
                                "inspect": "(() => {document.querySelector('main details.erp-surface').open=true; return !document.querySelector('[name=sort_order]');})()",
                                "description": "open the item editor without a technical order input",
                            },
                            {
                                "searchChoice": {
                                    "name": "unit_of_measure",
                                    "query": "متر",
                                    "value": str(unit.pk),
                                }
                            },
                            {
                                "fill": {
                                    "description": f"ردیف اجرایی {index}",
                                    "quantity": "2",
                                    "unit_price": "10",
                                },
                                "submit": True,
                                "formSelector": "main details form",
                                "afterPath": detail,
                                "mustText": f"ردیف اجرایی {index}",
                            },
                            context_check,
                            current_check,
                        ],
                        mustText=[f"ردیف اجرایی {index}"],
                        mustLinks=[listing],
                    )
                )
            item_scenarios.append(
                scenario(
                    "approval",
                    scoped_detail,
                    steps=[
                        {
                            "clickSelector": f'form[action="{approve}"] button',
                            "afterPath": detail,
                            "mustText": "این برآورد تأیید شده",
                        },
                        context_check,
                        current_check,
                    ],
                    mustText=["این برآورد تأیید شده"],
                    mustLinks=[listing],
                )
            )
            self.browser(self.owner, item_scenarios)
            estimate.refresh_from_db()
            instance.refresh_from_db()
            self.assertEqual(estimate.status, "approved")
            self.assertEqual(instance.status, "completed")
            self.assertEqual(
                list(
                    estimate.current_revision.items.values_list("sort_order", flat=True)
                ),
                [1, 2],
            )
            self.assertEqual(
                Estimate.objects.get(
                    estimate_number=("EUX-CREATED-" + suffix).upper()
                ).project,
                self.project,
            )
        self.assertEqual(dict(self.client.session), before)
