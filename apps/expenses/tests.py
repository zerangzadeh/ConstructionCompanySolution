from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.expenses.models import ExpenseStatus
from apps.expenses.models import LegacyExpenseCategory as ExpenseCategory
from apps.expenses.services import (
    create_expense,
    create_expense_category,
    get_organization_expenses,
    void_expense,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import PartyKind
from apps.parties.services import create_business_party
from apps.projects.models import ProjectPhaseStatus
from apps.projects.services import (
    create_project,
    create_project_phase,
    create_project_site,
)


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
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        self.project = create_project(
            organization=self.organization,
            actor=self.owner,
            code="P-EXPENSE",
            name="Expense project",
        )
        self.site = create_project_site(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            code="SITE-EXPENSE",
            name="Expense worksite",
        )
        self.phase = create_project_phase(
            organization=self.organization,
            site=self.site,
            actor=self.owner,
            code="PH-EXPENSE",
            name="Foundation works",
            status=ProjectPhaseStatus.ACTIVE,
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
            "مبلغ هزینه نمی‌تواند منفی باشد.",
        ):
            create_expense(
                organization=self.organization,
                project=self.project,
                actor=self.owner,
                description="Invalid expense",
                amount=Decimal("-1.00"),
                incurred_on=date(2026, 8, 29),
            )

    def test_void_expense_preserves_amount_and_records_audit(self) -> None:
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Duplicate delivery",
            amount=Decimal("1250.75"),
            incurred_on=date(2026, 8, 29),
        )
        void_expense(expense=expense, actor=self.owner, reason="Duplicate entry")
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.VOID)
        self.assertEqual(expense.amount, Decimal("1250.75"))
        self.assertEqual(expense.void_reason, "Duplicate entry")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_VOIDED,
                entity_id=str(expense.pk),
            ).exists()
        )

    def test_member_cannot_void_expense(self) -> None:
        member = User.objects.create_user(
            username="expense-void-member",
            password="test-password",
        )
        self.organization.memberships.create(
            user=member,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Protected expense",
            amount=Decimal("30.00"),
            incurred_on=date(2026, 8, 29),
        )

        with self.assertRaises(PermissionDenied):
            void_expense(
                expense=expense,
                actor=member,
                reason="Unauthorized void",
            )

        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.RECORDED)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_VOIDED,
                entity_id=str(expense.pk),
            ).exists()
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

    def test_expense_optionally_scopes_to_a_project_phase(self) -> None:
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            phase=self.phase,
            actor=self.owner,
            description="Foundation concrete",
            amount=Decimal("3250.00"),
            incurred_on=date(2026, 8, 29),
        )

        self.assertEqual(expense.phase, self.phase)
        event = AuditEvent.objects.get(
            action=AuditAction.EXPENSE_RECORDED,
            entity_id=str(expense.pk),
        )
        self.assertEqual(event.metadata["phase_id"], str(self.phase.pk))

    def test_expense_uses_scoped_party_and_category_snapshots(self) -> None:
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind=PartyKind.COMPANY,
            display_name="Concrete Supplier",
        )
        category = create_expense_category(
            organization=self.organization,
            actor=self.owner,
            code="concrete",
            name="Concrete",
        )
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Concrete delivery",
            amount=Decimal("25.00"),
            incurred_on=date(2026, 8, 29),
            party=party,
            expense_category=category,
        )
        self.assertEqual(expense.party, party)
        self.assertEqual(expense.expense_category, category)
        self.assertEqual(expense.vendor_name, "Concrete Supplier")
        self.assertEqual(expense.category, ExpenseCategory.OTHER)
        self.assertEqual(expense.primary_group.code, ExpenseCategory.OTHER)
        self.assertEqual(category.primary_group.code, ExpenseCategory.OTHER)

    def test_expense_rejects_phase_from_another_project(self) -> None:
        other_project = self.organization.projects.create(
            code="P-OTHER-PHASE-EXP",
            name="Other expense project",
            created_by=self.owner,
            updated_by=self.owner,
        )
        other_site = create_project_site(
            organization=self.organization,
            project=other_project,
            actor=self.owner,
            code="SITE-OTHER-PHASE-EXP",
            name="Other expense worksite",
        )
        other_phase = create_project_phase(
            organization=self.organization,
            site=other_site,
            actor=self.owner,
            code="PH-OTHER-EXP",
            name="Other expense phase",
            status=ProjectPhaseStatus.ACTIVE,
        )

        with self.assertRaises(PermissionDenied):
            create_expense(
                organization=self.organization,
                project=self.project,
                phase=other_phase,
                actor=self.owner,
                description="Invalid phase expense",
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

    def test_expense_void_view_rejects_cross_tenant_expense_identifier(self) -> None:
        other_project = self.other_organization.projects.create(
            code="P-VOID-HIDDEN",
            name="Hidden void project",
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        other_expense = self.other_organization.expenses.create(
            project=other_project,
            description="Other tenant expense",
            amount=Decimal("90.00"),
            incurred_on=date(2026, 8, 29),
            created_by=self.other_user,
            updated_by=self.other_user,
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("expenses:void", args=[other_expense.pk]),
            {"reason": "Attempted cross-tenant void"},
        )

        self.assertEqual(response.status_code, 404)
        other_expense.refresh_from_db()
        self.assertEqual(other_expense.status, ExpenseStatus.RECORDED)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_VOIDED,
                entity_id=str(other_expense.pk),
            ).exists()
        )

    def test_expense_void_view_rejects_blank_reason_without_mutation(self) -> None:
        expense = create_expense(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            description="Missing void reason",
            amount=Decimal("45.00"),
            incurred_on=date(2026, 8, 29),
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

        response = self.client.post(
            reverse("expenses:void", args=[expense.pk]),
            {"reason": ""},
        )

        self.assertEqual(response.status_code, 400)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.RECORDED)
        self.assertFalse(
            AuditEvent.objects.filter(
                action=AuditAction.EXPENSE_VOIDED,
                entity_id=str(expense.pk),
            ).exists()
        )
