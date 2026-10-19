from decimal import Decimal

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.daily_reports.models import (
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
)
from apps.documents.models import Document, DocumentLink, DocumentVersion
from apps.estimates.models import Estimate, EstimateItem
from apps.expenses.models import Expense
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectPhase, ProjectSite
from apps.treasury.models import TreasuryMovement


class TenantModelValidationTests(TestCase):
    def setUp(self) -> None:
        self.organization = Organization.objects.create(
            name="Tenant A", slug="tenant-a"
        )
        self.other_organization = Organization.objects.create(
            name="Tenant B", slug="tenant-b"
        )
        self.project = Project.objects.create(
            organization=self.organization, code="A", name="Project A"
        )
        self.other_project = Project.objects.create(
            organization=self.other_organization, code="B", name="Project B"
        )
        self.site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="A",
            name="Site A",
        )
        self.other_site = ProjectSite.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            code="B",
            name="Site B",
        )
        self.phase = ProjectPhase.objects.create(
            organization=self.organization, site=self.site, code="A", name="Phase A"
        )
        self.other_contract = Contract.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            contract_number="B",
            title="Contract B",
            counterparty_name="Counterparty B",
        )

    def test_direct_saves_reject_cross_tenant_relationships(self) -> None:
        actor = self.organization.memberships.create(
            user=User.objects.create_user(username="tenant-movement-actor"),
            role="company_owner",
            status="active",
        )
        invalid_models = [
            ProjectSite(
                organization=self.organization,
                project=self.other_project,
                code="X",
                name="Invalid site",
            ),
            ProjectPhase(
                organization=self.organization,
                site=self.other_site,
                code="X",
                name="Invalid phase",
            ),
            Contract(
                organization=self.organization,
                project=self.other_project,
                contract_number="X",
                title="Invalid contract",
                counterparty_name="Counterparty",
            ),
            Estimate(
                organization=self.organization,
                project=self.project,
                contract=self.other_contract,
                estimate_number="X",
                title="Invalid estimate",
            ),
            Expense(
                organization=self.organization,
                project=self.other_project,
                description="Invalid expense",
                amount=Decimal("1.00"),
                incurred_on=timezone.localdate(),
            ),
            TreasuryMovement(
                organization=self.organization,
                project=self.other_project,
                kind="receipt",
                amount=Decimal("1.00"),
                movement_date=timezone.localdate(),
                description="Invalid tenant",
                idempotency_key="TENANT-FAIL",
                payload_hash="x" * 64,
                created_by=actor,
            ),
            DailyReport(
                organization=self.organization,
                project=self.other_project,
                site=self.other_site,
                reporting_date=timezone.localdate(),
                work_performed="Invalid report",
            ),
        ]

        for instance in invalid_models:
            with (
                self.subTest(model=instance.__class__.__name__),
                self.assertRaises(ValidationError),
            ):
                instance.save()

    def test_estimate_item_and_daily_report_entry_reject_cross_tenant_parents(
        self,
    ) -> None:
        other_estimate = Estimate.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            estimate_number="B",
            title="Estimate B",
        )
        other_report = DailyReport.objects.create(
            organization=self.other_organization,
            project=self.other_project,
            site=self.other_site,
            reporting_date=timezone.localdate(),
            work_performed="Report B",
        )

        with self.assertRaises(ValidationError):
            EstimateItem(
                organization=self.organization,
                estimate=other_estimate,
                description="Invalid item",
                quantity=Decimal("1.0000"),
                unit_price=Decimal("1.00"),
            ).save()
        with self.assertRaises(ValidationError):
            DailyReportLaborEntry(
                organization=self.organization,
                report=other_report,
                team_name="Invalid team",
                worker_count=1,
                hours_worked=Decimal("1.00"),
            ).save()

    def test_business_admin_mutations_are_disabled(self) -> None:
        request = RequestFactory().get("/admin/")
        request.user = AnonymousUser()
        # Treasury exposes its governed product services; there is no admin CRUD.
        self.assertNotIn(TreasuryMovement, admin.site._registry)
        models = [
            Organization,
            Project,
            ProjectSite,
            ProjectPhase,
            Contract,
            Estimate,
            Expense,
            Document,
            DocumentVersion,
            DocumentLink,
            DailyReport,
            DailyReportLaborEntry,
            DailyReportEquipmentEntry,
            DailyReportMaterialEntry,
        ]

        for model in models:
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
