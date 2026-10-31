"""Real Chrome contextual creates on the isolated PostgreSQL live server."""

from datetime import date
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.models import ProgressClaim
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate
from apps.organizations.models import Organization
from apps.projects.models import Project
from core.jalali import format_jalali


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContextualBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/mvp-03/contextual-create/browser"
    )

    def test_general_create_submissions_and_native_context(self):
        self.make_fixture(persian=True)
        baseline = self._approved_baseline()
        project_url = reverse("projects:detail", args=[self.project.pk])
        contract_url = reverse("contracts:detail", args=[self.contract.pk])
        dates = {
            "period_start": format_jalali(date(2026, 9, 1)),
            "period_end": format_jalali(date(2026, 9, 30)),
            "measurement_cutoff": format_jalali(date(2026, 9, 30)),
        }
        self.browser(
            self.owner,
            [
                {
                    "name": "CTX-27-general-estimate-success",
                    "path": reverse("estimates:create"),
                    "status": 200,
                    "screenshot": True,
                    "mustLinks": [project_url],
                    "steps": [
                        {
                            "fill": {
                                "project": str(self.project.pk),
                                "estimate_number": "CTX-GENERAL-E",
                                "title": "برآورد از ورودی عمومی",
                            },
                            "submit": True,
                            "afterPrefix": "/estimates/",
                            "mustText": "برآورد از ورودی عمومی",
                        }
                    ],
                },
                {
                    "name": "CTX-28-general-contract-success",
                    "path": reverse("contracts:create"),
                    "status": 200,
                    "screenshot": True,
                    "mobile": True,
                    "mustLinks": [project_url],
                    "steps": [
                        {
                            "fill": {
                                "project": str(self.project.pk),
                                "party": str(self.party.pk),
                                "contract_number": "CTX-GENERAL-C",
                                "title": "قرارداد از ورودی عمومی",
                                "status": "active",
                                "direction": "receivable",
                                "contract_value": "100",
                            },
                            "submit": True,
                            "afterPrefix": "/contracts/",
                            "mustText": "قرارداد از ورودی عمومی",
                        }
                    ],
                },
                {
                    "name": "CTX-29-general-claim-success",
                    "path": reverse("billing:claim_create"),
                    "status": 200,
                    "screenshot": True,
                    "mustLinks": [project_url, contract_url],
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "contract",
                                "query": self.contract.contract_number,
                                "value": str(self.contract.pk),
                            }
                        },
                        {
                            "searchChoice": {
                                "name": "baseline",
                                "query": self.contract.title,
                                "value": str(baseline.pk),
                            }
                        },
                        {
                            "fill": dates,
                            "submit": True,
                            "afterPrefix": "/billing/claims/",
                            "mustText": "پیش‌نویس صورت‌وضعیت",
                        },
                    ],
                },
            ],
        )
        self.assertEqual(
            Estimate.objects.get(estimate_number="CTX-GENERAL-E").project, self.project
        )
        self.assertEqual(
            Contract.objects.get(contract_number="CTX-GENERAL-C").project, self.project
        )
        self.assertEqual(ProgressClaim.objects.get().baseline, baseline)
        scenarios = []
        for name, route, field, parent in (
            ("estimate", "estimates:create", "project", self.project),
            ("contract", "contracts:create", "project", self.project),
            ("claim", "billing:claim_create", "contract", self.contract),
        ):
            scenarios.append(
                {
                    "name": "CTX-30-native-" + name,
                    "path": reverse(route) + f"?{field}={parent.pk}&native_choices=1",
                    "status": 200,
                    "screenshot": True,
                    "steps": [
                        {
                            "inspect": f"document.querySelector('input[type=hidden][name={field}]').value==='{parent.pk}' && !document.querySelector('select[name={field}]')",
                            "description": "native fallback retains inherited parent",
                        }
                    ],
                }
            )
        self.browser(self.owner, scenarios)

    def test_contextual_creation_general_entries_and_isolation(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        baseline = self._approved_baseline()
        empty = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="CTX-NO-BASE",
            title="قرارداد بدون مبنای تأییدشده",
            counterparty_name="طرف نمونه",
            direction="receivable",
            status="active",
        )
        linked = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="CTX-LINK",
            title="برآورد متصل",
        )
        unlinked = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="CTX-UNLINK",
            title="برآورد مستقل",
        )
        foreign_org = Organization.objects.create(
            name="Private tenant", slug="ctx-private"
        )
        foreign_project = Project.objects.create(
            organization=foreign_org,
            code="CTX-PRIVATE",
            name="پروژه محرمانه",
        )
        foreign_contract = Contract.objects.create(
            organization=foreign_org,
            project=foreign_project,
            contract_number="PRIVATE-C",
            title="قرارداد محرمانه",
            counterparty_name="طرف محرمانه",
            direction="receivable",
            status="active",
        )
        project = reverse("projects:detail", args=[self.project.pk])
        contract = reverse("contracts:detail", args=[self.contract.pk])
        estimate_create = reverse("estimates:create")
        contract_create = reverse("contracts:create")
        claim_create = reverse("billing:claim_create")
        estimate_context = estimate_create + f"?project_id={self.project.pk}"
        contract_context = contract_create + f"?project={self.project.pk}"
        claim_context = claim_create + f"?contract={self.contract.pk}"

        def scenario(name, path, **kwargs):
            return dict(name=name, path=path, status=200, screenshot=True, **kwargs)

        def inherited(name, parent):
            return {
                "inspect": f"document.querySelector('input[type=hidden][name={name}]').value==='{parent.pk}' && !document.querySelector('select[name={name}]') && document.querySelectorAll('[data-inherited-context]').length===1 && !document.querySelector('main').innerText.includes('{parent.pk}')",
                "description": "trusted inherited parent, business identity without redundant selector or visible UUID",
            }

        dates = {
            "period_start": format_jalali(date(2026, 9, 1)),
            "period_end": format_jalali(date(2026, 9, 30)),
            "measurement_cutoff": format_jalali(date(2026, 9, 30)),
        }
        estimate_values = {
            "estimate_number": "CTX-BROWSER-E",
            "title": "برآورد زمینه‌دار مرورگر",
        }
        contract_values = {
            "contract_number": "CTX-BROWSER-C",
            "title": "قرارداد زمینه‌دار مرورگر",
            "party": str(self.party.pk),
            "direction": "receivable",
            "status": "active",
            "contract_value": "100",
        }
        scenarios = [
            scenario(
                "CTX-01-project-estimate-entry",
                project,
                steps=[
                    {"clickHref": estimate_context, "afterPath": estimate_create},
                    inherited("project", self.project),
                ],
                mustText=[self.project.name],
                mustLinks=[project],
            ),
            scenario(
                "CTX-02-project-estimate-mobile",
                estimate_context,
                mobile=True,
                steps=[inherited("project", self.project)],
            ),
            scenario(
                "CTX-03-estimate-error",
                estimate_context,
                steps=[
                    {"submit": True, "afterPath": estimate_create},
                    inherited("project", self.project),
                    {
                        "inspect": "document.querySelectorAll('.erp-form-field .text-red-600, .erp-form-field .text-red-700, [aria-invalid=true]').length>0",
                        "description": "visible validation error",
                    },
                ],
            ),
            scenario(
                "CTX-04-estimate-cancel",
                estimate_context,
                steps=[
                    {
                        "clickSelector": "main form a.erp-btn--secondary",
                        "afterPath": project,
                    }
                ],
            ),
            scenario(
                "CTX-05-estimate-success",
                estimate_context,
                steps=[
                    {
                        "fill": estimate_values,
                        "submit": True,
                        "afterPrefix": "/estimates/",
                        "mustText": estimate_values["title"],
                    },
                ],
                mustLinks=[project],
                mustText=[self.project.name, estimate_values["title"]],
            ),
            scenario(
                "CTX-06-project-contract-entry",
                project,
                steps=[
                    {"clickHref": contract_context, "afterPath": contract_create},
                    inherited("project", self.project),
                ],
            ),
            scenario(
                "CTX-07-project-contract-mobile",
                contract_context,
                mobile=True,
                steps=[inherited("project", self.project)],
            ),
            scenario(
                "CTX-08-contract-error",
                contract_context,
                steps=[
                    {"submit": True, "afterPath": contract_create},
                    inherited("project", self.project),
                ],
            ),
            scenario(
                "CTX-09-contract-cancel",
                contract_context,
                steps=[
                    {
                        "clickSelector": "main form a.erp-btn--secondary",
                        "afterPath": project,
                    }
                ],
            ),
            scenario(
                "CTX-10-contract-success",
                contract_context,
                mobile=True,
                steps=[
                    {
                        "fill": contract_values,
                        "submit": True,
                        "afterPrefix": "/contracts/",
                        "mustText": contract_values["title"],
                    },
                ],
                mustLinks=[project],
            ),
            scenario(
                "CTX-11-estimate-existing-contract",
                reverse("estimates:detail", args=[linked.pk]),
                steps=[
                    {
                        "clickHref": contract + f"?estimate={linked.pk}",
                        "afterPath": contract,
                    }
                ],
                mustText=[self.contract.title],
            ),
            scenario(
                "CTX-12-estimate-unlinked-limitation",
                reverse("estimates:detail", args=[unlinked.pk]),
                mobile=True,
                mustText=["ایجاد قرارداد متصل از این صفحه در دسترس نیست."],
            ),
            scenario(
                "CTX-13-contract-claim-entry",
                contract,
                steps=[
                    {"clickHref": claim_context, "afterPath": claim_create},
                    inherited("contract", self.contract),
                    {
                        "inspect": f"document.querySelector('[name=baseline]').value==='{baseline.pk}'",
                        "description": "single eligible approved baseline automatically selected",
                    },
                ],
                mustText=[
                    self.project.name,
                    self.contract.contract_number,
                    self.contract.title,
                ],
            ),
            scenario(
                "CTX-14-claim-mobile",
                claim_context,
                mobile=True,
                steps=[inherited("contract", self.contract)],
            ),
            scenario(
                "CTX-15-claim-error",
                claim_context,
                steps=[
                    {"submit": True, "mustText": "این فیلد را تکمیل کنید"},
                    inherited("contract", self.contract),
                ],
            ),
            scenario(
                "CTX-16-claim-cancel",
                claim_context,
                steps=[
                    {
                        "clickSelector": "main form a.erp-btn--secondary",
                        "afterPath": contract,
                    }
                ],
            ),
            scenario(
                "CTX-17-claim-success",
                claim_context,
                mobile=True,
                steps=[
                    {
                        "fill": dates,
                        "submit": True,
                        "afterPrefix": "/billing/claims/",
                        "mustText": "پیش‌نویس صورت‌وضعیت",
                    },
                ],
                mustLinks=[contract, project],
            ),
            scenario(
                "CTX-18-no-baseline",
                claim_create + f"?contract={empty.pk}",
                mustText=["مبنای اندازه‌گیری تأییدشده‌ای در دسترس نیست"],
                steps=[
                    inherited("contract", empty),
                    {
                        "inspect": "document.querySelector('main form button[type=submit]').disabled && [...document.querySelector('[name=baseline]').options].every(o=>!o.value)",
                        "description": "no eligible baseline and clear prerequisite",
                    },
                ],
            ),
            scenario(
                "CTX-19-no-baseline-mobile",
                claim_create + f"?contract={empty.pk}",
                mobile=True,
            ),
        ]
        for name, path, parent in (
            ("estimate", estimate_create, "project"),
            ("contract", contract_create, "project"),
            ("claim", claim_create, "contract"),
        ):
            scenarios.append(
                scenario(
                    f"CTX-20-general-{name}",
                    path,
                    steps=[
                        {
                            "inspect": f"!!document.querySelector('select[name={parent}]') && !document.querySelector('input[type=hidden][name={parent}]')",
                            "description": "general entry retains editable parent selector",
                        }
                    ],
                )
            )
        scenarios.extend(
            [
                scenario(
                    "CTX-21-tampered-project",
                    estimate_context,
                    steps=[
                        {
                            "fill": {
                                **estimate_values,
                                "project": str(foreign_project.pk),
                            },
                            "submit": True,
                            "mustText": "ارسال‌شده با زمینه این فرم هم‌خوان نیست",
                        },
                        inherited("project", self.project),
                    ],
                ),
                scenario(
                    "CTX-22-tampered-contract",
                    claim_context,
                    steps=[
                        {
                            "fill": {**dates, "contract": str(foreign_contract.pk)},
                            "submit": True,
                            "mustText": "ارسال‌شده با زمینه این فرم هم‌خوان نیست",
                        },
                        inherited("contract", self.contract),
                    ],
                ),
            ]
        )
        for offset in range(0, len(scenarios), 6):
            self.browser(self.owner, scenarios[offset : offset + 6])
        self.assertEqual(
            Estimate.objects.get(estimate_number="CTX-BROWSER-E").project, self.project
        )
        self.assertEqual(
            Contract.objects.get(contract_number="CTX-BROWSER-C").project, self.project
        )
        claim = ProgressClaim.objects.get(organization=self.organization)
        self.assertEqual(
            (claim.contract, claim.project, claim.baseline),
            (self.contract, self.project, baseline),
        )
        self.browser(
            self.owner,
            [
                {
                    "name": "CTX-23-foreign-project",
                    "path": estimate_create + f"?project={foreign_project.pk}",
                    "status": 404,
                    "screenshot": True,
                    "absentText": [foreign_project.name],
                },
                {
                    "name": "CTX-24-foreign-contract",
                    "path": claim_create + f"?contract={foreign_contract.pk}",
                    "status": 404,
                    "screenshot": True,
                    "absentText": [foreign_contract.title],
                },
            ],
        )
        self.browser(
            self.member,
            [
                {
                    "name": "CTX-25-missing-permission",
                    "path": claim_context,
                    "status": 403,
                    "screenshot": True,
                },
            ],
        )
        Contract.objects.filter(pk=self.contract.pk).update(status="closed")
        self.browser(
            self.owner,
            [
                {
                    "name": "CTX-26-stale-contract",
                    "path": claim_context,
                    "status": 404,
                    "screenshot": True,
                },
            ],
        )
