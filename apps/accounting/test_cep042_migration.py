"""Populated disposable PostgreSQL rollback/reapply preservation evidence."""

import json
import os
from datetime import date
from pathlib import Path

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.expenses import test_p4_s26_s30 as expense_fixtures
from apps.expenses.services import approve_expense, submit_expense
from apps.organizations.models import BusinessPermission, OrganizationRole

from .recognition_sources import digest
from .services import (
    create_account,
    create_fiscal_period,
    create_fiscal_year,
    create_journal,
)


class RecognitionMigrationTests(TransactionTestCase):
    _draft = expense_fixtures.ExpenseControlTests._draft
    _allocate = expense_fixtures.ExpenseControlTests._allocate

    def test_populated_existing_history_and_grants_survive_expand_rollback_reapply(
        self,
    ):
        expense_fixtures.ExpenseControlTests.setUp(self)
        expense = self._draft()
        self._allocate(expense)
        submit_expense(expense=expense, actor=self.maker)
        approve_expense(expense=expense, actor=self.approver)
        create_account(
            organization=self.organization,
            actor=self.maker,
            code="MIG42",
            name="Retained account",
            account_type="asset",
            is_posting=True,
        )
        year = create_fiscal_year(
            organization=self.organization,
            actor=self.maker,
            code="MIG42",
            name="Retained year",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            calendar_version=1,
        )
        period = create_fiscal_period(
            organization=self.organization,
            actor=self.maker,
            fiscal_year=year,
            number=1,
            name="Retained period",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        create_journal(
            organization=self.organization,
            actor=self.maker,
            period=period,
            kind="manual",
            document_date=date(2026, 10, 1),
            accounting_date=date(2026, 10, 1),
            description="Retained history",
            source_key="MIG42",
        )

        labels = (
            "accounting.Account",
            "accounting.JournalEntry",
            "accounting.JournalLine",
            "expenses.Expense",
            "expenses.ExpenseAllocation",
            "projects.BudgetVersion",
            "projects.Project",
            "payroll.PayrollRun",
            "inventory.InventoryValuationEvent",
            "fixed_assets.AssetTransaction",
            "audit.AuditEvent",
        )

        def snapshot():
            result = {}
            for label in labels:
                rows = list(apps.get_model(label).objects.order_by("pk").values())
                result[label] = {"count": len(rows), "sha256": digest(rows)}
            through = OrganizationRole.permissions.through
            grants = list(through.objects.order_by("pk").values())
            result["role_grants"] = {"count": len(grants), "sha256": digest(grants)}
            permissions = list(
                BusinessPermission.objects.exclude(
                    code__startswith="accounting_recognition."
                )
                .order_by("pk")
                .values()
            )
            result["preexisting_permission_catalog"] = {
                "count": len(permissions),
                "sha256": digest(permissions),
            }
            return result

        before = snapshot()
        self.assertGreater(before["accounting.JournalEntry"]["count"], 0)
        self.assertGreater(before["expenses.Expense"]["count"], 0)
        self.assertGreater(before["role_grants"]["count"], 0)
        old_targets = [
            ("accounting", "0012_controlaccountmappingversion"),
            ("organizations", "0119_cep037_variation_eligibility_permissions"),
        ]
        new_targets = [
            ("accounting", "0013_cep042_recognition_mapping"),
            ("organizations", "0120_cep042_recognition_permissions"),
        ]
        try:
            MigrationExecutor(connection).migrate(old_targets)
            self.assertEqual(snapshot(), before)
            self.assertNotIn(
                "accounting_recognitionmappingversion",
                connection.introspection.table_names(),
            )
            MigrationExecutor(connection).migrate(new_targets)
            self.assertEqual(snapshot(), before)
            for label in (
                "accounting.RecognitionMappingVersion",
                "accounting.RecognitionMappingApproval",
                "accounting.SourceRecognitionDraft",
            ):
                self.assertEqual(apps.get_model(label).objects.count(), 0)
            self.assertEqual(
                BusinessPermission.objects.filter(
                    code__startswith="accounting_recognition.", is_active=True
                ).count(),
                4,
            )
            self.assertFalse(
                OrganizationRole.permissions.through.objects.filter(
                    businesspermission__code__startswith="accounting_recognition."
                ).exists()
            )
        finally:
            MigrationExecutor(connection).migrate(new_targets)
        output = os.getenv("BONIRA_CEP042_MIGRATION_TRACE")
        if output:
            Path(output).write_text(
                json.dumps(
                    {
                        "database": "disposable test PostgreSQL",
                        "before": before,
                        "after": snapshot(),
                        "preserved": True,
                        "new_tables_empty": True,
                        "implicit_new_grants": False,
                        "production": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
