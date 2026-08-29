from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.expenses.models import ExpenseCategory
from apps.expenses.services import create_expense, get_organization_expenses
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.projects.services import create_project


class ExpenseServiceTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="expense-owner",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="other-expense-user",
            password="test-password",
        )
        self.organization = Organization.objects.create(
            name="Expense Company",
            slug="expense-company",
            created_by=self.owner,
            updated_by=self.owner,
        )
        self.other_organization = Organization.objects.create(
            name="Other Expense Company",
            slug="other-expense-company",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.organization.memberships.create(
            user=self.owner,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-EXPENSE",
            name="Expense project",
        )

    def test_create_expense_records_decimal_amount_and_audit(self) -> None:
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Concrete delivery",
            amount=Decimal("1250.75"),
            incurred_on=date(2026, 8, 29),
            category=ExpenseCategory.MATERIALS,
            vendor_name="Supplier LLC",
        )

        self.assertEqual(expense.amount, Decimal("1250.75"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_RECORDED,
                organization=self.organization,
                entity_id=str(expense.pk),
            ).exists()
        )

    def test_expense_rejects_negative_amount(self) -> None:
        with self.assertRaisesMessage(
            ValueError,
            "Expense amount cannot be negative.",
        ):
            create_expense(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                description="Invalid expense",
                amount=Decimal("-1.00"),
                incurred_on=date(2026, 8, 29),
            )

    def test_expense_rejects_cross_tenant_project(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-OTHER-EXP",
            name="Other project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        with self.assertRaises(PermissionDenied):
            create_expense(
                organization=self.organization,
                project=other_project,
                actor=self.owner,
                description="Invalid tenant expense",
                amount=Decimal("10.00"),
                incurred_on=date(2026, 8, 29),
            )

    def test_member_cannot_create_expense(self) -> None:
        member = User.objects.create_user(
            username="expense-member",
            password="test-password",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            create_expense(
                organization=self.organization,
                project=self.project,
                actor=member,
                description="Unauthorized expense",
                amount=Decimal("10.00"),
                incurred_on=date(2026, 8, 29),
            )

    def test_expense_queryset_is_tenant_scoped(self) -> None:
        create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Visible expense",
            amount=Decimal("50.00"),
            incurred_on=date(2026, 8, 29),
        )

        expenses = get_organization_expenses(
            user=self.owner,
            organization=self.organization,
        )

        self.assertEqual(
            list(expenses.values_list("description", flat=True)),
            ["Visible expense"],
        )
        with self.assertRaises(PermissionDenied):
            get_organization_expenses(
                user=self.other_user,
                organization=self.organization,
            )

    def test_expense_list_requires_active_organization(self) -> None:
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("expenses:list"))

        self.assertRedirects(response, reverse("organizations:select"))

    def test_expense_create_view_limits_project_choices(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.other_organization.projects.create(
            code="P-HIDDEN-EXP",
            name="Hidden expense project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        response = self.client.get(reverse("expenses:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, "Hidden expense project")

    def test_expense_create_view_records_expense(self) -> None:
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("expenses:create"),
            {
                "project": str(self.project.pk),
                "category": "materials",
                "description": "View delivery",
                "vendor_name": "Supplier",
                "amount": "75.50",
                "incurred_on": "2026-08-29",
                "receipt_reference": "",
                "notes": "",
            },
        )

        self.assertRedirects(response, reverse("expenses:list"))
        self.assertTrue(
            self.organization.expenses.filter(
                description="View delivery",
            ).exists()
        )
