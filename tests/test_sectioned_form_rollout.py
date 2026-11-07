"""Sectioned Form browser and request verification through supported MVP routes."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from django import forms
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_warehouse_reference_list import RenderedControls, WarehouseListFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.daily_reports.models import DailyReport
from apps.expenses.models import Expense, PlatformExpenseGroup
from apps.organizations.models import BusinessPermission
from apps.projects.models import ProjectSite
from apps.quality import workflow as quality_workflow
from apps.quality.models import QualityIssue
from apps.safety import workflow as safety_workflow
from apps.safety.models import SafetyIncident
from apps.workflows.models import WorkflowTemplate, WorkflowType
from core.forms import parse_jalali_datetime


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class SectionedFormRolloutTests(WarehouseListFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/sectioned-form-rollout")

    def verify_pages(self, records):
        scenarios = []
        for name, route, cancel_route, payload, required in records:
            url = reverse(route)
            cancel_url = reverse(cancel_route)
            self.login(self.owner)
            response = self.client.get(url)
            form = response.context["form"]
            names = [
                attrs.get("name")
                for _tag, attrs in RenderedControls(response.content).nodes
            ]
            for field in form:
                self.assertEqual(names.count(field.name), 1, field.name)
            for width in (1440, 1024, 390):
                scenarios.append(
                    {
                        "name": f"{name}-{width}",
                        "path": url,
                        "width": width,
                        "status": 200,
                        "screenshot": True,
                        "viewportScreenshot": True,
                        "fullPageScreenshot": True,
                        "bottomScreenshot": True,
                        "noJsErrors": True,
                        "steps": [
                            {
                                "inspect": f"""(() => {{
                            const form = document.querySelector('main .erp-sectioned-form');
                            const grids = [...form.querySelectorAll('.erp-form-grid')];
                            return document.documentElement.dir === 'rtl' && grids.length >= 3
                                && grids.every(grid => getComputedStyle(grid).gridTemplateColumns.split(' ').length === (innerWidth < 640 ? 1 : 2))
                                && document.querySelectorAll('[data-context-project]').length === 1
                                && form.querySelectorAll('button[type=submit]').length === 1
                                && form.querySelectorAll('footer').length === 1
                                && getComputedStyle(form.querySelector('footer')).position === 'static'
                                && form.querySelector('footer a').getAttribute('href') === '{cancel_url}'
                                && !form.querySelector('details,[type=file]');
                        }})()""",
                                "description": "RTL sections, one global context, supported controls and in-flow actions",
                            }
                        ],
                    }
                )
            scenarios.append(
                {
                    "name": f"{name}-keyboard",
                    "path": url,
                    "status": 200,
                    "steps": [
                        {
                            "inspect": "(() => {const controls = [...document.querySelectorAll('main .erp-sectioned-form input:not([type=hidden]), main .erp-sectioned-form select, main .erp-sectioned-form textarea, main .erp-sectioned-form button, main .erp-sectioned-form a[href]')].filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length); window.expectedSectionedTabTarget = controls[1]; controls[0].focus(); return true;})()",
                            "description": "focus the first project selector",
                        },
                        {"pressTab": True},
                        {
                            "inspect": "document.activeElement === window.expectedSectionedTabTarget",
                            "description": "Tab advances to the next enabled form control",
                        },
                    ],
                }
            )
        self.browser(self.owner, scenarios)

        journeys = []
        for name, route, cancel_route, payload, required in records:
            url = reverse(route)
            cancel_url = reverse(cancel_route)
            invalid = self.client.post(url, {**payload, required: ""})
            self.assertEqual(invalid.status_code, 200)
            self.assertIn(required, invalid.context["form"].errors)
            self.assertContains(invalid, f'id="id_{required}-errors"')
            for key, value in payload.items():
                if key != required:
                    bound = invalid.context["form"][key]
                    retained = bound.value()
                    if isinstance(bound.field, forms.DateTimeField):
                        self.assertEqual(
                            datetime.fromisoformat(retained),
                            parse_jalali_datetime(value),
                        )
                        continue
                    if isinstance(bound.field, forms.DateField):
                        retained = bound.field.widget.format_value(retained)
                    self.assertEqual(retained, str(value))
            journeys.append(
                {
                    "name": f"{name}-validation",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "screenshot": True,
                    "viewportScreenshot": True,
                    "fullPageScreenshot": True,
                    "steps": [
                        {
                            "inspect": "document.querySelector('.erp-sectioned-form').noValidate = true",
                            "description": "exercise server validation",
                        },
                        {
                            "fill": {
                                **{key: str(value) for key, value in payload.items()},
                                required: "",
                            },
                            "submit": True,
                            "afterPath": url,
                        },
                        {
                            "inspect": f"document.querySelector('#id_{required}').getAttribute('aria-describedby').includes('id_{required}-errors') && document.querySelector('#id_{required}-errors').offsetHeight > 0",
                            "description": "the associated error remains visible in its section",
                        },
                    ],
                }
            )
            journeys.append(
                {
                    "name": f"{name}-save",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "steps": [
                        {
                            "fill": {key: str(value) for key, value in payload.items()},
                            "submit": True,
                        },
                        {
                            "inspect": "!document.querySelector('.erp-sectioned-form')",
                            "description": "valid submission follows the existing success destination",
                        },
                    ],
                }
            )
            journeys.append(
                {
                    "name": f"{name}-cancel",
                    "path": url,
                    "width": 390,
                    "status": 200,
                    "steps": [
                        {
                            "clickSelector": "main .erp-sectioned-form footer a",
                            "afterPath": cancel_url,
                        }
                    ],
                }
            )
        self.browser(self.owner, journeys)
        self.login(self.denied)
        for _name, route, _cancel, payload, _required in records:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
            self.assertEqual(self.client.post(reverse(route), payload).status_code, 403)

    def test_safety_quality_daily_report(self):
        self.make_fixture()
        for module in (safety_workflow, quality_workflow):
            WorkflowTemplate.objects.get_or_create(
                workflow_type=WorkflowType.objects.get(code=module.WORKFLOW_TYPE_CODE),
                code=module.TEMPLATE_CODE,
                defaults={
                    "name": module.TEMPLATE_CODE,
                    "configuration": module.COMPATIBILITY_CONFIGURATION,
                },
            )
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="SECTIONED-SITE",
            name="کارگاه آزمون بخش‌بندی",
        )
        records = [
            (
                "safety",
                "safety:create",
                "safety:list",
                {
                    "project": self.project.pk,
                    "site": site.pk,
                    "incident_number": "SECTIONED-S",
                    "occurred_at": "1405/07/23 12:00",
                    "incident_type": "near_miss",
                    "severity": "low",
                    "description": "شرح حادثه آزمایشی",
                    "immediate_action": "اقدام فوری آزمایشی",
                },
                "description",
            ),
            (
                "quality",
                "quality:create",
                "quality:list",
                {
                    "project": self.project.pk,
                    "site": site.pk,
                    "issue_number": "SECTIONED-Q",
                    "identified_at": "1405/07/23 12:00",
                    "issue_type": "nonconformance",
                    "severity": "minor",
                    "description": "شرح مسئله آزمایشی",
                    "specification_reference": "مرجع آزمون",
                },
                "description",
            ),
            (
                "daily-report",
                "daily_reports:create",
                "daily_reports:list",
                {
                    "project": self.project.pk,
                    "site": site.pk,
                    "reporting_date": "1405/07/23",
                    "labor_count": "0",
                    "work_performed": "فعالیت آزمایشی",
                },
                "work_performed",
            ),
        ]
        self.verify_pages(records)
        for model in (SafetyIncident, QualityIssue, DailyReport):
            self.assertEqual(
                model.objects.filter(organization=self.organization).count(), 1
            )
        self.reader_scope.membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=(
                    "safety_incidents.create",
                    "quality_issues.create",
                    "daily_reports.create",
                )
            )
        )
        self.login(self.reader)
        for _name, route, _cancel, payload, _required in records:
            response = self.client.post(
                reverse(route), {**payload, "project": self.hidden_project.pk}
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("project", response.context["form"].errors)

    def test_expense_pilot(self):
        self.make_fixture()
        group, _created = PlatformExpenseGroup.objects.get_or_create(
            code="materials", defaults={"name": "مصالح آزمایشی"}
        )
        payload = {
            "project": self.project.pk,
            "category": group.code,
            "description": "هزینه آزمایشی",
            "amount": "125000",
            "incurred_on": "1405/07/23",
            "notes": "توضیحات آزمایشی",
        }
        records = [
            ("expense", "expenses:create", "expenses:list", payload, "description"),
            (
                "expense-draft",
                "expenses:draft_create",
                "expenses:list",
                {
                    **payload,
                    "classification": "direct",
                    "source_reference": "SECTIONED-TEST",
                    "idempotency_key": str(uuid4()),
                },
                "description",
            ),
        ]
        self.verify_pages(records)
        self.assertEqual(
            Expense.objects.filter(
                organization=self.organization, description="هزینه آزمایشی"
            ).count(),
            2,
        )
        self.reader_scope.membership.role_definition.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=("expenses.create", "expenses.view")
            )
        )
        self.login(self.reader)
        for _name, route, _cancel, data, _required in records:
            response = self.client.post(
                reverse(route), {**data, "project": self.hidden_project.pk}
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("project", response.context["form"].errors)
            self.assertNotIn(
                self.hidden_project, response.context["form"].fields["project"].queryset
            )
