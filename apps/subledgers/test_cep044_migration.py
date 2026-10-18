"""Narrow disposable migration rehearsal; preserve populated prior evidence."""

import json
import os
from pathlib import Path

from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .models import WriteOffDecision, WriteOffProposal
from .services import _canonical_hash
from .test_cep044_lineage import WriteOffLineageFixture
from .test_cep044_writeoffs import CEP044Fixture


class WriteOffLineageMigrationTests(WriteOffLineageFixture, TransactionTestCase):
    def test_populated_history_preserved_and_used_lineage_cannot_be_dropped(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        old = [("subledgers", "0006_cep043_payroll_ap")]
        new = [("subledgers", "0008_cep044_writeoff_actions")]
        historical = MigrationExecutor(connection).loader.project_state(new).apps
        approved_proposal = self.make_proposal("synthetic-finalized-legacy")
        # Historical migration models intentionally seed synthetic finalized
        # legacy facts without activating the application's gated transitions.
        historical_decision = historical.get_model(
            "subledgers", "WriteOffDecision"
        ).objects.create(
            organization_id=self.organization.pk,
            proposal_id=approved_proposal.pk,
            decision="approved",
            reason="Synthetic finalized legacy approval",
            decided_by_id=self.membership.pk,
        )
        historical.get_model("subledgers", "WriteOffReversal").objects.create(
            organization_id=self.organization.pk,
            decision_id=historical_decision.pk,
            effective_date=approved_proposal.effective_date,
            reason="Synthetic finalized legacy reversal",
            reversed_by_id=self.membership.pk,
        )
        self.decision = WriteOffDecision.objects.get(pk=historical_decision.pk)
        labels = (
            "subledgers.Obligation",
            "subledgers.WriteOffProposal",
            "subledgers.WriteOffDecision",
            "subledgers.WriteOffReversal",
            "accounting.JournalEntry",
            "audit.AuditEvent",
            "organizations.BusinessPermission",
            "organizations.OrganizationRole",
            "organizations.MembershipRoleAssignment",
            "organizations.MembershipScopeGrant",
            "organizations.TenantPolicySelection",
        )

        def snapshot():
            result = {}
            for label in labels:
                model = apps.get_model(label)
                # Compare only pre-existing columns on both sides of the expand.
                fields = [
                    f.attname
                    for f in model._meta.fields
                    if f.name not in {"corrects", "authority_evidence"}
                ]
                rows = list(model.objects.order_by("pk").values(*fields))
                result[label] = {"count": len(rows), "sha256": _canonical_hash(rows)}
            model = apps.get_model("organizations.OrganizationRole").permissions.through
            rows = list(model.objects.order_by("pk").values())
            result["role_grants"] = {
                "count": len(rows),
                "sha256": _canonical_hash(rows),
            }
            return result

        before = snapshot()
        try:
            plan = MigrationExecutor(connection).migration_plan(old)
            self.assertEqual(
                [(m.app_label, m.name, backwards) for m, backwards in plan],
                [
                    ("subledgers", new[0][1], True),
                    ("subledgers", "0007_cep044_writeoff_correction_lineage", True),
                ],
            )
            MigrationExecutor(connection).migrate(old)
            self.assertEqual(before, snapshot())
            with connection.cursor() as cursor:
                columns = connection.introspection.get_table_description(
                    cursor, WriteOffProposal._meta.db_table
                )
            self.assertNotIn("corrects_id", [c.name for c in columns])
            MigrationExecutor(connection).migrate(new)
            after_reapply = snapshot()
            self.assertEqual(before, after_reapply)
            self.assertFalse(
                WriteOffProposal.objects.filter(corrects__isnull=False).exists()
            )
            linked = self.make_proposal("retained-lineage", corrects=self.decision)
            populated = snapshot()
            with self.assertRaisesMessage(RuntimeError, "forward recovery"):
                MigrationExecutor(connection).migrate(old)
            self.assertEqual(populated, snapshot())
            linked.refresh_from_db()
            self.assertEqual(linked.corrects_id, self.decision.pk)
        finally:
            MigrationExecutor(connection).migrate(new)
        if os.getenv("BONIRA_CEP044_MIGRATION_TRACE"):
            Path(os.environ["BONIRA_CEP044_MIGRATION_TRACE"]).write_text(
                json.dumps(
                    {
                        "database": "disposable test PostgreSQL only",
                        "before": before,
                        "after_reapply": after_reapply,
                        "after_new_lineage_and_refused_rollback": populated,
                        "preexisting_history_preserved": True,
                        "all_legacy_links_null_after_reapply": True,
                        "populated_lineage_drop_refused": True,
                        "production": False,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )


class WriteOffActionsMigrationTests(CEP044Fixture, TransactionTestCase):
    def test_populated_authority_and_correction_cannot_be_dropped(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        original = self.approve()
        result = self.correct(original)
        before = {
            label: _canonical_hash(
                list(apps.get_model(label).objects.order_by("pk").values())
            )
            for label in (
                "subledgers.Obligation",
                "subledgers.WriteOffProposal",
                "subledgers.WriteOffDecision",
                "subledgers.WriteOffReversal",
                "subledgers.WriteOffCorrection",
                "accounting.JournalEntry",
                "accounting.JournalLine",
                "accounting.SourceRecognitionDraft",
                "audit.AuditEvent",
                "organizations.MembershipRoleAssignment",
                "organizations.MembershipScopeGrant",
            )
        }
        with self.assertRaisesMessage(RuntimeError, "forward recovery"):
            MigrationExecutor(connection).migrate(
                [("subledgers", "0007_cep044_writeoff_correction_lineage")]
            )
        after = {
            label: _canonical_hash(
                list(apps.get_model(label).objects.order_by("pk").values())
            )
            for label in before
        }
        self.assertEqual(before, after)
        result.refresh_from_db()
        self.assertEqual(result.original_id, original.pk)
