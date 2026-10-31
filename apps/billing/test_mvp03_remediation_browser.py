"""Chrome verification of the targeted MVP-03 presentation remediation."""

from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.services import create_progress_record, request_progress_verification
from apps.billing.test_mvp03_remediation import RemediationFixture
from apps.contracts.models import Contract
from apps.estimates.models import Estimate
from apps.estimates.services import create_estimate
from apps.projects.models import Project
from core.jalali import format_jalali


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RemediationBrowserTests(RemediationFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/remediation-20261030/browser"
    )

    def test_targeted_context_status_and_visual_remediation(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه نمونه سازه"
        self.project.save()
        Contract.objects.filter(pk=self.contract.pk).update(
            signed_at=date(2026, 9, 1),
            start_date=date(2026, 9, 2),
            end_date=date(2026, 9, 30),
        )
        states = self.claim_states()
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=self.contract,
            estimate_number="UI-EST",
            title="برآورد سازه پروژه",
        )
        empty = Project.objects.create(
            organization=self.organization, code="UI-EMPTY", name="پروژه بدون سابقه"
        )

        def url(route, **query):
            return reverse(route) + ("?" + urlencode(query) if query else "")

        project = reverse("projects:detail", args=[self.project.pk])
        contracts = url("contracts:list", project_id=self.project.pk)
        estimates = url(
            "estimates:list", project_id=self.project.pk, contract=self.contract.pk
        )
        claims = url(
            "billing:claim_list", project_id=self.project.pk, contract=self.contract.pk
        )
        placement = """(() => {
          const h=document.querySelector('main h1');
          const f=document.querySelector('main [data-table-filter-controls], main #journey-search, main #claim-search');
          const n=document.querySelector('[data-billing-navigation]');
          return (!f || !!(h.compareDocumentPosition(f)&Node.DOCUMENT_POSITION_FOLLOWING)) &&
            (!n || n.querySelectorAll('.erp-btn--active[aria-current=page]').length===1) &&
            ![...document.querySelectorAll('main a[dir=ltr]')].some(a=>/[آ-ی]/.test(a.textContent));
        })()"""

        def scenario(name, path, **kwargs):
            return {
                "name": name,
                "path": path,
                "status": 200,
                "screenshot": True,
                "absentText": [
                    "ClaimAdjustment",
                    "idempotency",
                    "contract_term.retention",
                    "در AR",
                ],
                "steps": [
                    {
                        "inspect": placement,
                        "description": "header/filter order, visible active navigation and Persian direction",
                    }
                ],
                **kwargs,
            }

        scenarios = [
            scenario(
                "UI-01-project-hub",
                project,
                mustText=[
                    "برآورد، قرارداد و صورت‌وضعیت پروژه",
                    "مشاهده همه برآوردهای پروژه",
                    "مشاهده همه قراردادهای پروژه",
                    "مشاهده همه صورت‌وضعیت‌های پروژه",
                ],
            ),
            scenario("UI-02-project-mobile", project, mobile=True),
        ]
        for name, route, title in (
            ("baseline", "billing:baseline_list", "مبناهای اندازه‌گیری"),
            ("progress", "billing:progress_list", "پیشرفت کار"),
        ):
            path = url(route, contract=self.contract.pk)
            scenarios.append(
                scenario(
                    "UI-03-title-" + name,
                    path,
                    steps=[
                        {
                            "inspect": f"document.title==='{title} | بنیرا' && "
                            + placement,
                            "description": "plain title and active navigation",
                        }
                    ],
                )
            )
            scenarios.append(
                scenario(
                    "UI-04-clear-" + name,
                    path + "&q=ui-no-result",
                    steps=[
                        {"clickHref": path, "afterPath": reverse(route)},
                        {
                            "inspect": f"new URLSearchParams(location.search).get('contract')==='{self.contract.pk}' && !new URLSearchParams(location.search).has('q')",
                            "description": "Contract context retained when clearing query",
                        },
                    ],
                )
            )
        for name, path, route in (
            ("contracts", contracts, "contracts:list"),
            ("estimates", estimates, "estimates:list"),
            ("claims", claims, "billing:claim_list"),
        ):
            parameter = "q" if name == "claims" else "title"
            filtered = path + f"&{parameter}=ui-no-result"
            scenarios.append(
                scenario(
                    "UI-05-filtered-empty-" + name,
                    filtered,
                    mustText=["با فیلترهای فعلی نتیجه‌ای یافت نشد."],
                )
            )
            scenarios.append(
                scenario(
                    "UI-06-clear-" + name,
                    filtered,
                    steps=[
                        {"clickHref": path, "afterPath": reverse(route)},
                        {
                            "inspect": f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}' && !new URLSearchParams(location.search).has('{parameter}')",
                            "description": "clearing temporary filters retains Project/Contract context",
                        },
                        {
                            "inspect": placement,
                            "description": "filter controls follow page identity",
                        },
                    ],
                )
            )
            scenarios.append(
                scenario(
                    "UI-07-true-empty-" + name,
                    url(route, project_id=empty.pk),
                    mustText=["هنوز"],
                    absentText=["با فیلترهای فعلی نتیجه‌ای یافت نشد."],
                )
            )
        for state in ("superseded", "cancelled"):
            scenarios.append(
                scenario(
                    "UI-08-status-filter-" + state,
                    reverse("billing:claim_list"),
                    steps=[
                        {
                            "fill": {"status": state},
                            "clickSelector": "form[aria-label='فیلتر صورت‌وضعیت‌ها'] button",
                            "afterPath": reverse("billing:claim_list"),
                        },
                        {
                            "inspect": f"new URLSearchParams(location.search).get('status')==='{state}' && document.querySelectorAll('tbody tr').length===1",
                            "description": "all supported status options filter the scoped source",
                        },
                    ],
                    mustText=[states[state].get_status_display()],
                )
            )
        for state, claim in states.items():
            path = reverse("billing:claim_detail", args=[claim.pk])
            for mobile in (False, True):
                scenarios.append(
                    scenario(
                        f"UI-09-{state}-{'mobile' if mobile else 'desktop'}",
                        path,
                        mobile=mobile,
                        mustText=[claim.get_status_display(), "وضعیت و اقدام بعدی"],
                        steps=[
                            {
                                "inspect": "document.querySelector('h1').textContent.includes('نسخه') && "
                                + placement,
                                "description": "specific Claim identity and source state actions",
                            }
                        ],
                    )
                )
        scenarios.append(
            scenario(
                "UI-10-contract-identity-dates",
                reverse("contracts:detail", args=[self.contract.pk]),
                steps=[
                    {
                        "inspect": f"document.querySelector('main bdi[dir=ltr]').textContent==='{self.contract.contract_number}' && document.querySelector('main').innerText.replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).includes('{format_jalali(date(2026, 9, 1))}')",
                        "description": "canonical LTR contract number and Jalali display",
                    }
                ],
            )
        )
        scenarios.append(
            scenario(
                "UI-11-estimate-contract-handoff",
                reverse("estimates:detail", args=[estimate.pk]),
                steps=[
                    {
                        "clickHref": reverse(
                            "contracts:detail", args=[self.contract.pk]
                        ),
                        "afterPath": reverse(
                            "contracts:detail", args=[self.contract.pk]
                        ),
                    }
                ],
            )
        )
        for state in ("approved", "revised", "archived"):
            item = create_estimate(
                organization=self.organization,
                actor=self.owner,
                project=self.project,
                estimate_number="UI-" + state,
                title="برآورد نمونه "
                + dict(Estimate._meta.get_field("status").choices)[state],
            )
            Estimate.objects.filter(pk=item.pk).update(status=state)
            scenarios.append(
                scenario(
                    "UI-12-estimate-" + state,
                    reverse("estimates:detail", args=[item.pk]),
                    mobile=state == "archived",
                    absentText=["این برآورد تأیید شده"] if state != "approved" else [],
                )
            )
        baseline = states["draft"].baseline
        record = create_progress_record(
            organization=self.organization,
            actor=self.owner,
            baseline=baseline,
            baseline_item=baseline.items.get(),
            period_start=date(2026, 12, 1),
            period_end=date(2026, 12, 31),
            measured_on=date(2026, 12, 10),
            source_type="site_report",
            source_reference="UI-REASON",
            period_quantity="0.5000",
            cumulative_quantity="0.5000",
        )
        request_progress_verification(
            organization=self.organization, actor=self.owner, record=record
        )
        progress = reverse("billing:progress_detail", args=[record.pk])
        scenarios.append(
            scenario(
                "UI-13-progress-visible-reasons",
                progress,
                mobile=True,
                mustText=["دلیل راستی‌آزمایی", "دلیل رد اندازه‌گیری"],
                steps=[
                    {
                        "inspect": "document.querySelectorAll('textarea[name=reason][required]').length===2 && !document.querySelector('#progress-reject-reason').checkValidity()",
                        "description": "visible labels, multiline required reasons",
                    }
                ],
            )
        )
        for start in range(0, len(scenarios), 8):
            self.browser(self.owner, scenarios[start : start + 8])
        self.browser(
            self.manager,
            [
                scenario(
                    "UI-14-progress-rejection",
                    progress,
                    steps=[
                        {
                            "fill": {"reason": "شرح کافی برای بازبینی اندازه‌گیری"},
                            "formSelector": "form[action$='/reject/']",
                            "clickSelector": "form[action$='/reject/'] button",
                            "afterPath": progress,
                            "mustText": "پیشرفت رد شد",
                        }
                    ],
                    mustText=["پیشرفت رد شد"],
                )
            ],
        )
