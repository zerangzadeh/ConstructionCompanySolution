"""Detail presentation adoption through the actual authorized MVP routes."""

from datetime import date, timedelta
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from test_daily_report_references import DailyReferenceFixture

from apps.billing import test_mvp03_browser as browser_fixture
from apps.daily_reports.references import create_report_with_references
from apps.equipment.models import Equipment, MaintenanceRecord
from apps.equipment.p8_models import EquipmentWorkOrder
from apps.expenses.models import ExpenseCategory, PlatformExpenseGroup
from apps.materials.models import Material, MaterialCategory, UnitOfMeasure
from apps.organizations.models import BusinessPermission, MembershipScopeGrant
from apps.parties.models import BusinessParty
from apps.quality.record_review import submit_quality_record
from apps.safety.record_review import submit_safety_record


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class RecordDetailAdoptionTests(DailyReferenceFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/detail-page-rollout/adopters")

    def setup_adopters(self):
        self.setup_daily()
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="DETAIL-U",
            name="عدد",
            symbol="عدد",
            category="count",
        )
        category = MaterialCategory.objects.create(
            organization=self.organization, code="DETAIL-C", name="دسته نمونه"
        )
        material = Material.objects.create(
            organization=self.organization,
            code="DETAIL-M",
            name="مصالح نمونه جزئیات",
            category=category,
            unit_of_measure=unit,
        )
        group, _ = PlatformExpenseGroup.objects.get_or_create(
            code="materials", defaults={"name": "مصالح"}
        )
        expense_category = ExpenseCategory.objects.create(
            organization=self.organization,
            code="DETAIL-XC",
            name="دسته هزینه نمونه",
            primary_group=group,
        )
        equipment = Equipment.objects.create(
            organization=self.organization,
            code="DETAIL-E",
            name="تجهیز نمونه جزئیات",
            category="ماشین‌آلات",
            ownership_type="owned",
            created_by=self.owner,
            updated_by=self.owner,
        )
        maintenance = MaintenanceRecord.objects.create(
            organization=self.organization,
            equipment=equipment,
            project=self.project,
            site=self.site,
            record_number="DETAIL-MR",
            summary="سرویس نمونه",
            maintenance_type="preventive",
            scheduled_date=date(2026, 11, 5),
            created_by=self.owner,
            updated_by=self.owner,
        )
        order = EquipmentWorkOrder.objects.create(
            organization=self.organization,
            equipment=equipment,
            number="DETAIL-WO",
            summary="دستورکار نمونه",
            created_by=self.owner,
        )
        party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind="company",
            display_name="طرف تجاری نمونه",
            legal_name="شرکت نمونه",
            created_by=self.owner,
            updated_by=self.owner,
        )
        report = create_report_with_references(
            actor=self.owner,
            organization=self.organization,
            report_values=self.report_values(),
            safety_ids=[self.incident.pk],
            quality_ids=[self.issue.pk],
            document_ids=[self.document.pk],
        )
        submit_safety_record(
            organization=self.organization,
            actor=self.owner,
            incident_id=self.incident.pk,
            reason="سوابق بررسی نمونه",
        )
        submit_quality_record(
            organization=self.organization,
            actor=self.owner,
            issue_id=self.issue.pk,
            reason="سوابق کیفیت نمونه",
        )
        self.records = [
            ("safety", "safety:detail", [self.incident.pk]),
            ("quality", "quality:detail", [self.issue.pk]),
            ("material", "materials:material_detail", [material.pk]),
            ("material-category", "materials:category_detail", [category.pk]),
            ("expense-category", "expenses:category_detail", [expense_category.pk]),
            ("equipment", "equipment:detail", [equipment.pk]),
            ("party", "parties:detail", [party.pk]),
            (
                "phase",
                "projects:phase_detail",
                [self.project.pk, self.site.pk, self.phase.pk],
            ),
            ("site", "projects:site_detail", [self.project.pk, self.site.pk]),
            ("maintenance", "equipment:maintenance_detail", [maintenance.pk]),
            ("work-order", "equipment:work_order_detail", [order.pk]),
            ("warehouse", "inventory:warehouse_detail", [self.warehouses[0].pk]),
            ("daily-report", "daily_reports:detail", [report.pk]),
            ("document", "documents:detail", [self.document.pk]),
            (
                "membership",
                "organizations:member_detail",
                [self.reader_scope.membership.pk],
            ),
        ]
        return material, category, expense_category

    def test_all_adopted_routes(self):
        material, category, expense_category = self.setup_adopters()
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "fullPageScreenshot": True,
            "bottomScreenshot": True,
            "noJsErrors": True,
        }
        for offset in range(0, len(self.records), 3):
            self.browser(
                self.owner,
                [
                    dict(
                        common,
                        name=f"{name}-{width}",
                        path=reverse(route, args=args),
                        width=width,
                        steps=[
                            {
                                "inspect": "document.querySelectorAll('main h1').length === 1 && [...document.querySelectorAll('main a[href^=\"#\"]')].every(a=>a.getAttribute('href')==='#' || !!document.getElementById(a.getAttribute('href').slice(1)))",
                                "description": "one record identity and valid section navigation",
                            }
                        ],
                    )
                    for name, route, args in self.records[offset : offset + 3]
                    for width in (1440, 1024, 390)
                ],
            )
        self.login(self.denied)
        for _, route, args in self.records:
            self.assertIn(
                self.client.get(reverse(route, args=args)).status_code, (403, 404)
            )
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "safety_incidents.view",
                    "quality_issues.view",
                    "daily_reports.view",
                ]
            )
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name="safety-restricted",
                    path=reverse("safety:detail", args=[self.incident.pk]),
                    width=390,
                    steps=[
                        {
                            "inspect": "document.querySelectorAll('main form').length === 0",
                            "description": "read access does not grant HSE actions",
                        }
                    ],
                )
            ],
        )

        self.login(self.reader)
        self.assertIn(
            self.client.get(
                reverse("inventory:warehouse_detail", args=[self.hidden.pk])
            ).status_code,
            (403, 404),
        )
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=[
                    "materials.view",
                    "material_categories.view",
                    "expense_categories.view",
                ]
            )
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.reader_scope.membership,
            scope_type="organization",
            reason="Synthetic master read authority",
        )
        self.browser(
            self.reader,
            [
                dict(
                    common,
                    name=f"{name}-read-only",
                    path=reverse(route, args=[record.pk]),
                    width=390,
                    steps=[
                        {
                            "inspect": "!document.querySelector('main .erp-form-footer button[type=submit]') && [...document.querySelectorAll('main .erp-compact-form input:not([type=hidden]),main .erp-compact-form select')].every(el=>el.disabled)",
                            "description": "existing Compact editor remains read only without change permission",
                        }
                    ],
                )
                for name, route, record in [
                    ("material", "materials:material_detail", material),
                    ("material-category", "materials:category_detail", category),
                    ("expense-category", "expenses:category_detail", expense_category),
                ]
            ],
        )

    def test_hse_closed_history_and_real_actions(self):
        from apps.quality import services as quality_services
        from apps.quality import workflow as quality_workflow
        from apps.quality.record_review import decide_quality_record
        from apps.safety import services as safety_services
        from apps.safety import workflow as safety_workflow
        from apps.safety.record_review import decide_safety_record
        from apps.workflows.models import WorkflowTemplate, WorkflowType

        self.setup_adopters()
        for workflow in (safety_workflow, quality_workflow):
            WorkflowTemplate.objects.get_or_create(
                workflow_type=WorkflowType.objects.get(
                    code=workflow.WORKFLOW_TYPE_CODE
                ),
                code=workflow.TEMPLATE_CODE,
                defaults={
                    "name": workflow.TEMPLATE_CODE,
                    "configuration": workflow.COMPATIBILITY_CONFIGURATION,
                },
            )
        common = {
            "status": 200,
            "screenshot": True,
            "viewportScreenshot": True,
            "fullPageScreenshot": True,
            "bottomScreenshot": True,
            "noJsErrors": True,
        }
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"{name}-review-action",
                    width=390,
                    path=reverse(f"{name}:detail", args=[record.pk]),
                    steps=[
                        {
                            "submit": True,
                            "formSelector": "main form[action$='/review/']",
                            "afterPath": reverse(f"{name}:detail", args=[record.pk]),
                        }
                    ],
                )
                for name, record in [("safety", self.incident), ("quality", self.issue)]
            ],
        )
        safety = {
            "organization": self.organization,
            "actor": self.owner,
            "incident_id": self.incident.pk,
        }
        quality = {
            "organization": self.organization,
            "actor": self.owner,
            "issue_id": self.issue.pk,
        }
        decide_safety_record(**safety, outcome="approved", reason="تأیید سابقه بررسی")
        decide_quality_record(**quality, outcome="approved", reason="تأیید سابقه کیفیت")
        due_date = timezone.localdate() + timedelta(days=7)
        safety_services.assign_safety_incident(
            **safety, due_date=due_date, responsible_user=self.owner
        )
        safety_services.start_corrective_action(
            **safety, corrective_action="ایمن‌سازی محل"
        )
        safety_services.resolve_safety_incident(**safety, resolution_summary="رفع شد")
        safety_services.close_safety_incident(**safety, closure_summary="بسته شد")
        quality_services.assign_quality_issue(
            **quality, due_date=due_date, responsible_user=self.owner
        )
        quality_services.start_quality_corrective_action(
            **quality, corrective_action="اصلاح شد"
        )
        quality_services.submit_quality_issue_for_verification(
            **quality, corrective_action_result="رفع نقص"
        )
        quality_services.verify_quality_issue(
            **quality, verification_summary="راستی‌آزمایی شد"
        )
        quality_services.close_quality_issue(**quality, closure_summary="بسته شد")
        for record in (self.incident, self.issue):
            record.refresh_from_db()
            self.assertEqual(record.status, "closed")
        before = [
            type(record).objects.filter(pk=record.pk).values().get()
            for record in (self.incident, self.issue)
        ]
        self.browser(
            self.owner,
            [
                dict(
                    common,
                    name=f"{name}-closed-{width}",
                    width=width,
                    path=reverse(f"{name}:detail", args=[record.pk]),
                    steps=[
                        {
                            "inspect": "document.querySelectorAll('#record-actions form').length === 0 && document.querySelectorAll('#record-history li').length >= 3",
                            "description": "closed record is immutable and retains actual review history",
                        }
                    ],
                )
                for name, record in [("safety", self.incident), ("quality", self.issue)]
                for width in (1440, 1024, 390)
            ],
        )
        self.assertEqual(
            before,
            [
                type(record).objects.filter(pk=record.pk).values().get()
                for record in (self.incident, self.issue)
            ],
        )

    def test_operational_form_accessibility(self):
        self.setup_adopters()
        paths = [
            (name, reverse(route, args=args))
            for name, route, args in self.records
            if name in ("daily-report", "document", "equipment")
        ]
        self.browser(
            self.owner,
            [
                {
                    "name": f"{name}-field-labels",
                    "path": path,
                    "width": 390,
                    "status": 200,
                    "screenshot": True,
                    "viewportScreenshot": True,
                    "fullPageScreenshot": True,
                    "noJsErrors": True,
                    "steps": [
                        {
                            "inspect": "(() => { const ids=[...document.querySelectorAll('main [id]')].map(e=>e.id); return ids.length===new Set(ids).size && [...document.querySelectorAll('main label[for]')].every(l=>!!document.getElementById(l.htmlFor)); })()",
                            "description": "unique IDs and real control labels in preserved operational forms",
                        }
                    ]
                    + (
                        [
                            {
                                "fill": {
                                    "team_name": "گروه آزمون جزئیات",
                                    "worker_count": "2",
                                    "hours_worked": "8",
                                    "notes": "یادداشت آزمون برچسب",
                                },
                                "formSelector": "main form[action$='/labor/']",
                                "submit": True,
                                "afterPath": path,
                            },
                            {
                                "inspect": "document.querySelector('main').innerText.includes('گروه آزمون جزئیات') && [...document.querySelectorAll('[data-material-name-field]')].every(e=>!!document.getElementById(e.dataset.materialNameField))",
                                "description": "unchanged POST contract and derived widget targets work with unique IDs",
                            },
                        ]
                        if name == "daily-report"
                        else []
                    ),
                }
                for name, path in paths
            ],
        )
        report_id = next(
            args[0] for name, _, args in self.records if name == "daily-report"
        )
        from apps.daily_reports.models import DailyReportLaborEntry

        self.assertEqual(
            DailyReportLaborEntry.objects.get(report_id=report_id).team_name,
            "گروه آزمون جزئیات",
        )
        foreign = MaterialCategory.objects.create(
            organization=self.other_organization,
            code="FOREIGN-DETAIL",
            name="دسته شرکت دیگر",
        )
        self.assertEqual(
            self.client.get(
                reverse("materials:category_detail", args=[foreign.pk])
            ).status_code,
            404,
        )

    def test_shared_read_only_badges(self):
        self.setup_adopters()
        self.browser(
            self.owner,
            [
                {
                    "name": f"{name}-{width}",
                    "path": reverse(route, args=args),
                    "width": width,
                    "status": 200,
                    "screenshot": True,
                    "viewportScreenshot": True,
                    "fullPageScreenshot": True,
                    "bottomScreenshot": True,
                    "noJsErrors": True,
                    "steps": [
                        {
                            "inspect": "document.querySelectorAll('main .erp-badge').length === 1",
                            "description": "actual status uses the shared semantic badge",
                        }
                    ],
                }
                for name, route, args in self.records
                if name in ("site", "membership", "maintenance", "work-order")
                for width in (1440, 1024, 390)
            ],
        )
