"""Real Chrome journey evidence on an isolated PostgreSQL live server."""

import json
import os
import subprocess
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing.models import ProgressClaim
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.contracts.services import (
    approve_contract_term_version,
    create_contract_term_version,
)
from apps.estimates.services import create_estimate
from core.jalali import format_jalali


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractBillingBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/remediation-20261030/browser"
    )

    def test_project_hub_hands_off_to_dedicated_pages(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        claim = self._claim()
        create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="HUB-E",
            title="برآورد سازه پروژه",
        )
        project = reverse("projects:detail", args=[self.project.pk])
        contracts = reverse("contracts:list") + f"?project_id={self.project.pk}"
        estimates = reverse("estimates:list") + f"?project_id={self.project.pk}"
        claims = reverse("billing:claim_list") + f"?project_id={self.project.pk}"
        contract_create = reverse("contracts:create") + f"?project={self.project.pk}"
        estimate_create = reverse("estimates:create") + f"?project_id={self.project.pk}"
        base = {"status": 200, "screenshot": True}
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "P-project-hub-desktop",
                    "path": project,
                    "mustText": [
                        "برآورد، قرارداد و صورت‌وضعیت پروژه",
                        "اجرای سازه بتنی",
                        "برآورد سازه پروژه",
                    ],
                    "mustLinks": [
                        contracts,
                        estimates,
                        claims,
                        contract_create,
                        estimate_create,
                    ],
                    "steps": [
                        {
                            "inspect": "document.querySelectorAll('#commercial-summary article').length===3 && document.querySelectorAll('#commercial-summary form').length===0",
                            "description": "compact read-only commercial hub",
                        }
                    ],
                },
                {
                    **base,
                    "name": "Q-project-hub-mobile",
                    "path": project,
                    "mobile": True,
                    "mustLinks": [contracts, estimates, claims],
                },
                {
                    **base,
                    "name": "R-project-contracts-filter",
                    "path": project,
                    "steps": [
                        {
                            "clickHref": contracts,
                            "afterPath": reverse("contracts:list"),
                        },
                        {
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": reverse("contracts:list"),
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
                            "description": "filter submission retains project",
                        },
                    ],
                    "mustText": ["فهرست به سوابق قابل مشاهده این پروژه محدود است."],
                    "mustLinks": [contract_create],
                },
                {
                    **base,
                    "name": "S-project-estimates-filter",
                    "path": project,
                    "steps": [
                        {
                            "clickHref": estimates,
                            "afterPath": reverse("estimates:list"),
                        },
                        {
                            "clickSelector": "form[data-table-filter-form] button",
                            "afterPath": reverse("estimates:list"),
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
                            "description": "estimate filter retains project",
                        },
                    ],
                    "mustLinks": [estimate_create],
                },
                {
                    **base,
                    "name": "T-project-claims-handoff",
                    "path": project,
                    "steps": [
                        {
                            "clickHref": claims,
                            "afterPath": reverse("billing:claim_list"),
                        },
                        {
                            "clickSelector": "form[aria-label='فیلتر صورت‌وضعیت‌ها'] button",
                            "afterPath": reverse("billing:claim_list"),
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
                            "description": "claim filter retains project",
                        },
                    ],
                    "mustLinks": [
                        reverse("billing:claim_detail", args=[claim.pk]),
                        contracts,
                    ],
                    "mustText": ["انتخاب قرارداد پروژه برای صورت‌وضعیت جدید"],
                },
                {
                    **base,
                    "name": "U-project-contract-create-context",
                    "path": project,
                    "steps": [
                        {
                            "clickHref": contract_create,
                            "afterPath": reverse("contracts:create"),
                        },
                        {
                            "inspect": f"document.querySelector('[name=project]').value==='{self.project.pk}'",
                            "description": "dedicated contract form receives project",
                        },
                    ],
                },
                {
                    **base,
                    "name": "V-project-estimate-create-context",
                    "path": project,
                    "mobile": True,
                    "steps": [
                        {
                            "clickHref": estimate_create,
                            "afterPath": reverse("estimates:create"),
                        },
                        {
                            "inspect": f"document.querySelector('[name=project]').value==='{self.project.pk}'",
                            "description": "dedicated estimate form receives project",
                        },
                    ],
                },
            ],
        )

    def _fixture_teardown(self):
        from django.core.management import call_command
        from django.db import connections

        # Match MVP-02's isolated cleanup for intentionally retained Payment FKs.
        for alias in self._databases_names(include_mirrors=False):
            self.assertTrue(
                connections[alias].settings_dict["NAME"].startswith("test_")
            )
            call_command(
                "flush",
                verbosity=0,
                interactive=False,
                database=alias,
                reset_sequences=False,
                allow_cascade=True,
                inhibit_post_migrate=True,
            )

    def browser(self, actor, scenarios):
        self.login(actor)
        env = os.environ.copy()
        # Reuse the qualified Chrome/CDP UI driver; its environment names are legacy.
        env["MVP02_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP02_SCENARIOS"] = json.dumps(scenarios)
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "node",
                str(root / "scripts/verification/mvp02_browser.mjs"),
                self.live_server_url,
                str(
                    getattr(
                        self,
                        "browser_evidence_directory",
                        root / "output/mvp-03/browser",
                    )
                ),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-3000:])
        results = json.loads(result.stdout)
        self.assertEqual(len(results), len(scenarios))
        (
            Path(
                getattr(
                    self, "browser_evidence_directory", root / "output/mvp-03/browser"
                )
            )
            / f"batch-{scenarios[0]['name']}.json"
        ).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def test_representative_journey_desktop_mobile_and_approval(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 9, 1),
            reason="Synthetic browser fixture only",
            insurance_classification=self.insurance_classification,
            retention_rate=Decimal(10),
            retention_cap=Decimal(12),
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=term,
            reason="Independent synthetic fixture review",
        )
        record = self._verified_record()
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            contract=self.contract,
            actor=self.owner,
            estimate_number="MVP03-BOQ",
            title="برآورد سازه بتنی",
        )
        Contract.objects.bulk_create(
            [
                Contract(
                    organization=self.organization,
                    project=self.project,
                    party=self.party,
                    contract_number=f"SEARCH-{i:03}",
                    title=f"قرارداد نمونه جستجو {i:03}",
                    counterparty_name=self.party.display_name,
                    direction="receivable",
                    status="active",
                )
                for i in range(45)
            ]
        )
        target = Contract.objects.get(
            organization=self.organization, contract_number="SEARCH-044"
        )
        create = reverse("billing:claim_create")
        contract_url = reverse("contracts:detail", args=[self.contract.pk])
        create_context = f"{create}?contract={self.contract.pk}"
        dates = {
            "period_start": format_jalali(date(2026, 9, 1)),
            "period_end": format_jalali(date(2026, 9, 30)),
            "measurement_cutoff": format_jalali(date(2026, 9, 30)),
        }
        base = {
            "status": 200,
            "screenshot": True,
            "absentText": [
                "ClaimAdjustment",
                "contract_term.retention",
                "idempotency",
                "در AR",
            ],
        }

        def scenario(name, path, **kwargs):
            return {**base, "name": name, "path": path, **kwargs}

        self.browser(
            self.owner,
            [
                scenario(
                    "A-estimate-contract-handoff",
                    reverse("estimates:detail", args=[estimate.pk]),
                    steps=[
                        {
                            "clickHref": contract_url + f"?estimate={estimate.pk}",
                            "afterPath": contract_url,
                        }
                    ],
                    mustText=["اجرای سازه بتنی", "برآورد سازه بتنی"],
                ),
                scenario(
                    "B-contract-claim-context",
                    contract_url,
                    steps=[
                        {"clickHref": create_context, "afterPath": create},
                        {
                            "inspect": f"document.querySelector('[name=contract]').value==='{self.contract.pk}' && document.querySelector('[name=baseline]').value==='{record.baseline_id}'",
                            "description": "contract and baseline context retained",
                        },
                    ],
                ),
                scenario(
                    "C-selector-pagination-search",
                    create,
                    steps=[
                        {
                            "searchChoice": {
                                "name": "contract",
                                "query": "SEARCH-044",
                                "value": str(target.pk),
                            }
                        },
                        {
                            "inspect": "document.querySelector('[name=baseline]').value===''",
                            "description": "parent change clears baseline",
                        },
                        {"emptyLookup": "baseline"},
                    ],
                ),
                scenario(
                    "D-invalid-form",
                    create_context,
                    steps=[{"submit": True, "mustText": "این فیلد را تکمیل کنید"}],
                    mustText=["این فیلد را تکمیل کنید"],
                ),
                scenario(
                    "E-create-claim",
                    create_context,
                    steps=[
                        {
                            "fill": dates,
                            "submit": True,
                            "afterPrefix": "/billing/claims/",
                            "mustText": "پیش‌نویس صورت‌وضعیت",
                        }
                    ],
                    mustText=["کسور تضمین", "وضعیت و اقدام بعدی"],
                ),
            ],
        )
        claim = ProgressClaim.objects.get(organization=self.organization)
        self.assertEqual(claim.adjustments.get().amount, Decimal(-6))
        detail = reverse("billing:claim_detail", args=[claim.pk])
        self.browser(
            self.owner,
            [
                scenario(
                    "F-mobile-claim-deductions",
                    detail,
                    mobile=True,
                    mustText=["کسور تضمین", "تاریخ نهایی اندازه‌گیری"],
                ),
                scenario(
                    "G-refresh-deductions",
                    detail,
                    steps=[
                        {
                            "clickSelector": "form[action$='/recalculate/'] button",
                            "afterPath": detail,
                            "mustText": "مقادیر و کسور پیش‌نویس به‌روز شد",
                        }
                    ],
                ),
                scenario(
                    "H-submit-for-approval",
                    detail,
                    steps=[
                        {
                            "clickSelector": "form[action$='/submit/'] button",
                            "afterPath": detail,
                            "mustText": "در انتظار بررسی",
                        }
                    ],
                    mustText=["تصمیم‌گیری بر اساس مسئولیت بررسی"],
                ),
                scenario(
                    "I-filter-empty-state",
                    "/billing/claims/?q=no-such-contract",
                    mustText=["با فیلترهای فعلی نتیجه‌ای یافت نشد"],
                ),
                scenario("J-mobile-create-form", create_context, mobile=True),
                scenario(
                    "K-baseline-detail",
                    reverse("billing:baseline_detail", args=[record.baseline_id]),
                ),
                scenario(
                    "L-progress-list", f"/billing/progress/?contract={self.contract.pk}"
                ),
            ],
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "submitted")
        self.login(self.manager)
        decision_page = self.client.get(detail)
        self.assertTrue(
            decision_page.context["can_decide_claim"],
            "The independent reviewer must retain the existing decision authority.",
        )
        self.browser(
            self.manager,
            [
                scenario(
                    "M-decision-required-reason",
                    detail,
                    steps=[
                        {
                            "clickSelector": "form[action$='/approve/'] button",
                            "mustText": "دلیل تصمیم را وارد کنید",
                        }
                    ],
                ),
                scenario(
                    "N-independent-approval",
                    detail,
                    steps=[
                        {
                            "fill": {"reason": "کنترل مستقل مقدار و کسور"},
                            "submit": True,
                            "formSelector": "form[action$='/approve/']",
                            "afterPath": detail,
                            "mustText": "این نسخه تأیید و نهایی شده",
                        }
                    ],
                    mustText=["کسور تضمین"],
                ),
                scenario(
                    "O-mobile-approved",
                    detail,
                    mobile=True,
                    mustText=["این نسخه تأیید و نهایی شده"],
                ),
            ],
        )
        claim.refresh_from_db()
        self.assertEqual(claim.status, "approved")
        self.assertEqual(claim.approved_by, self.manager)
