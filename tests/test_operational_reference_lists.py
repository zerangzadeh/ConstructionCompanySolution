"""Isolated PostgreSQL/Chrome evidence for Expenses, Safety and Quality lists."""

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.expenses.models import Expense, PlatformExpenseGroup
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident


@override_settings(
    PRODUCT_SURFACE_PROFILE="FULL_ERP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class OperationalListBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown

    def test_reference_lists(self):
        self.make_fixture(persian=True)
        PlatformExpenseGroup.objects.get_or_create(
            code="other", defaults={"name": "سایر"}
        )
        phase = os.environ.get("BONIRA_LIST_PHASE", "after")
        self.browser_evidence_directory = (
            Path("output/operational-reference-lists") / phase
        )
        common = {
            "organization": self.organization,
            "project": self.project,
            "created_by": self.owner,
            "updated_by": self.owner,
        }
        for index in range(28):
            Expense.objects.create(
                **common,
                description=f"هزینه نمونه {index:02}",
                category="other",
                amount=Decimal("1250000.50"),
                incurred_on=date(2026, 10, 1),
            )
            SafetyIncident.objects.create(
                **common,
                incident_number=f"SAFE-{index:02}",
                incident_type="near_miss",
                severity="high",
                occurred_at=timezone.now(),
                description="حادثه نمونه",
            )
            QualityIssue.objects.create(
                **common,
                issue_number=f"QUAL-{index:02}",
                issue_type="defect",
                severity="minor",
                identified_at=timezone.now(),
                description="مسئله نمونه",
            )
        scenarios = []
        for path in ("expenses", "safety", "quality", "contracts"):
            for width in (1440, 1024, 390):
                scenarios.append(
                    {
                        "name": f"{path}-{width}",
                        "path": f"/{path}/",
                        "width": width,
                        "screenshot": True,
                        "status": 200,
                        "steps": []
                        if phase == "before"
                        else [
                            {
                                "inspect": "!!document.querySelector('.erp-reference-list') && !document.querySelector('[data-more-filters][open]')",
                                "description": "reference layout and advanced filters collapsed by default",
                            }
                        ],
                    }
                )
        self.browser(self.owner, scenarios)
        if phase == "before":
            return
        scenarios = []
        for domain, search, value, quick, selected, date_field, sort in (
            (
                "expenses",
                "description",
                "هزینه نمونه",
                "category",
                "other",
                "incurred_on",
                "description",
            ),
            ("safety", "number", "SAFE", "severity", "high", "occurred_at", "number"),
            (
                "quality",
                "number",
                "QUAL",
                "severity",
                "minor",
                "identified_at",
                "number",
            ),
        ):
            path = f"/{domain}/"
            query = f"?{search}={value}&{quick}={selected}&sort={sort}&direction=asc"

            def inspect(expression, description):
                return {"inspect": expression, "description": description}

            for width in (1440, 1024, 390):
                scenarios.append(
                    {
                        "name": f"{domain}-interactions-{width}",
                        "path": path + query,
                        "width": width,
                        "status": 200,
                        "screenshot": True,
                        "steps": [
                            {"clickSelector": "[rel=next]", "afterPath": path},
                            inspect(
                                f"document.querySelectorAll('tbody tr').length===3 && new URLSearchParams(location.search).get('page')==='2' && new URLSearchParams(location.search).has('{search}') && new URLSearchParams(location.search).get('{quick}')==='{selected}' && new URLSearchParams(location.search).get('sort')==='{sort}'",
                                "pagination retains filters and sort",
                            ),
                            {
                                "clickSelector": f"[data-filter-chip={quick}]",
                                "afterPath": path,
                            },
                            inspect(
                                f"!new URLSearchParams(location.search).has('{quick}') && !new URLSearchParams(location.search).has('page') && new URLSearchParams(location.search).has('{search}')",
                                "individual chip removal",
                            ),
                            {
                                "clickSelector": "[data-table-filter-clear]",
                                "afterPath": path,
                            },
                            inspect(
                                f"!new URLSearchParams(location.search).has('{search}') && new URLSearchParams(location.search).get('sort')==='{sort}'",
                                "clear preserves sorting",
                            ),
                            {
                                "toggleSelector": "[data-more-toggle]"
                                if width == 1440
                                else "[data-more-filters] > summary"
                            },
                            inspect(
                                "document.querySelector('[data-more-filters]').open",
                                "advanced filters open",
                            ),
                            {
                                "fill": {
                                    search: value,
                                    quick: selected,
                                    f"{date_field}_from": "1405/07/01",
                                },
                                "clickSelector": "[data-more-filters] button[type=submit]",
                                "afterPath": path,
                            },
                            inspect(
                                f"document.querySelector('[data-filter-chip={date_field}_from]')!==null",
                                "Jalali date filter and chip",
                            ),
                            {"toggleSelector": ".erp-list-sort-menu summary"},
                            {
                                "clickSelector": f".erp-list-sort-menu a[href*='sort={sort}']",
                                "afterPath": path,
                            },
                            inspect(
                                f"new URLSearchParams(location.search).has('{date_field}_from')",
                                "sorting retains date filter",
                            ),
                            {"toggleSelector": ".erp-list-row-menu summary"},
                            inspect(
                                "document.querySelector('.erp-list-row-menu').open && document.querySelector('.erp-list-row-menu a').target==='_blank'",
                                "legitimate detail row action",
                            ),
                        ],
                    }
                )
            scenarios.append(
                {
                    "name": f"{domain}-filtered-empty",
                    "path": path + f"?{search}=NO-MATCH",
                    "status": 200,
                    "screenshot": True,
                    "mustText": ["با فیلترهای فعلی نتیجه‌ای یافت نشد"],
                }
            )
            scenarios.append(
                {
                    "name": f"{domain}-detail-and-back",
                    "path": path + query,
                    "status": 200,
                    "screenshot": True,
                    "steps": [
                        {
                            "clickSelector": ".erp-list-title a"
                            if domain == "expenses"
                            else ".erp-list-identifier a",
                            "afterPrefix": path,
                        },
                        {"history": "back"},
                        inspect(
                            f"new URLSearchParams(location.search).has('{search}')",
                            "detail navigation and back retain search",
                        ),
                    ],
                }
            )
        self.browser(self.owner, scenarios)
        from apps.accounts.models import User
        from apps.organizations.models import (
            BusinessPermission,
            MembershipRoleAssignment,
            MembershipScopeGrant,
            OrganizationRole,
        )
        from apps.projects.models import Project

        reader = User.objects.create_user(username="operational-list-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization,
            code="operational-reader",
            name="مشاهده سوابق",
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "expenses.view",
                    "safety_incidents.view",
                    "quality_issues.view",
                ]
            )
        )
        membership = self.organization.memberships.create(
            user=reader, status="active", role_definition=role
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Synthetic read-only verification",
        )
        grant = MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="project",
            project=self.project,
            reason="Synthetic read-only project scope",
        )
        self.browser(
            reader,
            [
                {
                    "name": f"{d}-restricted",
                    "path": f"/{d}/",
                    "width": 390,
                    "status": 200,
                    "screenshot": True,
                    "absentLinks": [
                        "/expenses/drafts/new/",
                        "/safety/new/",
                        "/quality/new/",
                        "/expenses/recurrences/",
                    ],
                    "steps": [
                        inspect(
                            "!document.querySelector('main .erp-page-header__action')",
                            "view-only user has no create CTA",
                        )
                    ],
                }
                for d in ("expenses", "safety", "quality")
            ],
        )
        empty_project = Project.objects.create(
            organization=self.organization, code="LIST-EMPTY", name="پروژه بدون سابقه"
        )
        grant.project = empty_project
        grant.save()
        self.browser(
            reader,
            [
                {
                    "name": f"{d}-genuine-empty",
                    "path": f"/{d}/",
                    "status": 200,
                    "screenshot": True,
                    "mustText": ["هنوز"],
                    "absentText": ["با فیلترهای فعلی نتیجه‌ای یافت نشد"],
                }
                for d in ("expenses", "safety", "quality")
            ],
        )
