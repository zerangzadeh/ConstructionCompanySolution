"""Real installed Chrome against isolated, explicitly authorized test data."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.estimates.services import create_estimate
from apps.projects.models import (
    Project,
    ProjectCostFactKind,
    ProjectCostMeasure,
    ProjectSite,
)
from apps.projects.test_command_center import CostEvidenceFixture, scoped_reader
from core.jalali import format_jalali


def inspect(expression, description):
    return {"inspect": expression, "description": description}


BASE = {
    "status": 200,
    "screenshot": True,
    "noJsErrors": True,
    "noHttpErrors": True,
    "absentText": [
        "UUID",
        "None",
        "ProjectCost",
        "source_model",
        "producer_key",
        "receivable",
        "payable",
    ],
}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ProjectWorkspaceBrowserTests(
    CostEvidenceFixture, JourneyFixture, StaticLiveServerTestCase
):
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/projects-ui-20261103/browser"
    )

    def test_projects_list_journeys_and_command_center_states(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه مرجع ساحلی"
        self.project.code = "PRJ-REF-01"
        self.project.status = "active"
        self.project.start_date = date(2026, 10, 1)
        self.project.save()
        self._claim()
        create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="REF-E-01",
            title="برآورد اجرای سازه ساحلی",
        )
        Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="REF-C-02",
            title="اجرای تأسیسات ساحلی",
            counterparty_name="تأسیسات نمونه",
            status="draft",
        )
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="REF-S",
            name="کارگاه ساحلی",
        )
        DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 10, 1),
            work_performed="اجرای سازه",
            created_by=self.owner,
        )
        empty = Project.objects.create(
            organization=self.organization, code="EMPTY", name="پروژه آغازین"
        )
        Project.objects.bulk_create(
            [
                Project(
                    organization=self.organization,
                    code=f"PAGE-{i:03}",
                    name=f"پروژه صفحه {i:03}",
                    status="active",
                )
                for i in range(31)
            ]
        )
        listing = reverse("projects:list")
        detail = reverse("projects:detail", args=[self.project.pk])
        query = "?q=PAGE&status=active&sort=code&direction=asc"
        retained = "new URLSearchParams(location.search).get('q')==='PAGE' && new URLSearchParams(location.search).get('status')==='active'"
        chart_ready = "document.querySelectorAll('[data-chart-ready]').length===1 && !!Chart.getChart('project-contracts-chart')"
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": "PRJ-list-desktop",
                    "path": listing,
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-more-filters]').open && document.querySelector('.erp-list-identifier bdi').dir==='ltr' && !document.querySelector('main input[type=checkbox]')",
                            "compact default filters and canonical identifiers",
                        ),
                        inspect(
                            "!!Chart.getChart('projects-status-chart') && Chart.getChart('projects-status-chart').data.datasets[0].data.reduce((a,b)=>a+b,0)===33 && Chart.getChart('projects-status-chart').data.labels.length===5 && document.querySelectorAll('[data-project-status]').length===4",
                            "all authorized projects and every real model status",
                        ),
                    ],
                },
                {
                    **BASE,
                    "name": "PRJ-search-status-chips",
                    "path": listing,
                    "steps": [
                        {
                            "fill": {"q": "PRJ-REF", "status": "active"},
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        inspect(
                            "document.querySelectorAll('tbody tr').length===1 && document.querySelectorAll('[data-filter-chip]').length===2",
                            "search code and real status",
                        ),
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": listing,
                        },
                        inspect(
                            "!new URLSearchParams(location.search).has('status') && new URLSearchParams(location.search).get('q')==='PRJ-REF'",
                            "individual chip removal",
                        ),
                        {
                            "clickSelector": "[data-table-filter-clear]",
                            "afterPath": listing,
                        },
                        inspect(
                            "!location.search && !document.querySelector('[data-filter-chip]')",
                            "clear all",
                        ),
                    ],
                    "mustText": ["پروژه جدید"],
                },
                {
                    **BASE,
                    "name": "PRJ-search-name",
                    "path": listing + "?q=ساحلی",
                    "mustText": ["پروژه مرجع ساحلی"],
                    "steps": [
                        inspect(
                            "document.querySelectorAll('tbody tr').length===1",
                            "search by Persian project name",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PRJ-advanced-dates",
                    "path": listing,
                    "steps": [
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "document.querySelector('[data-more-filters]').open",
                            "description": "advanced opens",
                        },
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "!document.querySelector('[data-more-filters]').open",
                            "description": "advanced closes",
                        },
                        {"toggleSelector": "[data-more-toggle]"},
                        {
                            "fill": {
                                "start_date_from": format_jalali(date(2026, 10, 1)),
                                "start_date_to": format_jalali(date(2026, 10, 1)),
                            },
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "#list-more-filters button[type=submit]",
                            "afterPath": listing,
                        },
                        inspect(
                            "document.querySelectorAll('tbody tr').length===1 && document.querySelectorAll('[data-filter-chip]').length===2 && document.querySelector('[data-more-filters]').open",
                            "supported dates retained as chips",
                        ),
                    ],
                },
                {
                    **BASE,
                    "name": "PRJ-pagination-sort",
                    "path": listing + query,
                    "steps": [
                        {"clickSelector": "[rel=next]", "afterPath": listing},
                        inspect(
                            retained
                            + " && new URLSearchParams(location.search).get('page')==='2' && document.querySelectorAll('tbody tr').length===6",
                            "pagination preserves filters",
                        ),
                        {
                            "clickSelector": "th a[href*='sort=name']",
                            "afterPath": listing,
                        },
                        inspect(
                            retained
                            + " && !new URLSearchParams(location.search).has('page')",
                            "sorting preserves filters and resets page",
                        ),
                    ],
                },
                {
                    **BASE,
                    "name": "PRJ-navigation",
                    "path": listing + "?q=PRJ-REF",
                    "steps": [
                        {"clickSelector": ".erp-list-title a", "afterPath": detail},
                        inspect(
                            "document.querySelector('h1').textContent.includes('ساحلی')",
                            "project opens command center",
                        ),
                        {"history": "back"},
                    ],
                    "mustText": ["پروژه‌ها"],
                },
                {**BASE, "name": "PRJ-list-tablet", "path": listing, "width": 1024},
                {
                    **BASE,
                    "name": "PRJ-list-mobile",
                    "path": listing + query,
                    "mobile": True,
                    "steps": [
                        inspect(
                            "getComputedStyle(document.querySelector('tbody tr')).display==='grid' && document.querySelector('.erp-list-identifier bdi').dir==='ltr'",
                            "mobile cards and LTR code",
                        ),
                        {"toggleSelector": "[data-filter-options] > summary"},
                        {
                            "toggleSelector": "[data-more-filters] > summary",
                            "inspect": "document.querySelector('[data-more-filters]').open",
                            "description": "mobile advanced panel",
                        },
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-rich-desktop",
                    "path": detail,
                    "mustText": [
                        "مرکز کنترل پروژه",
                        "آخرین موارد ثبت‌شده",
                        "کارگاه ساحلی",
                        "پوشش ناقص",
                    ],
                    "steps": [inspect(chart_ready, "real status chart mounted")],
                    "mustLinks": [
                        reverse("contracts:list") + f"?project_id={self.project.pk}",
                        reverse("projects:site_list", args=[self.project.pk]),
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-rich-tablet",
                    "path": detail,
                    "width": 1024,
                    "steps": [
                        inspect(
                            chart_ready
                            + " && getComputedStyle(document.querySelector('.erp-project-analytics')).gridTemplateColumns.split(' ').length===1",
                            "tablet analytics stack",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-rich-mobile",
                    "path": detail,
                    "mobile": True,
                    "steps": [
                        inspect(
                            chart_ready
                            + " && document.querySelector('canvas').getBoundingClientRect().right<=innerWidth",
                            "mobile chart fits viewport",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-responsive-resize",
                    "path": detail,
                    "steps": [
                        {
                            "resize": {"width": 390},
                            **inspect(
                                chart_ready
                                + " && document.documentElement.scrollWidth<=innerWidth && Chart.getChart('project-contracts-chart').width<390",
                                "chart resizes to mobile",
                            ),
                        },
                        {
                            "resize": {"width": 1440},
                            **inspect(
                                chart_ready
                                + " && document.documentElement.scrollWidth<=innerWidth && Chart.getChart('project-contracts-chart').width>200",
                                "chart resizes back to desktop",
                            ),
                        },
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-chart-library-failure",
                    "path": detail,
                    "blockedURLs": ["*chart.umd.min.js*"],
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-chart-ready]') && document.querySelector('#project-contracts-chart-values').innerText.includes('فعال')",
                            "exact fallback remains when library fails",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-no-javascript",
                    "path": detail,
                    "noJS": True,
                    "mustText": ["وضعیت قراردادهای پروژه", "فعال", "پوشش ناقص"],
                },
                {
                    **BASE,
                    "name": "PCC-empty",
                    "path": reverse("projects:detail", args=[empty.pk]),
                    "mustText": ["هنوز قراردادی برای نمایش", "شواهد هم‌ارز کافی"],
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-chart-ready]')",
                            "no fabricated empty charts",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-contract-handoff",
                    "path": detail,
                    "steps": [
                        {
                            "clickHref": reverse("contracts:list")
                            + f"?project_id={self.project.pk}",
                            "afterPath": reverse("contracts:list"),
                        }
                    ],
                    "mustText": ["فهرست به سوابق قابل مشاهده این پروژه محدود است."],
                },
            ],
        )
        user, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["projects.view"],
            username="browser-reader",
        )
        self.browser(
            user,
            [
                {
                    **BASE,
                    "name": "PCC-restricted-desktop",
                    "path": detail,
                    "absentText": [
                        *BASE["absentText"],
                        "هزینه ثبت‌شده",
                        "برآورد، قرارداد و صورت‌وضعیت",
                    ],
                    "steps": [
                        inspect(
                            "!document.querySelector('canvas') && document.querySelectorAll('.erp-project-kpis article').length===1",
                            "no unauthorized metrics",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-restricted-mobile",
                    "path": detail,
                    "mobile": True,
                },
                {
                    **BASE,
                    "name": "PRJ-restricted-list",
                    "path": listing,
                    "absentText": ["پروژه جدید", "پروژه صفحه", "پروژه آغازین"],
                    "steps": [
                        inspect(
                            "document.querySelectorAll('tbody tr').length===1 && Chart.getChart('projects-status-chart').data.datasets[0].data.reduce((a,b)=>a+b,0)===1",
                            "project isolation includes summary and chart",
                        )
                    ],
                },
            ],
        )

    def test_real_cost_chart_and_incomplete_coverage(self):
        self.make_cost_fixture()
        self.project.name = "پروژه هزینه طبقه‌بندی‌شده"
        self.project.save()
        source = self._contract(ProjectCostMeasure.ACTUAL)
        self._fact(
            source, ProjectCostFactKind.ACTUAL_RECOGNIZED, "123.45", "PCC-BROWSER"
        )
        detail = reverse("projects:detail", args=[self.project.pk])
        ready = "!!Chart.getChart('project-cost-chart') && Chart.getChart('project-cost-chart').data.datasets[0].data[1]===123.45"
        self.browser(
            self.preparer,
            [
                {
                    **BASE,
                    "name": "PCC-cost-evidence-desktop",
                    "path": detail,
                    "mustText": ["پوشش ناقص", "بودجه و هزینه ثبت‌شده"],
                    "steps": [
                        inspect(
                            ready, "real producer-cost projection visualized exactly"
                        ),
                        inspect(
                            "Chart.getChart('project-cost-chart').options.plugins.tooltip.callbacks.label({dataIndex:1}).includes('۱۲۳٫۴۵') && Chart.getChart('project-cost-chart').options.plugins.tooltip.rtl",
                            "Persian exact-value financial tooltip",
                        ),
                        {
                            "toggleSelector": ".erp-project-evidence summary",
                            "inspect": "document.querySelector('.erp-project-evidence').open",
                            "description": "source coverage accessible",
                        },
                    ],
                },
                {
                    **BASE,
                    "name": "PCC-cost-evidence-mobile",
                    "path": detail,
                    "mobile": True,
                    "steps": [
                        inspect(
                            ready
                            + " && Chart.getChart('project-cost-chart').width<390",
                            "real cost chart fits mobile",
                        )
                    ],
                },
            ],
        )

    def test_reference_layout_and_empty_list_with_local_assets(self):
        """Synthetic source records, never values inferred from reference images."""
        self.make_fixture(persian=True)
        self.project.name = "ساختمان خدمات مهندسی"
        self.project.description = "اجرای ساختمان اداری و محوطه‌سازی مجموعه خدمات مهندسی"
        self.project.estimated_budget = Decimal(280000000000)
        self.project.start_date = date(2026, 7, 12)
        self.project.end_date = date(2027, 9, 20)
        self.project.save()
        for code, name, status, budget in (
            ("PRJ-02", "مجتمع مسکونی سپیدار", "active", "190000000000"),
            ("PRJ-03", "بهسازی مرکز آموزشی", "on_hold", "65000000000"),
            ("PRJ-04", "توسعه ساختمان درمانگاه", "active", "95000000000"),
        ):
            Project.objects.create(
                organization=self.organization,
                code=code,
                name=name,
                status=status,
                estimated_budget=Decimal(budget),
                start_date=date(2026, 7, 12),
                end_date=date(2027, 9, 20),
            )
        for status in ("draft", "completed"):
            Contract.objects.create(
                organization=self.organization,
                project=self.project,
                contract_number=f"VIS-{status}",
                title="قرارداد اجرای تأسیسات",
                counterparty_name="پیمانکار نمونه",
                status=status,
            )
        self._claim()
        create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            estimate_number="VIS-E",
            title="برآورد اجرای ساختمان",
        )
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="VIS-S",
            name="کارگاه ساختمان خدمات مهندسی",
        )
        DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 10, 1),
            work_performed="اجرای ساختمان",
            created_by=self.owner,
        )
        listing = reverse("projects:list")
        detail = reverse("projects:detail", args=[self.project.pk])
        profile = "!!document.querySelector('header a[href*=profile]') || document.querySelector('header').innerText.includes('تنظیمات شخصی')"
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": "visual-list-1672",
                    "width": 1672,
                    "height": 941,
                    "path": listing,
                    "steps": [
                        inspect(
                            "Chart.getChart('projects-status-chart').data.datasets[0].data.join(',')==='2,1,1,0,0'",
                            "real grouped statuses",
                        ),
                        inspect(profile, "profile and personal settings preserved"),
                    ],
                },
                {
                    **BASE,
                    "name": "visual-detail-1672",
                    "width": 1672,
                    "height": 941,
                    "path": detail,
                    "steps": [
                        inspect(
                            "Chart.getChart('project-contracts-chart').data.datasets[0].data.join(',')==='1,1,1' && !document.getElementById('project-cost-chart')",
                            "real contracts and unavailable financial comparison",
                        )
                    ],
                },
                {**BASE, "name": "visual-list-390", "mobile": True, "path": listing},
                {**BASE, "name": "visual-detail-390", "mobile": True, "path": detail},
                {
                    **BASE,
                    "name": "list-filtered-empty",
                    "path": listing + "?q=absent-project",
                    "mustText": ["نتیجه‌ای"],
                    "steps": [
                        inspect(
                            "!!Chart.getChart('projects-status-chart') && !document.querySelector('tbody')",
                            "filtered empty keeps authorized overview",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "list-chart-library-failure",
                    "path": listing,
                    "blockedURLs": ["*chart.umd.min.js*"],
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-chart-ready]') && document.querySelector('#projects-status-chart-values').innerText.includes('فعال')",
                            "server values survive asset failure",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "list-no-javascript",
                    "path": listing,
                    "noJS": True,
                    "mustText": ["توزیع وضعیت پروژه‌ها", "بهسازی مرکز آموزشی"],
                },
            ],
        )
        reader, _, _ = scoped_reader(
            self.organization,
            self.project,
            ["projects.view"],
            username="empty-list-reader",
        )
        from django.utils import timezone

        self.project.deleted_at = timezone.now()
        self.project.save(update_fields=["deleted_at"])
        self.browser(
            reader,
            [
                {
                    **BASE,
                    "name": "list-empty-desktop",
                    "path": listing,
                    "mustText": ["هنوز پروژه‌ای برای نمایش نمودار وجود ندارد."],
                    "steps": [
                        inspect(
                            "!document.querySelector('canvas') && !document.querySelector('tbody')",
                            "no fabricated empty chart",
                        )
                    ],
                },
                {**BASE, "name": "list-empty-mobile", "path": listing, "mobile": True},
            ],
        )
