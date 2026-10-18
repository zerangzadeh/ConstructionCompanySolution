"""Populated disposable PostgreSQL preservation and additive rollback/reapply."""

import json
import os
from datetime import date
from pathlib import Path

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.accounting.models import FiscalPeriod, FiscalYear, JournalEntry
from apps.organizations.models import BusinessPermission, OrganizationRole

from . import test_cep043_payroll_handoff as scenarios
from .models import Obligation
from .services import _canonical_hash


class PayrollAPMigrationTests(scenarios.PayrollAPFixture, TransactionTestCase):
    def test_populated_legacy_history_grants_and_catalog_survive_additive_reapply(self):
        # Explicit pre-existing synthetic rows, independent of new AP draft tables.
        year = FiscalYear.objects.create(
            organization=self.organization,
            code="MIG043",
            name="Retained",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=self.owner,
        )
        period = FiscalPeriod.objects.create(
            organization=self.organization,
            fiscal_year=year,
            number=1,
            name="Retained",
            starts_on=year.starts_on,
            ends_on=year.ends_on,
        )
        JournalEntry.objects.create(
            organization=self.organization,
            period=period,
            kind="manual",
            document_date=self.day,
            accounting_date=self.day,
            description="Synthetic retained draft",
            source_key="retained043",
            prepared_by=self.ap_membership,
        )
        Obligation.objects.create(
            organization=self.organization,
            source_kind="synthetic.retained",
            source_uuid=self.proposal.pk,
            source_version=1,
            source_status="retained",
            source_hash="retained",
            source_snapshot={"evidence": "pre-existing fixture"},
            direction="payable",
            party_name_snapshot="Retained synthetic party",
            original_amount=5,
            recognized_on=self.day,
            idempotency_key="retained043",
            payload_hash="retained",
            recognized_by=self.ap_membership,
        )
        labels = (
            "payroll.PayrollRun",
            "payroll.PayrollRunEmployee",
            "payroll.PayrollResultLine",
            "payroll.FinancialHandoffProposal",
            "payroll.FinancialHandoffLine",
            "payroll.FinancialHandoffReview",
            "subledgers.Obligation",
            "accounting.Account",
            "accounting.ControlAccountMappingVersion",
            "accounting.JournalEntry",
            "audit.AuditEvent",
            "organizations.MembershipRoleAssignment",
            "organizations.MembershipScopeGrant",
        )

        def snapshot():
            values = {}
            for label in labels:
                rows = list(apps.get_model(label).objects.order_by("pk").values())
                values[label] = {"count": len(rows), "sha256": _canonical_hash(rows)}
            rows = list(
                OrganizationRole.permissions.through.objects.order_by("pk").values()
            )
            values["role_grants"] = {
                "count": len(rows),
                "sha256": _canonical_hash(rows),
            }
            rows = list(
                BusinessPermission.objects.exclude(
                    code__startswith="subledgers_payroll."
                )
                .order_by("pk")
                .values()
            )
            values["preexisting_catalog"] = {
                "count": len(rows),
                "sha256": _canonical_hash(rows),
            }
            return values

        before = snapshot()
        old = [
            ("subledgers", "0005_supplierinvoiceapreversal"),
            ("organizations", "0120_cep042_recognition_permissions"),
        ]
        new = [
            ("subledgers", "0006_cep043_payroll_ap"),
            ("organizations", "0121_cep043_payroll_ap_permissions"),
        ]
        try:
            MigrationExecutor(connection).migrate(old)
            self.assertEqual(snapshot(), before)
            self.assertNotIn(
                "subledgers_payrollapdraft", connection.introspection.table_names()
            )
            MigrationExecutor(connection).migrate(new)
            self.assertEqual(snapshot(), before)
            for name in (
                "PayrollAPEnrollment",
                "PayrollAPEnrollmentEvent",
                "PayrollAPDraft",
                "PayrollAPOperation",
                "PayrollAPReversal",
            ):
                self.assertEqual(apps.get_model("subledgers", name).objects.count(), 0)
            self.assertEqual(
                BusinessPermission.objects.filter(
                    code__startswith="subledgers_payroll.", is_active=True
                ).count(),
                4,
            )
        finally:
            MigrationExecutor(connection).migrate(new)
        if os.getenv("BONIRA_CEP043_MIGRATION_TRACE"):
            Path(os.environ["BONIRA_CEP043_MIGRATION_TRACE"]).write_text(
                json.dumps(
                    {
                        "database": "disposable test PostgreSQL only",
                        "before": before,
                        "after": snapshot(),
                        "preserved": True,
                        "new_tables_empty": True,
                        "production": False,
                    },
                    indent=2,
                )
                + "\n"
            )
