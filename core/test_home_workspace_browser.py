"""Real installed Chrome verification of the personalized Home workspace."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project
from core.test_home_workspace import HomeWorkspaceFixture

BASE = {
    "path": "/",
    "status": 200,
    "screenshot": True,
    "noJsErrors": True,
    "noHttpErrors": True,
    "absentText": ["سمت ثبت نشده", "None", "UUID"],
}


def inspect(expression, description):
    return {"inspect": expression, "description": description}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class HomeWorkspaceBrowserTests(HomeWorkspaceFixture, StaticLiveServerTestCase):
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    browser_evidence_directory = (
        Path(__file__).resolve().parents[1] / "output/home-workspace-20261104/browser"
    )

    def test_desktop_tablet_mobile_donut_and_links(self):
        checks = [
            inspect(
                "Chart.getChart(document.querySelector('#home-project-status')).data.datasets[0].data.join(',')==='2,1,1,1,1'",
                "exact authorized status counts",
            ),
            inspect(
                "document.querySelectorAll('.home-metric').length===5",
                "five real KPI cards",
            ),
            inspect(
                "document.querySelectorAll('.home-tasks li').length>0",
                "source-backed pending work",
            ),
            inspect(
                "Chart.getChart('home-project-status').options.plugins.tooltip.rtl===true",
                "Persian RTL tooltip",
            ),
        ]
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": f"home-{width}",
                    "width": width,
                    "mobile": width < 640,
                    "steps": checks,
                    "mustText": ["میز کار من", "قرارداد اجرای سازه", "مرور حوزه‌ها"],
                    "absentText": [
                        *BASE["absentText"],
                        "قرارداد سازمان دیگر",
                        "پروژه حذف‌شده",
                    ],
                }
                for width in [1672, 1440, 1024, 390]
            ]
            + [{**BASE, "name": "home-full-desktop", "height": 1250, "steps": checks}],
        )

    def test_restricted_home_and_zero_data(self):
        self.browser(
            self.reader,
            [
                {
                    **BASE,
                    "name": "restricted",
                    "steps": [
                        inspect(
                            "Chart.getChart('home-project-status').data.datasets[0].data.join(',')==='0,1,0,0,0'",
                            "project scope respected",
                        )
                    ],
                    "absentText": [
                        *BASE["absentText"],
                        "خارج از محدوده",
                        "قرارداد سازمان دیگر",
                        "درخواست‌های خرید ارسال‌شده",
                    ],
                },
                {**BASE, "name": "restricted-mobile", "mobile": True},
            ],
        )
        self.organization = create_organization_with_owner(
            owner=self.owner, name="سازمان خالی نمونه", slug="browser-home-empty"
        )
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": "empty",
                    "mustText": [
                        "پروژه‌ای برای نمایش وجود ندارد.",
                        "کاری در انتظار اقدام شما نیست.",
                    ],
                    "steps": [
                        inspect(
                            "!document.querySelector('#home-project-status') && [...document.querySelectorAll('.home-metric__value')].every(e=>e.dataset.value==='0')",
                            "real zero values without fabricated chart",
                        )
                    ],
                },
                {**BASE, "name": "empty-mobile", "mobile": True},
            ],
        )

        Project.objects.create(
            organization=self.organization,
            code="SECOND",
            name="پروژه سازمان دوم",
            status="completed",
        )
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": "organization-switch",
                    "mustText": ["پروژه سازمان دوم"],
                    "absentText": [
                        *BASE["absentText"],
                        "قرارداد اجرای سازه",
                        "پروژه نمونه ساحلی",
                    ],
                    "steps": [
                        inspect(
                            "Chart.getChart('home-project-status').data.datasets[0].data.join(',')==='0,0,0,1,0'",
                            "active organization data replaced",
                        )
                    ],
                }
            ],
        )

    def test_chart_fallback_and_persian_tooltip(self):
        self.browser(
            self.owner,
            [
                {
                    **BASE,
                    "name": "chart-library-failure",
                    "blockedURLs": ["*chart.umd.min.js*"],
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-chart-ready]') && document.querySelector('#home-project-status-values').innerText.includes('فعال')",
                            "server-rendered status counts survive asset failure",
                        )
                    ],
                },
                {
                    **BASE,
                    "name": "no-javascript",
                    "noJS": True,
                    "mustText": [
                        "وضعیت پروژه‌ها",
                        "پروژه‌های فعال",
                        "قرارداد اجرای سازه",
                    ],
                },
                {
                    **BASE,
                    "name": "persian-tooltip",
                    "steps": [
                        inspect(
                            "(()=>{const c=Chart.getChart('home-project-status');const t=c.options.plugins.tooltip;return t.textDirection==='rtl' && t.callbacks.label({dataIndex:1})==='فعال: ۱ پروژه';})()",
                            "tooltip formats exact source values in Persian",
                        )
                    ],
                },
            ],
        )
