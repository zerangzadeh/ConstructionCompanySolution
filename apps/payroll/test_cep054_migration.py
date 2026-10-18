"""Expand-only inquiry schema retains existing finalized Payroll history."""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationSettings
from apps.payroll.models import PayrollPeriod, PayrollRun, PayrollRunStatus


class InquiryMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_rollback_reapply_preserves_finalized_source_without_inferred_inquiry(self):
        actor = User.objects.create_user(username="cep054-migration")
        organization = Organization.objects.create(
            name="CEP-054", slug="cep054-migration"
        )
        OrganizationSettings.objects.create(organization=organization, currency="IRR")
        period = PayrollPeriod.objects.create(
            organization=organization,
            code="MIG54",
            name="Retained period",
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 10, 31),
            cutoff_at=timezone.now(),
            created_by=actor,
        )
        run = PayrollRun.objects.create(
            organization=organization,
            period=period,
            code="MIG54",
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="cep054-migration",
            calculation_digest="b" * 64,
            created_by=actor,
        )
        previous = [("payroll", "0007_statutorysourcepackage")]
        current = [("payroll", "0008_cep054_payroll_inquiry")]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertTrue(PayrollRun.objects.filter(pk=run.pk).exists())
            executor = MigrationExecutor(connection)
            executor.migrate(current)
            restored = PayrollRun.objects.get(pk=run.pk)
            self.assertEqual(restored.calculation_digest, "b" * 64)
            self.assertEqual(restored.status, PayrollRunStatus.FINALIZED)
            self.assertEqual(restored.period_id, period.pk)
            historical = executor.loader.project_state(current).apps
            self.assertEqual(
                historical.get_model("payroll", "PayrollInquiry").objects.count(),
                0,
            )
        finally:
            MigrationExecutor(connection).migrate(current)
