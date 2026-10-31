"""Real Estimate/Contract navigation and capability-level surface verification."""

import json
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.services import create_estimate
from apps.organizations.models import BusinessPermission


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateContractBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/estimate-contract-remediation/browser"
    )

    def test_contextual_general_paths_and_commercial_surface_both_profiles(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="EC-BROWSER",
            title="برآورد اجرای سازه",
        )
        project = reverse("projects:detail", args=[self.project.pk])
        estimate_url = reverse("estimates:detail", args=[estimate.pk])
        contract = reverse("contracts:detail", args=[self.contract.pk])
        contextual = contract + f"?estimate={estimate.pk}"
        collection = reverse("contracts:list")
        review = reverse("contracts:commercial_review", args=[self.contract.pk])

        def trail(*, contextual_path):
            expected = [
                [self.project.name, project],
                [estimate.title, estimate_url]
                if contextual_path
                else ["قراردادها", collection],
                [self.contract.title, None],
            ]
            return {
                "inspect": """(() => {
                    const nav=document.querySelector('main nav[aria-label="مسیر صفحه"]');
                    const nodes=[...nav.querySelectorAll('a,span')];
                    const expected="""
                + json.dumps(expected, ensure_ascii=False)
                + """;
                    return nodes.slice(-3).every((n,i)=>n.textContent.trim()===expected[i][0] && n.getAttribute('href')===expected[i][1]) &&
                        nodes.at(-1).tagName==='SPAN' && nodes.at(-1).getAttribute('aria-current')==='page' &&
                        nav.querySelectorAll('[aria-current=page]').length===1 && !nav.querySelector('a[href="#"],a[aria-current]') &&
                        """
                + (
                    f"!nav.querySelector('a[href=\"{collection}\"]')"
                    if contextual_path
                    else "true"
                )
                + ";})()",
                "description": "exact Project/Estimate/Contract path or normal Project/Contracts/Contract path",
            }

        for profile in ("MVP", "FULL_ERP"):
            with override_settings(PRODUCT_SURFACE_PROFILE=profile):
                # Permission is retained independently of product exposure.
                self.login(self.owner)
                response = self.client.get(contract)
                self.assertTrue(response.context["can_review_commercial"])
                scenarios = []
                for mobile in (False, True):
                    suffix = "mobile" if mobile else "desktop"
                    common = {"status": 200, "screenshot": True, "mobile": mobile}
                    exposure = (
                        {"mustLinks": [review]}
                        if profile == "FULL_ERP"
                        else {
                            "absentLinks": [review],
                            "absentText": ["مرور تجاری و استثناها"],
                        }
                    )
                    scenarios.extend(
                        [
                            {
                                **common,
                                **exposure,
                                "name": f"EC-{profile}-{suffix}-handoff",
                                "path": estimate_url,
                                "steps": [
                                    {"clickHref": contextual, "afterPath": contract},
                                    trail(contextual_path=True),
                                ],
                            },
                            {
                                **common,
                                "name": f"EC-{profile}-{suffix}-estimate-back",
                                "path": contextual,
                                "steps": [
                                    {
                                        "clickSelector": f'main nav[aria-label="مسیر صفحه"] a[href="{estimate_url}"]',
                                        "afterPath": estimate_url,
                                    }
                                ],
                                "mustText": [estimate.title],
                                "mustLinks": [project],
                            },
                            {
                                **common,
                                "name": f"EC-{profile}-{suffix}-project-back",
                                "path": contextual,
                                "steps": [
                                    {
                                        "clickSelector": f'main nav[aria-label="مسیر صفحه"] a[href="{project}"]',
                                        "afterPath": project,
                                    }
                                ],
                                "mustText": [self.project.name],
                            },
                            {
                                **common,
                                **exposure,
                                "name": f"EC-{profile}-{suffix}-general",
                                "path": contract,
                                "steps": [trail(contextual_path=False)],
                            },
                        ]
                    )
                for start in range(0, len(scenarios), 4):
                    self.browser(self.owner, scenarios[start : start + 4])
                if profile == "MVP":
                    self.browser(
                        self.owner,
                        [
                            {
                                "name": "EC-MVP-direct-review-denied",
                                "path": review + "?profile=FULL_ERP",
                                "status": 403,
                                "screenshot": True,
                            }
                        ],
                    )
                else:
                    self.browser(
                        self.owner,
                        [
                            {
                                "name": "EC-FULL_ERP-review-open",
                                "path": contract,
                                "status": 200,
                                "screenshot": True,
                                "steps": [{"clickHref": review, "afterPath": review}],
                                "mustText": ["خط زمانی و مقایسه تجاری قرارداد"],
                            }
                        ],
                    )
                    role = self.organization.memberships.get(
                        user=self.owner
                    ).role_definition
                    role.permissions.remove(
                        BusinessPermission.objects.get(code="contractual_records.view")
                    )
                    self.browser(
                        self.owner,
                        [
                            {
                                "name": "EC-FULL_ERP-without-review-permission",
                                "path": contract,
                                "status": 200,
                                "screenshot": True,
                                "absentLinks": [review],
                                "absentText": ["مرور تجاری و استثناها"],
                            }
                        ],
                    )
                    self.assertEqual(self.client.get(review).status_code, 403)
