"""Additive provenance schema: native history survives; external history blocks reverse."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from . import test_cep058_import as opening_fixtures
from .cumulative_services import record_cumulative_for_run
from .models import PayrollCumulativeState, PayrollRun
from .opening_import import import_payroll_opening


class OpeningProvenanceMigrationTests(TransactionTestCase):
    _run = opening_fixtures.PayrollOpeningImportTests._run
    _lines = opening_fixtures.PayrollOpeningImportTests._lines
    setUp = opening_fixtures.PayrollOpeningImportTests.setUp

    def test_reverse_and_reapply_before_openings_preserves_native_sources(self):
        record_cumulative_for_run(
            organization=self.organization, actor=self.actor, run=self.run
        )
        states = list(
            PayrollCumulativeState.objects.values(
                "id", "source_line_id", "delta", "balance"
            )
        )
        self.assertEqual(len(states), 5)
        current = [("payroll", "0009_cep058_external_opening_provenance")]
        previous = [("payroll", "0008_cep054_payroll_inquiry")]
        count = PayrollRun.objects.count()
        try:
            MigrationExecutor(connection).migrate(previous)
            self.assertEqual(PayrollRun.objects.count(), count)
            MigrationExecutor(connection).migrate(current)
            self.assertEqual(PayrollRun.objects.count(), count)
            self.assertEqual(
                list(
                    PayrollCumulativeState.objects.values(
                        "id", "source_line_id", "delta", "balance"
                    )
                ),
                states,
            )
        finally:
            MigrationExecutor(connection).migrate(current)

    def test_reverse_guard_rejects_retained_external_history(self):
        import_payroll_opening(
            organization=self.organization,
            actor=self.actor,
            year=self.year,
            rows=self.rows,
            identities=self.ids,
            components=self.dev_components,
            totals=self.totals,
        )
        ids = set(PayrollCumulativeState.objects.values_list("pk", flat=True))
        with self.assertRaises(RuntimeError):
            MigrationExecutor(connection).migrate(
                [("payroll", "0008_cep054_payroll_inquiry")]
            )
        self.assertEqual(
            set(PayrollCumulativeState.objects.values_list("pk", flat=True)), ids
        )
        self.assertIn(
            ("payroll", "0009_cep058_external_opening_provenance"),
            MigrationExecutor(connection).loader.applied_migrations,
        )
