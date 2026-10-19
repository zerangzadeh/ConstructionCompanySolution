"""Conditional INT-B03 framework; bindings here are synthetic, never activation."""

from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

from django.test import TransactionTestCase

from apps.accounting.recognition_registry import (
    RecognitionRequest,
    registered_recognition_owner_policies,
    resolve_recognition_owner,
)
from apps.projects import actual_integration as integration
from apps.projects import financial_actual_source as financial
from apps.projects import test_cep047_actual as fixtures
from apps.projects.actual_sources import ActualRejected
from apps.projects.models import ProjectCostFact
from apps.projects.services import (
    _stable_payload_hash,
    approve_project_cost_source_contract,
    create_project_cost_source_contract,
)

KEY = financial.KEY


class FinancialActualFrameworkTests(TransactionTestCase):
    _draft = fixtures.ActualTargetTests._draft
    _classify_and_submit = fixtures.ActualTargetTests._classify_and_submit
    map_source = fixtures.ActualTargetTests.map_source
    read_source = fixtures.ActualTargetTests.read_source
    consume = fixtures.ActualTargetTests.consume
    candidate = fixtures.ActualTargetTests.candidate
    reconcile = fixtures.ActualTargetTests.reconcile

    def setUp(self):
        fixtures.ActualTargetTests.setUp(self)
        self.native_patch.stop()
        self.contracts[KEY] = approve_project_cost_source_contract(
            contract=create_project_cost_source_contract(
                organization=self.organization,
                actor=self.preparer,
                producer_key=KEY,
                version=1,
                measure="actual",
                source_model="financial.recognition_occurrence",
                event_schema=f"{KEY}.v1",
                classification_policy_reference="TEST-CLASSIFICATION-1",
                recognition_policy_reference="TEST-EXPLICIT-DATE-1",
                reconciliation_policy_reference="TEST-RECONCILIATION-1",
                requires_financial_evidence=True,
            ),
            actor=self.approver,
        )
        self.policies[
            (
                KEY,
                "TEST-CLASSIFICATION-1",
                "TEST-EXPLICIT-DATE-1",
                "TEST-RECONCILIATION-1",
            )
        ] = integration.ActualPolicyBinding(self.map_source)
        policy = next(
            p
            for p in registered_recognition_owner_policies()
            if p.source_family == "Direct Expense"
        )
        self.request = RecognitionRequest(
            self.organization.pk,
            self.organization.pk,
            policy.source_family,
            policy.economic_occurrence,
            uuid4(),
            1,
            policy.recognition_type,
            policy.recognition_owner,
            True,
        )
        self.occurrences = {}
        self.bindings = {}
        self.enroll("source-1")
        self.binding_patch = patch.object(financial, "BINDINGS", self.bindings)
        self.binding_patch.start()
        self.addCleanup(self.binding_patch.stop)

    def enroll(
        self,
        identity,
        *,
        request=None,
        operation="recognize",
        predecessor="",
        active=True,
    ):
        request = request or self.request
        covered = (("expenses.expense", str(request.source_identity)),)
        evidence = {
            "financial": {
                **resolve_recognition_owner(request=request).audit_metadata(),
                "exclusive_coverage_reference": "SYNTHETIC-EXCLUSIVE-COVERAGE-1",
                "covered_sources": covered,
            },
            "operation": operation,
            "predecessor": predecessor,
        }
        template = self.sources["pcp-inv-actual", "source-1"]
        source = replace(
            template,
            producer_key=KEY,
            source_type="financial.recognition_occurrence",
            source_id=identity,
            source_version=_stable_payload_hash(evidence),
            evidence=evidence,
            operation=operation,
            predecessor_id=predecessor,
            active=active,
        )
        self.occurrences[identity] = financial.FinancialOccurrence(
            source, request, covered, "SYNTHETIC-EXCLUSIVE-COVERAGE-1"
        )
        self.bindings[identity] = financial.FinancialSourceBinding(
            lambda source_id, **kwargs: self.occurrences[str(source_id)]
        )

    def test_no_binding_or_mapping_never_creates_fact(self):
        with (
            patch.object(financial, "BINDINGS", {}),
            self.assertRaisesMessage(
                ActualRejected, "approved_financial_occurrence_binding_required"
            ),
        ):
            self.candidate(KEY)
        with (
            patch.object(integration, "POLICIES", {}),
            self.assertRaises(ActualRejected),
        ):
            self.candidate(KEY)
        self.assertEqual(ProjectCostFact.objects.count(), 0)

    def test_source_owner_identity_replay_and_read_only_reconciliation(self):
        candidate = self.candidate(KEY)
        self.assertEqual(ProjectCostFact.objects.count(), 0)
        result = self.consume(candidate)
        self.assertEqual(self.consume(candidate).fact_ids, result.fact_ids)
        self.assertEqual(ProjectCostFact.objects.count(), 1)
        report = self.reconcile(KEY)
        self.assertTrue(report["target_payload_matches"])
        self.assertFalse(report["missing_target"])
        print("CEP059 synthetic contract source/replay/reconciliation:", report)

    def test_cash_and_payroll_settlement_never_become_cost(self):
        for family, occurrence in [
            ("Treasury Cash Movement", "Posted Treasury movement"),
            ("Payroll", "Payroll payable/disbursement request"),
        ]:
            p = next(
                p
                for p in registered_recognition_owner_policies()
                if p.source_family == family and p.economic_occurrence == occurrence
            )
            request = replace(
                self.request,
                source_family=family,
                economic_occurrence=occurrence,
                recognition_type=p.recognition_type,
                recognition_owner=p.recognition_owner,
            )
            self.enroll("source-1", request=request)
            with self.assertRaisesMessage(
                ActualRejected, "cash_settlement_is_not_project_cost"
            ):
                self.candidate(KEY)

    def test_alias_does_not_duplicate_same_economic_occurrence(self):
        self.consume(self.candidate(KEY))
        self.enroll("alias")
        with self.assertRaisesMessage(
            ActualRejected, "financial_occurrence_alias_already_consumed"
        ):
            self.candidate(KEY, "alias")
        self.assertEqual(ProjectCostFact.objects.count(), 1)

    def test_failed_target_rollback_retains_failure_and_revalidates_retry(self):
        candidate = self.candidate(KEY)
        original = integration.record_project_cost_fact

        def fail(**kwargs):
            original(**kwargs)
            raise RuntimeError("synthetic failure")

        with (
            patch.object(integration, "record_project_cost_fact", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.consume(candidate)
        self.assertEqual(ProjectCostFact.objects.count(), 0)
        failure = integration._events(self.organization).get(metadata__stage="failed")
        self.assertEqual(failure.metadata["error_code"], "target_failure")
        self.bindings.clear()
        with self.assertRaises(ActualRejected):
            self.consume(candidate, retry_of=str(failure.entity_id))
        self.enroll("source-1")
        self.consume(candidate, retry_of=str(failure.entity_id))
        self.assertEqual(ProjectCostFact.objects.count(), 1)

    def test_exact_reversal_preserves_history_and_source_version(self):
        candidate = self.candidate(KEY)
        result = self.consume(candidate)
        self.enroll(
            "reverse-2",
            request=replace(self.request, source_version=2),
            operation="reverse",
            predecessor="source-1",
        )
        inverse = self.consume(self.candidate(KEY, "reverse-2"))
        original = ProjectCostFact.objects.get(pk=result.fact_ids[0])
        reversal = ProjectCostFact.objects.get(pk=inverse.fact_ids[0])
        self.assertEqual(reversal.reverses_id, original.pk)
        self.assertEqual(reversal.amount, -original.amount)
        self.assertEqual(self.consume(candidate).fact_ids, result.fact_ids)
        self.assertEqual(len(self.reconcile(KEY, "reverse-2")["target_reversals"]), 1)

    def test_forged_owner_or_source_version_fails_closed(self):
        original = self.occurrences["source-1"]
        self.occurrences["source-1"] = replace(
            original, recognition=replace(self.request, recognition_owner="Treasury")
        )
        with self.assertRaises(ActualRejected):
            self.candidate(KEY)
        self.occurrences["source-1"] = replace(
            original, source=replace(original.source, source_version="forged")
        )
        with self.assertRaisesMessage(
            ActualRejected, "financial_source_version_lineage_mismatch"
        ):
            self.candidate(KEY)

    def test_cross_tenant_recognition_identity_never_creates_fact(self):
        original = self.occurrences["source-1"]
        self.occurrences["source-1"] = replace(
            original,
            recognition=replace(self.request, source_organization_id=uuid4()),
        )
        with self.assertRaises(ActualRejected):
            self.candidate(KEY)
        self.assertEqual(ProjectCostFact.objects.count(), 0)
