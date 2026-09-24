from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.estimates.services import add_estimate_item, approve_estimate, create_estimate
from apps.expenses.models import ExpenseStatus
from apps.expenses.services import create_expense
from apps.financials.services import (
    get_organization_dashboard,
    get_organization_financial_reports,
    get_project_financial_report,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.payments.models import PaymentDirection
from apps.payments.services import create_payment, void_payment
from apps.projects.services import create_project


class FinancialReportTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="financial-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-financial-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Financial Company",
            slug="financial-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Financial Company",
            slug="other-financial-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-FIN",
            name="Financial project",
        )

    def test_report_uses_approved_estimates_and_recorded_expenses(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-FIN",
            title="Approved estimate",
        )
        add_estimate_item(
            estimate=estimate,
            actor=self.owner,
            description="Work",
            quantity=Decimal(10),
            unit_price=Decimal("100.00"),
        )
        approve_estimate(estimate=estimate, actor=self.owner)
        create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-DRAFT",
            title="Draft estimate",
        )
        create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Recorded expense",
            amount=Decimal("250.55"),
            incurred_on=date(2026, 8, 29),
        )
        self.project.expenses.create(
            organization=self.organization,
            description="Void expense",
            amount=Decimal("1000.00"),
            incurred_on=date(2026, 8, 29),
            status=ExpenseStatus.VOID,
            created_by=self.owner,
            updated_by=self.owner,
        )

        report = get_project_financial_report(
            user=self.owner,
            organization=self.organization,
            project_id=str(self.project.pk),
        )

        self.assertEqual(report.approved_estimate_total, Decimal("1000.00"))
        self.assertEqual(report.recorded_expense_total, Decimal("250.55"))
        self.assertEqual(report.variance, Decimal("749.45"))
        self.assertEqual(report.approved_estimate_count, 1)
        self.assertEqual(report.recorded_expense_count, 1)

    def test_report_rejects_cross_tenant_project(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-FIN",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            get_project_financial_report(
                user=self.owner,
                organization=self.organization,
                project_id=str(other_project.pk),
            )

    def test_financial_report_view_is_tenant_scoped(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("financials:report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financial project")
        self.assertNotContains(response, "Other Financial Company")

    def test_organization_reports_include_only_active_projects(self) -> None:
        reports = get_organization_financial_reports(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].project, self.project)

    def test_dashboard_returns_tenant_scoped_counts_and_totals(self) -> None:
        estimate = create_estimate(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            estimate_number="E-DASH",
            title="Dashboard estimate",
        )
        add_estimate_item(
            estimate=estimate,
            actor=self.owner,
            description="Scope",
            quantity=Decimal(5),
            unit_price=Decimal("200.00"),
        )
        approve_estimate(estimate=estimate, actor=self.owner)
        create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Dashboard expense",
            amount=Decimal("125.50"),
            incurred_on=date(2026, 8, 29),
        )
        create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="PAY-DASH-RECEIPT",
            direction=PaymentDirection.RECEIPT,
            amount=Decimal("600.00"),
            paid_on=date(2026, 8, 29),
            counterparty_name="Client LLC",
        )
        payment_to_void = create_payment(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            payment_number="PAY-DASH-VOID",
            direction=PaymentDirection.DISBURSEMENT,
            amount=Decimal("90.00"),
            paid_on=date(2026, 8, 29),
            counterparty_name="Supplier LLC",
        )
        void_payment(payment=payment_to_void, actor=self.owner, reason="Duplicate")

        summary = get_organization_dashboard(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(summary.project_count, 1)
        self.assertEqual(summary.contract_count, 0)
        self.assertEqual(summary.estimate_count, 1)
        self.assertEqual(summary.approved_estimate_total, Decimal("1000.00"))
        self.assertEqual(summary.recorded_expense_total, Decimal("125.50"))
        self.assertEqual(summary.variance, Decimal("874.50"))
        self.assertEqual(summary.posted_payment_count, 1)
        self.assertEqual(summary.receipt_total, Decimal("600.00"))
        self.assertEqual(summary.disbursement_total, Decimal("0.00"))
        self.assertEqual(summary.net_cash_flow, Decimal("600.00"))

    def test_dashboard_view_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("financials:dashboard"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_dashboard_view_renders_active_organization(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.get(reverse("financials:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "داشبورد شرکت")
        self.assertContains(response, "Financial Company")
