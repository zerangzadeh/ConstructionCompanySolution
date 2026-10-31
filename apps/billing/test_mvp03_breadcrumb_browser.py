"""Focused real Chrome breadcrumb parents and final current-page semantics."""

import json
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import ProgressRecord
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.services import create_estimate
from apps.workforce.test_mvp02 import make_field_fixture


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BreadcrumbBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/breadcrumb-remediation/browser"
    )

    def test_business_and_shared_breadcrumb_destinations(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        claim = self._claim()
        record = ProgressRecord.objects.get(baseline=claim.baseline)
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="BC-BROWSER",
            title="برآورد مسیر پروژه",
        )
        _, _, _, employee, _ = make_field_fixture(self.owner, self.organization)
        project = reverse("projects:detail", args=[self.project.pk])
        estimate_url = reverse("estimates:detail", args=[estimate.pk])
        contract = reverse("contracts:detail", args=[self.contract.pk])
        contextual_contract = contract + f"?estimate={estimate.pk}"

        def inspect(parents):
            return {
                "inspect": """(() => {
                const nav=document.querySelector('main nav[aria-label="مسیر صفحه"]');
                if(!nav) return false;
                const items=[...nav.querySelectorAll('a,span')], current=items.at(-1);
                return nav.querySelectorAll('[aria-current=page]').length===1 &&
                    current.tagName==='SPAN' && current.getAttribute('aria-current')==='page' &&
                    !nav.querySelector('a[aria-current],a[href="#"]') &&
                    """
                + json.dumps(parents)
                + """.every(url=>[...nav.querySelectorAll('a[href]')].some(a=>a.getAttribute('href')===url)) &&
                    !/billing:|workforce:|contracts:|estimates:|apps\\./.test(nav.innerText);
            })()""",
                "description": "real exposed parent links and one final non-clickable current page",
            }

        scenarios = []

        def add(name, path, parents=(), mobile=False, steps=()):
            scenarios.append(
                {
                    "name": "BC-" + name,
                    "path": path,
                    "status": 200,
                    "mobile": mobile,
                    "screenshot": True,
                    "steps": [*steps, inspect(parents)],
                }
            )

        for mobile in (False, True):
            suffix = "mobile" if mobile else "desktop"
            add("project-" + suffix, project, [reverse("projects:list")], mobile)
            add(
                "estimate-create-" + suffix,
                reverse("estimates:create") + f"?project={self.project.pk}",
                [project, reverse("estimates:list") + f"?project_id={self.project.pk}"],
                mobile,
            )
            add(
                "estimate-detail-" + suffix,
                estimate_url,
                [project, reverse("estimates:list")],
                mobile,
            )
            add(
                "estimate-contract-" + suffix,
                estimate_url,
                [project, estimate_url],
                mobile,
                [{"clickHref": contextual_contract, "afterPath": contract}],
            )
            add(
                "claim-create-" + suffix,
                reverse("billing:claim_create") + f"?contract={self.contract.pk}",
                [project, contract, reverse("billing:claim_list")],
                mobile,
            )
            add(
                "claim-detail-" + suffix,
                reverse("billing:claim_detail", args=[claim.pk]),
                [project, contract, reverse("billing:claim_list")],
                mobile,
            )
            add(
                "baseline-detail-" + suffix,
                reverse("billing:baseline_detail", args=[claim.baseline.pk]),
                [project, contract, reverse("billing:baseline_list")],
                mobile,
            )
            add(
                "progress-detail-" + suffix,
                reverse("billing:progress_detail", args=[record.pk]),
                [project, contract, reverse("billing:progress_list")],
                mobile,
            )
        for name, route in (
            ("baseline", "billing:baseline_list"),
            ("progress", "billing:progress_list"),
            ("claims", "billing:claim_list"),
        ):
            add(
                name + "-scoped-list",
                reverse(route) + f"?contract={self.contract.pk}",
                [project, contract],
            )
            add(name + "-general-list", reverse(route), [reverse("home")])
        add(
            "estimate-error",
            reverse("estimates:create") + f"?project={self.project.pk}",
            [project, reverse("estimates:list") + f"?project_id={self.project.pk}"],
            True,
            [{"submit": True, "afterPath": reverse("estimates:create")}],
        )
        add(
            "project-parent-click",
            reverse("estimates:create") + f"?project={self.project.pk}",
            [reverse("projects:list")],
            False,
            [
                {
                    "clickSelector": f"main nav[aria-label='مسیر صفحه'] a[href='{project}']",
                    "afterPath": project,
                }
            ],
        )
        add(
            "estimate-parent-click",
            contextual_contract,
            [project, reverse("estimates:list")],
            True,
            [
                {
                    "clickSelector": f"main nav[aria-label='مسیر صفحه'] a[href='{estimate_url}']",
                    "afterPath": estimate_url,
                }
            ],
        )
        add(
            "contract-parent-click",
            reverse("billing:claim_create") + f"?contract={self.contract.pk}",
            [project, reverse("contracts:list")],
            False,
            [
                {
                    "clickSelector": f"main nav[aria-label='مسیر صفحه'] a[href='{contract}']",
                    "afterPath": contract,
                }
            ],
        )
        field_list = reverse("workforce:field_list")
        for name, path in (
            ("workforce-create", reverse("workforce:field_create")),
            ("workforce-detail", reverse("workforce:field_detail", args=[employee.pk])),
            ("workforce-edit", reverse("workforce:field_edit", args=[employee.pk])),
            ("workforce-assignment", reverse("workforce:assignment_create")),
            ("workforce-team", reverse("workforce:work_team_create")),
        ):
            add(name, path, [field_list], name.endswith(("edit", "assignment")))
        add(
            "timekeeping-form",
            reverse("timekeeping:attendance_create"),
            [reverse("timekeeping:workbench")],
            True,
        )
        gallery = reverse("projects:gallery", args=[self.project.pk])
        add("project-gallery", gallery, [project, reverse("projects:list")])
        add(
            "project-photo",
            reverse("projects:photo_add", args=[self.project.pk]),
            [project, gallery, reverse("projects:list")],
            True,
        )
        for name, route in (
            ("parties", "parties:list"),
            ("documents", "documents:list"),
            ("materials", "materials:material_list"),
        ):
            add("shared-" + name, reverse(route), [reverse("home")])
        for offset in range(0, len(scenarios), 6):
            self.browser(self.owner, scenarios[offset : offset + 6])
