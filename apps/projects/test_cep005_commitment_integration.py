"""Real PostgreSQL root tests with synthetic trusted child evidence; no producer activation."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.access_services import bootstrap_membership_authorization
from apps.organizations.models import (
    Organization,
    OrganizationMembership,
    OrganizationStatus,
)
from apps.projects import commitment_integration as root
from apps.projects import test_p4_budget_preparation as helpers
from apps.projects import test_p4_integrated_cost as legacy
from apps.projects.models import ProjectCostFact, ProjectCostMeasure
from apps.projects.services import (
    accept_budget_version,
    approve_project_cost_source_contract,
    create_project,
    create_project_cost_source_contract,
)


def _authorized_project(**kwargs):
    # Adapt retained fixture construction to the existing explicit-role policy.
    # No production permission rule or legacy shared test file is changed.
    for membership in OrganizationMembership.objects.all():
        bootstrap_membership_authorization(
            membership=membership, actor=membership.user, source="cep005-test-fixture"
        )
    return create_project(**kwargs)


class CanonicalIdentityTests(SimpleTestCase):
    def test_exact_five_components(self):
        self.assertEqual(
            root.canonical_key("contract", "type", "source", "version", "COMMITMENT"),
            ("contract", "type", "source", "version", "COMMITMENT"),
        )
        self.assertEqual(len(root.canonical_key("c", "t", "s", "v", "r")), 5)


class CommitmentRootTests(TransactionTestCase):
    _draft = helpers.BudgetPreparationTests._draft
    _classify_and_submit = helpers.BudgetPreparationTests._classify_and_submit

    def setUp(self):
        with patch.object(helpers, "create_project", side_effect=_authorized_project):
            helpers.BudgetPreparationTests.setUp(self)
        self.budget = accept_budget_version(
            budget=self._classify_and_submit(self._draft()),
            actor=self.approver,
            approval_reason="Independent CEP-005 fixture budget",
        )
        self.contract = create_project_cost_source_contract(
            organization=self.organization,
            actor=self.preparer,
            producer_key="pcp-po-commitment",
            version=1,
            measure=ProjectCostMeasure.COMMITMENT,
            source_model="procurement.purchaseorder",
            event_schema="synthetic-child.v1",
            classification_policy_reference="MAPPING-1",
            recognition_policy_reference="SOURCE-APPROVED",
            reconciliation_policy_reference="RECON-1",
            requires_financial_evidence=False,
        )
        self.contract = approve_project_cost_source_contract(
            contract=self.contract, actor=self.approver
        )
        self.evidence = {}
        self.effect = root.CostEffect(
            amount=Decimal("100.00"),
            currency="IRR",
            recognition_date=date(2026, 10, 14),
            cbs_node=self.cbs,
            wbs_node=self.wbs,
            cost_center=self.cost_center,
            classification_reference="MAPPING-1",
            valuation_reference="SOURCE-AMOUNT-1",
        )

        def validate(**kwargs):
            return self.evidence[(kwargs["source_id"], kwargs["source_version"])]

        self.producer = root.Producer(
            "procurement",
            self.contract.source_model,
            self.contract.event_schema,
            validate,
        )
        self.registry = patch.object(
            root, "PRODUCERS", {self.contract.producer_key: self.producer}
        )
        self.registry.start()
        self.addCleanup(self.registry.stop)

    def instruction(self, version="1", source="PO-1", **changes):
        item = root.SourceInstruction(
            version, version, "eligible", "CREATE", (self.effect,)
        )
        self.evidence[source, version] = replace(item, **changes)
        return self.evidence[source, version]

    def apply(self, version="1", source="PO-1", **changes):
        return root.process_commitment(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract_id=str(self.contract.pk),
            source_id=source,
            source_version=version,
            **changes,
        )

    def test_approved_occurrence_replay_and_changed_payload(self):
        self.instruction()
        before = dict(self.evidence)
        first = self.apply()
        replay = self.apply(correlation_id=uuid4())
        self.assertEqual(first.fact_ids, replay.fact_ids)
        self.assertEqual(replay.outcome, "replayed")
        self.assertEqual(ProjectCostFact.objects.count(), 1)
        self.assertEqual(self.evidence, before)
        fact = ProjectCostFact.objects.get(pk=first.fact_ids[0])
        self.assertEqual((fact.source_id, fact.source_version), ("PO-1", "1"))
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"], source_line_reference="different"
        )
        with self.assertRaisesMessage(root.CommitmentRejected, "payload_conflict"):
            self.apply()
        self.assertEqual(ProjectCostFact.objects.count(), 1)
        print(
            "CEP005 TRACE: canonical identity -> one fact -> revalidated replay -> conflict rejected"
        )

    def test_versions_adjustment_stale_replay_and_cancellation_release(self):
        self.instruction()
        initial = self.apply()
        self.instruction(
            "2",
            operation="SUPERSEDE",
            predecessor_version="1",
            prior_fact_ids=initial.fact_ids,
            effects=(replace(self.effect, amount=Decimal("20.00")),),
        )
        second = self.apply("2")
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"],
            active_source_version="2",
            eligibility="superseded",
        )
        self.assertEqual(self.apply().outcome, "replayed")
        self.instruction("0", active_source_version="2")
        with self.assertRaisesMessage(root.CommitmentRejected, "stale_source_version"):
            self.apply("0")
        self.instruction(
            "3",
            eligibility="cancelled",
            operation="RELEASE",
            predecessor_version="2",
            prior_fact_ids=initial.fact_ids + second.fact_ids,
            effects=(replace(self.effect, amount=Decimal("120.00")),),
        )
        released = self.apply("3")
        self.assertEqual(
            ProjectCostFact.objects.get(pk=released.fact_ids[0]).kind,
            "commitment_relief",
        )
        result = root.reconcile_commitment(
            organization=self.organization,
            project=self.project,
            actor=self.preparer,
            contract_id=str(self.contract.pk),
            source_id="PO-1",
            source_version="3",
        )
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["active_source_version"], "3")
        self.assertEqual(result["effective_commitment"], Decimal(0))
        self.assertEqual(len(result["lineage"]), 3)
        print(
            "CEP005 TRACE: v1 CREATE -> v2 SUPERSEDE(+20) -> stale REJECT -> v3 RELEASE(120); net=0"
        )

    def test_reversal_is_linked_and_cancellation_cannot_reverse(self):
        self.instruction()
        first = self.apply()
        self.instruction(
            "2",
            operation="REVERSE",
            predecessor_version="1",
            prior_fact_ids=first.fact_ids,
            effects=(replace(self.effect, amount=Decimal("-100.00")),),
        )
        reversal = self.apply("2")
        self.assertEqual(
            ProjectCostFact.objects.get(pk=reversal.fact_ids[0]).amount,
            Decimal("-100.00"),
        )
        self.instruction(
            "3",
            operation="REVERSE",
            predecessor_version="2",
            prior_fact_ids=first.fact_ids,
            effects=(replace(self.effect, amount=Decimal("-100.00")),),
        )
        with self.assertRaisesMessage(root.CommitmentRejected, "already_reversed"):
            self.apply("3")
        self.evidence["PO-1", "3"] = replace(
            self.evidence["PO-1", "3"], eligibility="cancelled"
        )
        with self.assertRaisesMessage(
            root.CommitmentRejected, "cancellation_requires_release"
        ):
            self.apply("3")

    def test_target_and_success_audit_rollback_durable_failure_retry_revalidates(self):
        self.instruction()
        source_before = dict(self.evidence)
        emit = root._emit

        def fail_success(**kwargs):
            if kwargs["metadata"]["stage"] == "succeeded":
                raise RuntimeError("synthetic success-evidence fault")
            return emit(**kwargs)

        with (
            patch.object(root, "_emit", side_effect=fail_success),
            self.assertRaises(RuntimeError),
        ):
            self.apply()
        self.assertEqual(ProjectCostFact.objects.count(), 0)

        self.assertFalse(
            AuditEvent.objects.filter(action="project_cost.fact_recorded").exists()
        )
        failure = AuditEvent.objects.get(action=root.ACTION, metadata__stage="failed")
        self.assertEqual(self.evidence, source_before)
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"], eligibility="pending"
        )
        with self.assertRaisesMessage(root.CommitmentRejected, "source_ineligible"):
            self.apply(retry_of=failure.entity_id)
        self.instruction()
        result = self.apply(retry_of=failure.entity_id)
        self.assertEqual(
            self.apply(retry_of=failure.entity_id).fact_ids, result.fact_ids
        )
        self.assertEqual(ProjectCostFact.objects.count(), 1)
        print(
            "CEP005 TRANSACTION: attempt COMMIT -> fact+success ROLLBACK -> failure COMMIT -> retry revalidates -> one fact"
        )

    def test_missing_contract_producer_mapping_cutoff_and_outer_transaction_fail_closed(
        self,
    ):
        self.instruction()
        with self.assertRaisesMessage(root.CommitmentRejected, "missing_contract"):
            root.process_commitment(
                organization=self.organization,
                project=self.project,
                actor=self.preparer,
                contract_id=str(uuid4()),
                source_id="PO-1",
                source_version="1",
            )
        with (
            patch.object(root, "PRODUCERS", {}),
            self.assertRaisesMessage(root.CommitmentRejected, "unapproved_producer"),
        ):
            self.apply()
        for changes, reason in [
            ({"effects": ()}, "missing_mapping"),
            ({"effects": (replace(self.effect, currency="USD"),)}, "invalid_mapping"),
            ({"cutoff_required": True}, "missing_cutoff"),
        ]:
            self.instruction(**changes)
            with self.assertRaisesMessage(root.CommitmentRejected, reason):
                self.apply()
        with (
            transaction.atomic(),
            self.assertRaisesMessage(
                root.CommitmentRejected, "requires_autocommit_boundary"
            ),
        ):
            self.apply()
        self.assertEqual(ProjectCostFact.objects.count(), 0)

    def test_zero_result_successor_retains_version_lineage(self):
        effective_at = timezone.now()
        self.instruction(
            source="ZERO",
            effects=(replace(self.effect, amount=Decimal(0)),),
            effective_at=effective_at,
        )
        self.assertEqual(self.apply(source="ZERO").fact_ids, ())
        event = AuditEvent.objects.get(action=root.ACTION, metadata__stage="succeeded")
        self.assertEqual(
            event.metadata["source_effective_at"], effective_at.isoformat()
        )
        self.instruction(
            "2", source="ZERO", operation="ADJUST", predecessor_version="1"
        )
        self.assertEqual(len(self.apply("2", source="ZERO").fact_ids), 1)
        self.instruction(
            "3", source="ZERO", operation="ADJUST", predecessor_version="2"
        )
        with self.assertRaisesMessage(
            root.CommitmentRejected, "missing_correction_link"
        ):
            self.apply("3", source="ZERO")
        self.instruction(source="NAIVE", effective_at=effective_at.replace(tzinfo=None))
        with self.assertRaisesMessage(
            root.CommitmentRejected, "invalid_source_effective_time"
        ):
            self.apply(source="NAIVE")

    def test_reconciliation_missing_mismatch_duplicate_and_broken_lineage_is_read_only(
        self,
    ):
        self.instruction()
        args = {
            "organization": self.organization,
            "project": self.project,
            "actor": self.preparer,
            "contract_id": str(self.contract.pk),
            "source_id": "PO-1",
            "source_version": "1",
        }
        self.assertIn(
            "missing_target_effect", root.reconcile_commitment(**args)["issues"]
        )
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"], eligibility="pending"
        )
        self.assertEqual(root.reconcile_commitment(**args)["issues"], [])
        self.instruction()
        self.apply()
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"],
            effects=(replace(self.effect, amount=Decimal("101.00")),),
        )
        self.assertIn(
            "source_payload_mismatch", root.reconcile_commitment(**args)["issues"]
        )
        self.instruction()
        self.evidence["PO-1", "1"] = replace(
            self.evidence["PO-1", "1"], active_source_version="2"
        )
        event = AuditEvent.objects.get(action=root.ACTION, metadata__stage="succeeded")
        corrupt = {**event.metadata, "prior_fact_ids": [str(uuid4())]}
        record_audit_event(
            action=root.ACTION,
            entity_type=root.ENTITY,
            entity_id=str(uuid4()),
            organization=self.organization,
            actor=self.preparer,
            metadata=corrupt,
        )
        count = AuditEvent.objects.count(), ProjectCostFact.objects.count()
        result = root.reconcile_commitment(**args)
        self.assertTrue(
            {
                "source_version_mismatch",
                "stale_target_effect",
                "duplicate_target_effect",
                "lineage_inconsistency",
            }.issubset(result["issues"])
        )
        self.assertEqual(
            count, (AuditEvent.objects.count(), ProjectCostFact.objects.count())
        )

    def test_audit_catalog_migration_reverse_reapply_preserves_history(self):
        self.instruction()
        self.apply()
        before = list(AuditEvent.objects.order_by("pk").values())
        call_command("migrate", "audit", "0053", verbosity=0)
        self.assertFalse(
            MigrationRecorder(connection)
            .migration_qs.filter(
                app="audit", name="0054_cep005_integration_attempt_action"
            )
            .exists()
        )
        call_command("migrate", "audit", "0054", verbosity=0)
        self.assertEqual(before, list(AuditEvent.objects.order_by("pk").values()))
        self.assertEqual(
            root.ACTION.values if hasattr(root.ACTION, "values") else str(root.ACTION),
            "project_cost.integration_attempt",
        )
        print(
            "CEP005 MIGRATION: reverse 0054 -> 0053 -> reapply 0054; all audit rows byte/value-preserved"
        )

    def test_subcontract_family_uses_same_root_and_current_tenant_authority(self):
        self.contract = create_project_cost_source_contract(
            organization=self.organization,
            actor=self.preparer,
            producer_key="pcp-subcontract-commitment",
            version=1,
            measure=ProjectCostMeasure.COMMITMENT,
            source_model="contracts.subcontract",
            event_schema="synthetic-subcontract.v1",
            classification_policy_reference="MAPPING-1",
            recognition_policy_reference="SOURCE-APPROVED",
            reconciliation_policy_reference="RECON-1",
            requires_financial_evidence=False,
        )
        self.contract = approve_project_cost_source_contract(
            contract=self.contract, actor=self.approver
        )
        producer = root.Producer(
            "contracts",
            self.contract.source_model,
            self.contract.event_schema,
            self.producer.validate,
        )
        self.instruction(source="SC-1")
        with patch.object(root, "PRODUCERS", {self.contract.producer_key: producer}):
            self.apply(source="SC-1")
            before = AuditEvent.objects.count()
            with self.assertRaises(PermissionDenied):
                root.process_commitment(
                    organization=self.organization,
                    project=self.project,
                    actor=self.outsider,
                    contract_id=str(self.contract.pk),
                    source_id="SC-1",
                    source_version="1",
                )
            self.assertEqual(AuditEvent.objects.count(), before)
            Organization.objects.filter(pk=self.organization.pk).update(
                status=OrganizationStatus.SUSPENDED
            )
            with self.assertRaises(PermissionDenied):
                self.apply(source="SC-1")
        self.assertEqual(ProjectCostFact.objects.count(), 1)


class RetainedProjectionRegressionTests(legacy.IntegratedProjectCostTests):
    """Existing five projection tests, with only current explicit fixture authority."""

    def setUp(self):
        with patch.object(helpers, "create_project", side_effect=_authorized_project):
            super().setUp()
