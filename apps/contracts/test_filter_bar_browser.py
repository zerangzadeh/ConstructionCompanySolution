"""Actual Chrome interactions for Filter Bar, URL history and parent context."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.contracts.models import Contract
from apps.projects.models import Project


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContractFilterBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2]
        / "output/mvp-03/contract-filter-bar/browser"
    )

    def test_filter_bar_desktop_mobile_and_real_history(self):
        self.make_fixture(persian=True)
        self.project.name = "پروژه پل ساحلی"
        self.project.save()
        payable = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            party=self.party,
            contract_number="SIDE-2026",
            title="اجرای دیوار ساحلی",
            counterparty_name="ساحل سازان نمونه",
            direction="payable",
            status="draft",
        )
        listing = reverse("contracts:list")
        scoped = listing + f"?project_id={self.project.pk}"
        project_url = reverse("projects:detail", args=[self.project.pk])
        payable_link = reverse("contracts:detail", args=[payable.pk])
        receivable_link = reverse("contracts:detail", args=[self.contract.pk])
        combined = {"q": "ساحلی", "status": "draft", "side": "payable"}
        base = {
            "status": 200,
            "screenshot": True,
            "absentText": ["receivable", "payable", "دریافتنی", "پرداختنی"],
        }

        def inspect(expression, description):
            return {"inspect": expression, "description": description}

        def values(side="payable"):
            return inspect(
                f"document.querySelector('main [name=q]').value==='ساحلی' && document.querySelector('main [name=status]').value==='draft' && document.querySelector('main [name=side]').value==='{side}'",
                "rendered inputs match restored URL state",
            )

        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "FB-01-general-desktop",
                    "path": listing,
                    "mustLinks": [payable_link, receivable_link],
                    "mustText": [
                        "سمت قرارداد",
                        "با کارفرما",
                        "با پیمانکار / تأمین‌کننده",
                    ],
                    "steps": [
                        inspect(
                            "document.querySelectorAll('main [data-filter-bar]').length===1 && !document.querySelector('main [data-table-filter-row]') && !!document.querySelector('main [name=project]').tomselect",
                            "shared bar replaces column inputs and enhances Project search",
                        )
                    ],
                },
                {
                    **base,
                    "name": "FB-02-combined-submit",
                    "path": listing,
                    "steps": [
                        {
                            "fill": combined,
                            "formSelector": "#list-filter-bar",
                            "inspect": "!location.search",
                            "description": "explicit Apply prevents premature filter navigation",
                        },
                        {"clickSelector": "[data-filter-apply]", "afterPath": listing},
                        values(),
                        inspect(
                            "document.querySelectorAll('[data-filter-chip]').length===3",
                            "all active constraints are visible as chips",
                        ),
                    ],
                    "mustLinks": [payable_link],
                    "absentLinks": [receivable_link],
                },
                {
                    **base,
                    "name": "FB-03-chip-back-forward-refresh",
                    "path": listing,
                    "steps": [
                        {
                            "fill": combined,
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        {
                            "clickSelector": "[data-filter-chip=side]",
                            "afterPath": listing,
                        },
                        values(""),
                        {"history": "back"},
                        values(),
                        {"history": "forward"},
                        values(""),
                        {"reload": True, "afterPath": listing},
                        values(""),
                    ],
                },
                {
                    **base,
                    "name": "FB-04-clear-general",
                    "path": listing + "?q=ساحلی&status=draft&side=payable",
                    "steps": [
                        {
                            "clickSelector": "[data-filter-bar] [data-table-filter-clear]",
                            "afterPath": listing,
                        },
                        inspect(
                            "!location.search && document.querySelectorAll('[data-filter-chip]').length===0",
                            "clear restores unfiltered authorized list",
                        ),
                    ],
                    "mustLinks": [payable_link, receivable_link],
                },
                {
                    **base,
                    "name": "FB-05-receivable-side",
                    "path": listing + "?side=receivable",
                    "mustLinks": [receivable_link],
                    "absentLinks": [payable_link],
                    "mustText": ["سمت قرارداد: با کارفرما"],
                },
                {
                    **base,
                    "name": "FB-06-payable-side",
                    "path": listing + "?side=payable",
                    "mustLinks": [payable_link],
                    "absentLinks": [receivable_link],
                    "mustText": ["سمت قرارداد: با پیمانکار / تأمین‌کننده"],
                },
                {
                    **base,
                    "name": "FB-07-project-entry",
                    "path": project_url,
                    "steps": [
                        {"clickHref": scoped, "afterPath": listing},
                        inspect(
                            "!document.querySelector('main [name=project]') && !!document.querySelector('main [name=project_id]')",
                            "inherited Project is context, not another selector",
                        ),
                    ],
                    "mustText": [self.project.name],
                },
                {
                    **base,
                    "name": "FB-08-project-submit-clear",
                    "path": scoped,
                    "steps": [
                        {
                            "fill": combined,
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        values(),
                        {
                            "clickSelector": "[data-filter-chip=status]",
                            "afterPath": listing,
                        },
                        inspect(
                            f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}' && document.querySelector('main [name=side]').value==='payable'",
                            "removing one filter retains Project and other filters",
                        ),
                        {
                            "clickSelector": "[data-filter-bar] [data-table-filter-clear]",
                            "afterPath": listing,
                        },
                        inspect(
                            f"location.search==='?project_id={self.project.pk}' && !document.querySelector('main [name=project]')",
                            "clear retains inherited Project",
                        ),
                    ],
                    "mustLinks": [payable_link, receivable_link],
                },
                {
                    **base,
                    "name": "FB-09-general-mobile",
                    "path": listing,
                    "mobile": True,
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-filter-options]').open && document.querySelector('main [name=q]').getBoundingClientRect().width>180",
                            "mobile Search stays visible with compact filter disclosure",
                        )
                    ],
                },
                {
                    **base,
                    "name": "FB-10-mobile-apply",
                    "path": listing,
                    "mobile": True,
                    "steps": [
                        {
                            "toggleSelector": "[data-filter-options] > summary",
                            "inspect": "document.querySelector('[data-filter-options]').open",
                            "description": "mobile filters expand",
                        },
                        {
                            "fill": combined,
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        values(),
                        inspect(
                            "document.querySelectorAll('[data-filter-chip]').length===3 && !document.querySelector('[data-filter-options]').open",
                            "chips stay visible after mobile controls collapse",
                        ),
                    ],
                    "mustLinks": [payable_link],
                    "absentLinks": [receivable_link],
                },
                {
                    **base,
                    "name": "FB-11-project-mobile",
                    "path": scoped + "&side=payable",
                    "mobile": True,
                    "steps": [
                        {
                            "clickSelector": "[data-filter-bar] [data-table-filter-clear]",
                            "afterPath": listing,
                        },
                        inspect(
                            f"location.search==='?project_id={self.project.pk}'",
                            "mobile clear preserves Project",
                        ),
                    ],
                    "mustText": [self.project.name],
                },
                {
                    **base,
                    "name": "FB-12-more-filters",
                    "path": listing,
                    "steps": [
                        {
                            "toggleSelector": "[data-more-toggle]",
                            "inspect": "document.querySelector('[data-more-filters]').open",
                            "description": "secondary filters open from toolbar",
                        },
                        {
                            "fill": {"number": "SIDE-2026"},
                            "formSelector": "#list-filter-bar",
                            "clickSelector": "[data-filter-apply]",
                            "afterPath": listing,
                        },
                        inspect(
                            "document.querySelector('[data-more-filters]').open && !!document.querySelector('[data-filter-chip=number]')",
                            "bookmarked secondary constraints remain visible",
                        ),
                    ],
                    "mustLinks": [payable_link],
                    "absentLinks": [receivable_link],
                },
                {
                    **base,
                    "name": "FB-13-empty-results",
                    "path": listing + "?q=cannot-match",
                    "mustText": ["با فیلترهای فعلی نتیجه‌ای یافت نشد.", "0 قرارداد"],
                    "steps": [
                        inspect(
                            "!!document.querySelector('[data-filter-chip=q]') && !!document.querySelector('[data-filter-bar] button[type=submit]')",
                            "empty results retain recovery and controls",
                        )
                    ],
                },
                {
                    **base,
                    "name": "FB-14-no-javascript",
                    "path": scoped + "&side=payable",
                    "noJS": True,
                    "mustLinks": [payable_link],
                    "absentLinks": [receivable_link],
                    "mustText": ["سمت قرارداد: با پیمانکار / تأمین‌کننده"],
                },
            ],
        )

        projects = [
            Project(
                organization=self.organization,
                name=f"پروژه گزینه {i:03}",
                code=f"OPTION-{i:03}",
            )
            for i in range(45)
        ]
        Project.objects.bulk_create(projects)
        Contract.objects.bulk_create(
            [
                Contract(
                    organization=self.organization,
                    project=p,
                    contract_number=f"OPTION-C-{i:03}",
                    title=f"قرارداد گزینه {i:03}",
                    counterparty_name="نمونه",
                )
                for i, p in enumerate(projects)
            ]
        )
        target = projects[-1]
        self.browser(
            self.owner,
            [
                {
                    **base,
                    "name": "FB-15-project-search-beyond-window",
                    "path": listing,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": target.name,
                                "value": str(target.pk),
                            }
                        },
                        {"clickSelector": "[data-filter-apply]", "afterPath": listing},
                        inspect(
                            f"new URLSearchParams(location.search).get('project')==='{target.pk}' && !new URLSearchParams(location.search).has('project_id') && !!document.querySelector('main [name=project]')",
                            "transient Project is removable and is not inherited context",
                        ),
                        {"reload": True, "afterPath": listing},
                        inspect(
                            f"document.querySelector('main [name=project]').value==='{target.pk}'",
                            "remote selected Project remains pinned after refresh",
                        ),
                    ],
                },
                {
                    **base,
                    "name": "FB-16-project-filter-chip-clear",
                    "path": listing + f"?project={target.pk}",
                    "mobile": True,
                    "steps": [
                        {
                            "clickSelector": "[data-filter-chip=project]",
                            "afterPath": listing,
                        },
                        inspect(
                            "!location.search",
                            "removing transient Project restores permitted general scope",
                        ),
                    ],
                },
            ],
        )
        from apps.accounts.models import User
        from apps.organizations.models import (
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )

        denied_actor = User.objects.create_user(username="filter-no-read")
        denied_role = OrganizationRole.objects.create(
            organization=self.organization,
            code="filter-no-read",
            name="بدون دسترسی قرارداد",
        )
        membership = self.organization.memberships.create(
            user=denied_actor, status="active", role_definition=denied_role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=denied_role,
            reason="Explicit denied browser fixture",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="organization",
            reason="Scope does not grant missing permission",
        )
        self.browser(
            denied_actor,
            [
                {
                    "name": "FB-17-permission-denied",
                    "path": listing,
                    "status": 403,
                    "screenshot": True,
                }
            ],
        )
