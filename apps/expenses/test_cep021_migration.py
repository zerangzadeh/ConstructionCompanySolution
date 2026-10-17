from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.expenses.models import Expense
from apps.organizations.models import MembershipRole, MembershipStatus, Organization
from apps.parties.models import BusinessParty, PartyKind
from apps.projects.models import Project
from apps.treasury.models import PaymentRequest


class ReimbursementLineageMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_existing_source_and_request_survive_rollback_and_reapply(self) -> None:
        actor = User.objects.create_user(username="cep021-migration")
        organization = Organization.objects.create(
            name="CEP-021 migration", slug="cep021-migration",
        )
        membership = organization.memberships.create(
            user=actor, role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        project = Project.objects.create(
            organization=organization, code="MIG-21", name="Migration fixture",
        )
        party = BusinessParty.objects.create(
            organization=organization, party_kind=PartyKind.COMPANY,
            display_name="Legacy party",
        )
        expense = Expense.objects.create(
            organization=organization, project=project,
            description="Legacy expense", amount=Decimal("10.00"),
            incurred_on=date(2026, 10, 1),
        )
        request = PaymentRequest.objects.create(
            organization=organization, kind="payment", amount=Decimal("10.00"),
            purpose="Legacy payment", idempotency_key="cep021-migration-payment",
            payload_hash="0" * 64, party=party, created_by=membership,
        )
        before = (expense.pk, request.pk)
        previous = [
            ("expenses", "0008_protect_expense_primary_group"),
            ("treasury", "0008_bankreconciliationruninvalidation_and_more"),
        ]
        current = [
            ("expenses", "0009_expense_reimbursement_employee_expense_replaces_and_more"),
            ("treasury", "0009_remove_paymentrequest_treasury_request_beneficiary_consistent_and_more"),
        ]
        try:
            MigrationExecutor(connection).migrate(previous)
        finally:
            MigrationExecutor(connection).migrate(current)

        restored_expense = Expense.objects.get(pk=before[0])
        restored_request = PaymentRequest.objects.get(pk=before[1])
        self.assertEqual(restored_expense.amount, Decimal("10.00"))
        self.assertEqual(restored_expense.source_version, 1)
        self.assertIsNone(restored_expense.reimbursement_employee_id)
        self.assertIsNone(restored_request.source_expense_id)
        self.assertIsNone(restored_request.source_expense_version)
        self.assertEqual(restored_request.party_id, party.pk)
        self.assertEqual(Expense.objects.filter(organization=organization).count(), 1)
        self.assertEqual(PaymentRequest.objects.filter(organization=organization).count(), 1)
