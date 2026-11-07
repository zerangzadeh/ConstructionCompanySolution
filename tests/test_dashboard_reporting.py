"""Source-backed Dashboard/Reporting browser evidence on disposable PostgreSQL."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_mvp03_browser as chrome_fixture
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    OrganizationRole,
)
from apps.organizations.services import set_active_organization
from apps.procurement.services import (
    add_goods_receipt_item,
    create_goods_receipt,
    post_goods_receipt,
)
from apps.projects.test_command_center import scoped_reader
from apps.reporting.services import refresh_metric
from core.product_surface import url_exposed
from core.test_home_workspace import HomeWorkspaceFixture
from tests.retirement_fixtures import explicit_fixture_roles

OUT = Path("output/dashboard-reporting/browser")
COMMON = {
    "status": 200,
    "screenshot": True,
    "viewportScreenshot": True,
    "fullPageScreenshot": True,
    "noJsErrors": True,
    "noHttpErrors": True,
    "absentText": ["None", "UUID", "P4-G10", "AP/AR"],
}
GEOMETRY = "document.documentElement.scrollWidth<=innerWidth+1 && getComputedStyle(document.querySelector('main')).direction==='rtl' && document.querySelectorAll('main h1').length===1"


def inspect(expression, description):
    return {"inspect": expression, "description": description}


def screens(name, path, *, checks=(), text=()):
    return [
        {
            **COMMON,
            "name": f"{name}-{width}",
            "path": path,
            "width": width,
            "mobile": width < 640,
            "steps": [
                inspect(GEOMETRY, "RTL, one heading and no page overflow"),
                *checks,
            ],
            "mustText": list(text),
        }
        for width in (1440, 1024, 390)
    ]


def grant_reporting(organization, user):
    role = OrganizationRole.objects.create(
        organization=organization, code="dashboard-report-reader", name="گزارش عملیاتی"
    )
    role.permissions.add(
        *BusinessPermission.objects.filter(code__startswith="reporting.")
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=organization.memberships.get(user=user),
        role=role,
        reason="Synthetic Dashboard/Reporting verification only",
    )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class DashboardReportingBrowserTests(HomeWorkspaceFixture, StaticLiveServerTestCase):
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = OUT

    def test_home_header_context_opens_and_preserves_dashboard_scope(self):
        context = "header .erp-list-context"
        panel = f"{context} .erp-list-context__panel"
        form = f"{panel} form"
        unchanged_chart = (
            "Chart.getChart('home-project-status').data.datasets[0].data.join(',')"
            "==='2,1,1,1,1'"
        )
        self.browser(
            self.owner,
            screens(
                "home-context-open",
                "/",
                checks=[
                    {"toggleSelector": f"{context} summary"},
                    inspect(
                        f"""(() => {{
                            const panel = document.querySelector('{panel}');
                            const bounds = panel.getBoundingClientRect();
                            return panel.closest('details').open
                                && bounds.width > 0
                                && bounds.left >= 0 && bounds.right <= innerWidth
                                && document.querySelectorAll('[data-context-project]').length === 1
                                && document.documentElement.scrollWidth <= innerWidth;
                        }})()""",
                        "single context selector opens inside the viewport",
                    ),
                ],
                text=["اعمال زمینه کاری", "آمار خانه همهٔ پروژه‌های مجاز را پوشش می‌دهد"],
            )
            + [
                {
                    **COMMON,
                    "name": "home-context-apply-and-clear",
                    "path": "/",
                    "width": 390,
                    "mobile": True,
                    "steps": [
                        {"toggleSelector": f"{context} summary"},
                        {
                            "fill": {"project_id": str(self.project.pk)},
                            "submit": True,
                            "formSelector": form,
                            "afterPath": "/",
                        },
                        inspect(
                            f"document.querySelector('{context} .erp-list-context__value')"
                            f".textContent.includes('پروژه نمونه ساحلی') && {unchanged_chart}",
                            "project is persisted without filtering dashboard statistics",
                        ),
                        {"toggleSelector": f"{context} summary"},
                        {
                            "fill": {"project_id": ""},
                            "submit": True,
                            "formSelector": form,
                            "afterPath": "/",
                        },
                        inspect(
                            f"document.querySelector('{form} [data-context-project]').value==='' "
                            f"&& {unchanged_chart}",
                            "clearing project restores the all-projects context",
                        ),
                    ],
                }
            ],
        )

    def test_pilot_home_real_kpis_charts_navigation_and_restricted_scope(self):
        project_url = reverse("projects:detail", args=[self.project.pk])
        self.browser(
            self.owner,
            screens(
                "pilot-project",
                project_url,
                checks=[
                    inspect(
                        "Chart.getChart('project-contracts-chart').data.datasets[0].data.join(',')==='1' && document.querySelectorAll('.erp-dashboard-metric').length>1",
                        "contract chart matches one source contract and real KPI row",
                    ),
                    inspect(
                        "!document.querySelector('#project-progress-chart')",
                        "no invented progress series",
                    ),
                ],
                text=["پروژه نمونه ساحلی", "کارگاه‌ها", "پوشش ناقص"],
            )
            + screens(
                "home",
                "/",
                checks=[
                    inspect(
                        "Chart.getChart('home-project-status').data.datasets[0].data.join(',')==='2,1,1,1,1'",
                        "chart equals authorized project status source counts",
                    )
                ],
                text=["میز کار من", "مرور حوزه‌ها"],
            )
            + [
                {
                    **COMMON,
                    "name": "pilot-chart-fallback",
                    "path": project_url,
                    "width": 390,
                    "blockedURLs": ["*chart.umd.min.js*"],
                    "steps": [
                        inspect(
                            "!document.querySelector('[data-chart-ready]') && document.querySelector('#project-contracts-chart-values').innerText.includes('فعال')",
                            "exact source values survive chart library failure",
                        )
                    ],
                },
                {
                    **COMMON,
                    "name": "pilot-no-js",
                    "path": project_url,
                    "noJS": True,
                    "mustText": ["وضعیت قراردادهای پروژه", "فعال"],
                },
                {
                    **COMMON,
                    "name": "pilot-contract-drilldown",
                    "path": project_url,
                    "steps": [
                        {
                            "clickHref": reverse("contracts:list")
                            + f"?project_id={self.project.pk}",
                            "afterPath": reverse("contracts:list"),
                        },
                        inspect(
                            f"new URLSearchParams(location.search).get('project_id')==='{self.project.pk}'",
                            "existing drilldown preserves project query scope",
                        ),
                    ],
                    "mustText": ["قرارداد اجرای سازه"],
                },
            ],
        )
        self.browser(
            self.reader,
            screens(
                "restricted-project",
                project_url,
                checks=[
                    inspect(
                        "document.querySelectorAll('.erp-dashboard-metric').length===3 && !document.querySelector('#project-cost-chart') && !document.querySelector('[data-kpi-tone=cost]')",
                        "only authorized budget, contract and daily report metrics remain",
                    )
                ],
            ),
        )
        self.login(self.reader)
        self.assertEqual(
            self.client.get(
                reverse("projects:detail", args=[self.other_project.pk])
            ).status_code,
            403,
        )

    def test_reporting_populated_incomplete_empty_and_permissions(self):
        grant_reporting(self.organization, self.owner)
        url = reverse("reporting:dashboard")
        self.browser(
            self.owner,
            screens(
                "reporting-empty", url, text=["نتیجه قابل نمایشی برای شما موجود نیست."]
            ),
        )
        incomplete = refresh_metric(
            organization=self.organization,
            actor=self.owner,
            metric_code="procurement_cycle_time",
            idempotency_key="ui-incomplete",
        )
        self.assertFalse(incomplete.coverage["complete"])
        self.browser(
            self.owner,
            screens(
                "reporting-incomplete", url, text=["نتیجه برای تصمیم‌گیری آماده نیست"]
            ),
        )
        order, item = self.create_issued_order()
        receipt = create_goods_receipt(
            organization=self.organization,
            actor=self.member,
            purchase_order=order,
            receipt_number="UI-REPORT-RECEIPT",
            received_at=timezone.now(),
        )
        add_goods_receipt_item(
            organization=self.organization,
            actor=self.member,
            goods_receipt=receipt,
            purchase_order_item=item,
            quantity=Decimal(10),
        )
        post_goods_receipt(
            organization=self.organization, actor=self.owner, goods_receipt=receipt
        )
        # Fixed source timestamps make the existing duration deterministic.
        start = timezone.now() - timedelta(hours=2)
        type(order.purchase_request).objects.filter(
            pk=order.purchase_request_id
        ).update(submitted_at=start)
        type(receipt).objects.filter(pk=receipt.pk).update(
            posted_at=start + timedelta(seconds=7200)
        )
        result = refresh_metric(
            organization=self.organization,
            actor=self.owner,
            metric_code="procurement_cycle_time",
            idempotency_key="ui-complete",
        )
        self.assertEqual(result.value, {"average_seconds": 7200, "completed_cycles": 1})
        self.login(self.owner)
        response = self.client.get(url)
        cards = response.context["read_model"].layers[0].cards
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].result.pk, result.pk)
        self.assertTrue(cards[0].usable)
        self.assertContains(response, "7,200")
        self.browser(
            self.owner,
            screens(
                "reporting-populated",
                url,
                text=["زمان چرخه تدارکات", "7,200", "کامل طبق منبع"],
                checks=[
                    inspect(
                        "document.querySelectorAll('.erp-insight-card').length===1 && !document.querySelector('main form')",
                        "one latest operational source result; hidden export/refresh stay absent",
                    )
                ],
            ),
        )
        for link in self.client.get(url).context["read_model"].layers:
            self.assertTrue(all(not card.can_drillthrough for card in link.cards))
        self.assertFalse(url_exposed(reverse("reporting:export")))
        self.browser(
            self.reader,
            [
                {
                    "name": "reporting-denied",
                    "path": url,
                    "status": 403,
                    "screenshot": True,
                }
            ],
        )

    def test_specialized_empty_pages_and_denied_reports(self):
        pages = {
            "comparison-empty": reverse(
                "projects:controls_comparison", args=[self.project.pk]
            ),
            "exceptions-empty": reverse(
                "projects:controls_exceptions", args=[self.project.pk]
            ),
            "valuation-empty": reverse("inventory:valuation_workbench"),
            "commercial-empty": reverse("billing:commercial_control_dashboard"),
            "statutory-empty": reverse("billing:statutory_operations_dashboard"),
        }
        self.browser(
            self.owner,
            [
                scenario
                for name, path in pages.items()
                for scenario in screens(name, path)
            ],
        )
        denied, _, _ = scoped_reader(
            self.organization, self.project, ["projects.view"], username="report-denied"
        )
        self.browser(
            denied,
            [
                {
                    "name": name + "-denied",
                    "path": path,
                    "status": 403,
                    "screenshot": True,
                }
                for name, path in pages.items()
            ],
        )

    def test_specialized_header_keyboard_and_empty_state(self):
        checks = [
            {"pressTab": True},
            inspect(
                "(()=>{const a=document.querySelector('main .erp-page-header__action');if(!a)return false;a.focus();return document.activeElement===a && parseInt(getComputedStyle(a).outlineWidth)>=2;})()",
                "existing create action uses accepted header and visible keyboard focus",
            ),
            {"pressTab": True},
            inspect(
                "document.activeElement.closest('main')!==null",
                "native Tab continues into contextual navigation",
            ),
            inspect(
                "(()=>{const regions=[...document.querySelectorAll('main .erp-report-table')];return regions.length>0 && regions.every(r=>r.tabIndex===0 && r.getAttribute('aria-label') && [...r.querySelectorAll('thead th')].every(th=>th.scope==='col'));})()",
                "empty report tables retain labeled keyboard regions and column headings",
            ),
        ]
        self.browser(
            self.owner,
            screens(
                "commercial-keyboard-empty",
                reverse("billing:commercial_control_dashboard"),
                checks=checks,
                text=["مواجهه فعال ثبت نشده است."],
            )
            + screens(
                "statutory-keyboard-empty",
                reverse("billing:statutory_operations_dashboard"),
                checks=checks,
                text=["صورتحسابی ثبت نشده است."],
            ),
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class ProjectReportSourceBrowserTests(StaticLiveServerTestCase):
    from apps.projects.test_command_center import CostEvidenceFixture
    from apps.projects.test_p4_s31_s34 import ProjectControlPresentationTests

    make_cost_fixture = CostEvidenceFixture.make_cost_fixture
    _draft = CostEvidenceFixture._draft
    _classify_and_submit = CostEvidenceFixture._classify_and_submit
    _approved_expense = ProjectControlPresentationTests._approved_expense
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = OUT

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        set_active_organization(session, self.organization)
        session.save()

    def test_nonempty_comparison_exceptions_and_full_project_export(self):
        self.make_cost_fixture()
        self._approved_expense(
            amount="120.00", key="ui-report-expense", source="UI-EXPENSE"
        )
        comparison = reverse("projects:controls_comparison", args=[self.project.pk])
        exceptions = reverse("projects:controls_exceptions", args=[self.project.pk])
        response = self.client.get(comparison)
        self.assertEqual(response.status_code, 200)
        row = response.context["comparison"].lines[0]
        self.assertEqual(row.accepted_budget_amount, Decimal(100))
        self.assertEqual(row.approved_or_recorded_expense_amount, Decimal(120))
        self.assertEqual(row.remaining_amount, Decimal(-20))
        self.assertNotContains(response, str(self.budget.pk))
        export = self.client.get(
            reverse("projects:controls_export", args=[self.project.pk])
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"accepted_budget_vs_expense", export.content)
        self.assertIn(b"120.00", export.content)
        self.assertIn(b"advisory_overrun_evidence", export.content)
        self.browser(
            self.preparer,
            screens(
                "comparison-populated", comparison, text=["100", "120", "-20", "ریال"]
            )
            + screens(
                "exceptions-populated", exceptions, text=["فقط مشورتی", "120", "ریال"]
            ),
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class CommercialDashboardSourceBrowserTests(StaticLiveServerTestCase):
    from apps.billing.test_commercial_controls import CommercialControlTests

    make_evidence = CommercialControlTests.make_evidence
    base_setup = CommercialControlTests.base_setup
    _guarantee = CommercialControlTests._guarantee
    _approve_guarantee = CommercialControlTests._approve_guarantee
    login = ProjectReportSourceBrowserTests.login
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = OUT

    def test_commercial_source_amounts_dates_and_navigation(self):
        from apps.billing import test_commercial_controls as fixture
        from apps.contracts.models import RetentionReleaseRequirement

        original = fixture.create_project

        def authorized_project(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return original(**kwargs)

        with patch.object(fixture, "create_project", side_effect=authorized_project):
            self.base_setup(
                slug="ui-commercial",
                release_requirement=RetentionReleaseRequirement.EVIDENCE_ONLY,
            )
        self.evidence = self.make_evidence("guarantee-evidence")
        guarantee = self._approve_guarantee(self._guarantee())
        self.login(self.owner)
        url = reverse("billing:commercial_control_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        groups = response.context["exposure"]["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["amount"], guarantee.amount)
        self.browser(
            self.owner,
            screens("commercial-populated", url, text=["G-001", "ریال", "مواجهه فعال"]),
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class StatutoryReportSourceBrowserTests(StaticLiveServerTestCase):
    from apps.billing.test_statutory_compliance import StatutoryComplianceFixture

    _contract = StatutoryComplianceFixture._contract
    _policy = StatutoryComplianceFixture._policy
    _claim = StatutoryComplianceFixture._claim
    _certificate = StatutoryComplianceFixture._certificate
    _approved_invoice = StatutoryComplianceFixture._approved_invoice
    login = ProjectReportSourceBrowserTests.login
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = OUT

    def test_statutory_source_records_and_existing_export(self):
        from apps.billing import test_statutory_compliance as fixture
        from apps.billing.statutory_services import record_statutory_submission

        original = fixture.create_project

        def authorized_project(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return original(**kwargs)

        with patch.object(fixture, "create_project", side_effect=authorized_project):
            fixture.StatutoryComplianceFixture.setUp(self)
        invoice = self._approved_invoice()
        record_statutory_submission(
            organization=self.organization,
            actor=self.owner,
            target=invoice,
            idempotency_key="ui-statutory-export",
            correlation_id=uuid4(),
            adapter=fixture.AcceptingAdapter(),
        )
        self.login(self.owner)
        url = reverse("billing:statutory_operations_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["invoices"].first().total_amount, invoice.total_amount
        )
        self.assertNotContains(response, str(invoice.series_id))
        self.browser(
            self.owner,
            screens(
                "statutory-populated",
                url,
                text=[invoice.source_claim.claim_number, "ریال"],
            ),
        )


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class InventoryReportSourceBrowserTests(StaticLiveServerTestCase):
    from apps.inventory.tests import InventoryFixtureMixin

    create_and_post = InventoryFixtureMixin.create_and_post
    login = ProjectReportSourceBrowserTests.login
    browser = chrome_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = chrome_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = OUT

    def test_valuation_exact_source_units_and_history(self):
        from apps.inventory import tests as fixture
        from apps.inventory.models import StockTransactionType
        from apps.inventory.p8_services import finalize_valuation
        from apps.organizations.models import (
            OrganizationSettings,
            PlatformPolicy,
            PlatformPolicyVersion,
            TenantPolicySelection,
        )
        from apps.organizations.policy_specs import (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
            get_platform_policy_spec,
            initial_accounting_policy_parameters,
        )

        original = fixture.create_warehouse

        def authorized_warehouse(**kwargs):
            explicit_fixture_roles(kwargs["organization"])
            return original(**kwargs)

        with patch.object(
            fixture, "create_warehouse", side_effect=authorized_warehouse
        ):
            fixture.InventoryFixtureMixin.setUp(self)
        OrganizationSettings.objects.get_or_create(organization=self.organization)
        self.material.name = "سیمان نمونه"
        self.material.save(update_fields=["name"])
        self.unit.symbol = "کیلوگرم"
        self.unit.save(update_fields=["symbol"])
        membership = self.organization.memberships.get(user=self.owner)
        now = timezone.now()
        for code in (
            ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
            ACCOUNTING_ROUNDING_POLICY_CODE,
        ):
            spec = get_platform_policy_spec(code)
            policy = PlatformPolicy.objects.create(
                code=code,
                name=spec.name,
                category=spec.category,
                sensitivity=spec.sensitivity,
                tenant_selectable=spec.tenant_selectable,
                requires_source_provenance=False,
                created_by=self.owner,
                updated_by=self.owner,
            )
            version = PlatformPolicyVersion.objects.create(
                policy=policy,
                version=1,
                parameters=initial_accounting_policy_parameters(code),
                effective_from=timezone.localdate(),
                status="published",
                source_basis="product_defined",
                created_by=self.owner,
                published_by=self.owner,
                published_at=now,
                reason="Isolated UI source fixture",
            )
            TenantPolicySelection.objects.create(
                organization=self.organization,
                policy=policy,
                policy_version=version,
                status="active",
                approved_by=membership,
                approved_at=now,
                applied_by=membership,
                applied_at=now,
                reason="Isolated UI source fixture",
            )
        movement = self.create_and_post(
            number="UI-VALUED-01",
            transaction_type=StockTransactionType.ADJUSTMENT_IN,
            quantity=Decimal(10),
            destination=self.central,
            actor=self.owner,
        )
        event = finalize_valuation(
            organization=self.organization,
            actor=self.owner,
            stock_transaction=movement,
            source_reference="UI-APPROVED-SOURCE",
            source_version="1",
            unit_cost=Decimal("1234.5"),
            idempotency_key="ui-valued-01",
        )
        self.assertEqual(event.value_amount, Decimal(12345))
        self.login(self.owner)
        url = reverse("inventory:valuation_workbench")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["pools"][0].value_amount, event.value_after)
        self.browser(
            self.owner,
            screens(
                "valuation-populated",
                url,
                text=["سیمان نمونه", "کیلوگرم", "12,345", "1,234.5", "ریال"],
            ),
        )
