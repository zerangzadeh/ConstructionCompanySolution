"""The operational YTD expansion preserves existing finalized Payroll sources."""

from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationSettings
from apps.payroll.models import PayrollPeriod, PayrollRun, PayrollRunStatus


class OperationalCumulativeMigrationTests(TransactionTestCase):
    serialized_rollback = True

    def test_existing_finalized_run_survives_rollback_and_reapply(self) -> None:
        actor = User.objects.create_user(username="cep025-migration")
        organization = Organization.objects.create(
            name="CEP-025 migration", slug="cep025-migration"
        )
        OrganizationSettings.objects.create(organization=organization, currency="IRR")
        period = PayrollPeriod.objects.create(
            organization=organization,
            code="MIG25",
            name="Existing period",
            starts_on=date(2026, 10, 1),
            ends_on=date(2026, 10, 31),
            cutoff_at=timezone.now(),
            created_by=actor,
        )
        run = PayrollRun.objects.create(
            organization=organization,
            period=period,
            code="MIG25",
            status=PayrollRunStatus.FINALIZED,
            idempotency_key="cep025-migration",
            calculation_digest="a" * 64,
            created_by=actor,
        )
        previous = [
            ("payroll", "0005_financialhandoffproposal_financialhandoffline_and_more")
        ]
        current = [("payroll", "0006_cep025_operational_cumulative_ytd")]
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertTrue(PayrollRun.objects.filter(pk=run.pk).exists())
            MigrationExecutor(connection).migrate(current)
            restored = PayrollRun.objects.get(pk=run.pk)
            self.assertEqual(restored.calculation_digest, "a" * 64)
            self.assertEqual(restored.status, PayrollRunStatus.FINALIZED)
            self.assertEqual(restored.period_id, period.pk)
        finally:
            MigrationExecutor(connection).migrate(current)
