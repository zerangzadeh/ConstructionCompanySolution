"""INT-C02 source availability, amount independence and retained lineage."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.accounting.models import JournalEntry
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.billing.models import (
    PayableCertificate,
    ProgressClaim,
    VariationBillingEligibility,
)
from apps.billing.variation_handoffs import (
    eligibility_for_source,
    reconcile_variation_billing,
    retry_variation_billing_handoff,
)
from apps.contracts import test_contractual_records as existing_tests
from apps.contracts.contractual_services import (
    create_contractual_revision,
    decide_contractual_record,
    submit_contractual_record,
)
from apps.contracts.models import ContractualRecord
from apps.contracts.services import create_contract, transition_contract_status
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.parties.services import create_business_party
from apps.projects.models import Project
from apps.subledgers.models import Obligation
from apps.treasury.models import TreasuryMovement


class VariationFixture:
    make_record = existing_tests.ContractualRecordTests.make_record

    def setUp(self):
        self.organization = Organization.objects.create(
            name="CEP037 test", slug="cep037"
        )
        self.owner = User.objects.create_user(username="cep037-preparer")
        self.approver = User.objects.create_user(username="cep037-checker")
        for user in (self.owner, self.approver):
            role = OrganizationRole.objects.create(
                code=f"cep037-{user.pk}", name="Isolated explicit grants"
            )
            role.permissions.set(BusinessPermission.objects.filter(is_active=True))
            membership = self.organization.memberships.create(
                user=user, role="company_owner", role_definition=role, status="active"
            )
            MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=membership,
                scope_type=AuthorizationScopeType.ORGANIZATION,
                reason="CEP037 fixture",
            )
        self.project = Project.objects.create(
            organization=self.organization, code="VAR", name="Variation test"
        )
        self.party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="Synthetic counterparty",
        )
        self.contract = create_contract(
            organization=self.organization,
            project=self.project,
            actor=self.owner,
            contract_number="VAR037",
            title="Test",
            counterparty_name="Synthetic",
            party=self.party,
            contract_value=Decimal(1000),
        )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            status="active",
        )
        self.contract.refresh_from_db()

    def approve(self, source, entitlement=True, amount=None):
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=source
        )
        return decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=source,
            approved=True,
            reason="Explicit source decision",
            entitlement_approved=entitlement,
            approved_amount=amount,
        )

    def original(self, entitlement=True, amount=None):
        return self.approve(self.make_record(kind="variation"), entitlement, amount)

    def correction(self, source, action="correction", entitlement=True, amount=None):
        revised = create_contractual_revision(
            organization=self.organization,
            actor=self.owner,
            predecessor=source,
            revision_action=action,
            reason="Explicit source revision",
            idempotency_key=f"{source.pk}-{action}",
        )
        return self.approve(revised, entitlement, amount)

    def retry(self, source, key="retry037"):
        return retry_variation_billing_handoff(
            organization=self.organization,
            actor=self.owner,
            source=source,
            idempotency_key=key,
        )

    def reconcile(self, source):
        return reconcile_variation_billing(
            organization=self.organization, actor=self.owner, source=source
        )


class VariationPredicateTests(SimpleTestCase):
    def test_only_entitlement_and_action_govern_source_availability(self):
        for amount in (None, Decimal(0), Decimal(12)):
            for action in ("original", "correction", "cancellation"):
                for entitlement in (True, False):
                    self.assertEqual(
                        eligibility_for_source(
                            SimpleNamespace(
                                revision_action=action,
                                entitlement_approved=entitlement,
                                approved_amount=amount,
                            )
                        ),
                        entitlement and action != "cancellation",
                    )


class VariationHandoffTests(VariationFixture, TestCase):
    def test_auto_handoff_and_amount_independence_create_no_financial_objects(self):
        source = self.original()
        target = VariationBillingEligibility.objects.get(source=source)
        self.assertTrue(target.active_at_occurrence)
        self.assertEqual(self.retry(source).pk, target.pk)
        self.assertEqual(self.retry(source, "other-key").pk, target.pk)
        self.assertEqual(VariationBillingEligibility.objects.count(), 1)
        self.assertIsNone(target.source_snapshot["approved_amount_evidence_only"])
        zero = self.correction(source, amount=Decimal(0))
        self.assertTrue(
            VariationBillingEligibility.objects.get(source=zero).active_at_occurrence
        )
        self.assertFalse(ProgressClaim.objects.exists())
        self.assertFalse(PayableCertificate.objects.exists())
        self.assertFalse(Obligation.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(TreasuryMovement.objects.exists())
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.contract_value, Decimal(1000))

    def test_latest_approved_chain_ignores_draft_and_timestamp_order(self):
        source = self.original()
        first = VariationBillingEligibility.objects.get(source=source)
        draft = create_contractual_revision(
            organization=self.organization,
            actor=self.owner,
            predecessor=source,
            revision_action="correction",
            reason="Draft only",
            idempotency_key="draft037",
        )
        self.assertEqual(self.reconcile(draft)["active_eligibility_id"], str(first.pk))
        replacement = self.approve(draft)
        with self.assertRaises(ValidationError):
            self.retry(source)
        trace = self.reconcile(source)
        self.assertEqual(trace["latest_approved_source_id"], str(replacement.pk))
        self.assertEqual(trace["latest_approved_version"], 2)
        self.assertEqual(len(trace["targets"]), 2)
        self.assertFalse(trace["targets"][0]["is_current_source"])

    def test_false_entitlement_correction_and_cancellation_preserve_old_evidence(self):
        source = self.original()
        original = VariationBillingEligibility.objects.get(source=source)
        payload = original.source_snapshot.copy()
        denied = self.correction(source, entitlement=False)
        inactive = VariationBillingEligibility.objects.get(source=denied)
        self.assertFalse(inactive.active_at_occurrence)
        self.assertEqual(inactive.predecessor_id, original.pk)
        self.assertIsNone(self.reconcile(denied)["active_eligibility_id"])
        restored = self.correction(denied, entitlement=True, amount=Decimal(0))
        self.assertIsNotNone(self.reconcile(restored)["active_eligibility_id"])
        cancelled = self.correction(restored, action="cancellation", entitlement=False)
        trace = self.reconcile(cancelled)
        self.assertIsNone(trace["active_eligibility_id"])
        self.assertFalse(trace["handoff_pending"])
        original.refresh_from_db()
        self.assertEqual(original.source_snapshot, payload)
        self.assertTrue(original.active_at_occurrence)
        for operation in (
            original.save,
            original.delete,
            lambda: VariationBillingEligibility.objects.update(
                active_at_occurrence=False
            ),
            lambda: VariationBillingEligibility.objects.all().delete(),
        ):
            with self.assertRaises(ValidationError):
                operation()
        if path := os.environ.get("CEP037_TRACE_PATH"):
            trace["failure_audit_count"] = AuditEvent.objects.filter(
                action=AuditAction.VARIATION_BILLING_FAILED
            ).count()
            Path(path).write_text(json.dumps(trace, indent=2), encoding="utf-8")

    def test_approved_correction_of_returned_source_uses_approved_effective_state(self):
        source = self.make_record(kind="variation")
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=source
        )
        decide_contractual_record(
            organization=self.organization,
            actor=self.approver,
            record=source,
            approved=False,
            reason="Return source for correction",
        )
        source.refresh_from_db()
        approved = self.correction(source)
        target = VariationBillingEligibility.objects.get(source=approved)
        self.assertTrue(target.active_at_occurrence)
        self.assertIsNone(target.predecessor_id)
        self.assertEqual(
            target.source_snapshot["source_chain"][1]["source_id"], str(source.pk)
        )
        self.assertIsNone(target.source_snapshot["source_chain"][1]["approved_at"])
        self.assertEqual(
            self.reconcile(source)["active_eligibility_id"], str(target.pk)
        )

    def test_false_entitlement_original_has_no_active_eligibility(self):
        source = self.original(entitlement=False, amount=Decimal(100))
        self.assertIsNone(self.reconcile(source)["active_eligibility_id"])
        self.assertFalse(
            VariationBillingEligibility.objects.get(source=source).active_at_occurrence
        )

    def test_target_failure_preserves_approved_source_and_retains_revalidated_retry(
        self,
    ):
        def fail_after_insert(**kwargs):
            if kwargs["action"] == AuditAction.VARIATION_BILLING_ACCEPTED:
                raise IntegrityError("injected after target insert")
            return record_audit_event(**kwargs)

        with patch(
            "apps.billing.variation_handoffs.record_audit_event",
            side_effect=fail_after_insert,
        ):
            source = self.original()
        source.refresh_from_db()
        self.assertEqual(source.status, "approved")
        self.assertFalse(VariationBillingEligibility.objects.exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.VARIATION_BILLING_FAILED
            ).exists()
        )
        self.assertTrue(self.reconcile(source)["handoff_pending"])
        self.assertTrue(self.retry(source).active_at_occurrence)
        correction = self.correction(source, entitlement=False)
        with self.assertRaises(ValidationError):
            self.retry(source)
        self.assertIsNone(self.reconcile(correction)["active_eligibility_id"])

    def test_tenant_scope_manual_retry_and_default_grants_fail_closed(self):
        self.assertFalse(
            OrganizationRole.objects.filter(
                is_system=True,
                code__in=("tenant_owner", "tenant_admin"),
                permissions__code__in=[
                    P.BILLING_VARIATION_ELIGIBILITY_VIEW,
                    P.BILLING_VARIATION_ELIGIBILITY_RETRY,
                ],
            ).exists()
        )
        # L2 source acceptance does not imply manual Billing retry/view rights.
        checker_role = self.organization.memberships.get(
            user=self.approver
        ).role_definition
        checker_role.permissions.remove(
            *BusinessPermission.objects.filter(
                code__in=[
                    P.BILLING_VARIATION_ELIGIBILITY_VIEW,
                    P.BILLING_VARIATION_ELIGIBILITY_RETRY,
                ]
            )
        )
        source = self.original()
        self.assertTrue(
            VariationBillingEligibility.objects.get(source=source).active_at_occurrence
        )
        with self.assertRaises(PermissionDenied):
            retry_variation_billing_handoff(
                organization=self.organization,
                actor=self.approver,
                source=source,
                idempotency_key="no-grant",
            )
        other = Organization.objects.create(name="Other", slug="other037")
        with self.assertRaises(PermissionDenied):
            retry_variation_billing_handoff(
                organization=other,
                actor=self.owner,
                source=source,
                idempotency_key="outside",
            )
        MembershipScopeGrant.objects.filter(membership__user=self.owner).delete()
        with self.assertRaises(PermissionDenied):
            self.retry(source)

    def test_unapproved_and_nonvariation_sources_cannot_be_retried(self):
        source = self.make_record(kind="variation")
        with self.assertRaises(ValidationError):
            self.retry(source)
        claim = self.make_record(key="claim037", kind="claim")
        self.approve(claim)
        with self.assertRaises(ValidationError):
            self.retry(claim)
        self.assertFalse(VariationBillingEligibility.objects.exists())


class VariationAffectedRegression(VariationFixture, TestCase):
    test_source_approval = existing_tests.ContractualRecordTests.test_governed_approval_records_explicit_facts_and_no_source_effects
    test_source_correction = existing_tests.ContractualRecordTests.test_approved_correction_and_cancellation_preserve_final_history
    test_source_withdrawal = existing_tests.ContractualRecordTests.test_submitted_withdrawal_closes_workflow_atomically


class VariationMigrationTests(VariationFixture, TransactionTestCase):
    def test_populated_source_history_survives_additive_rollback_reapply(self):
        with patch("apps.billing.variation_handoffs.accept_approved_variation_event"):
            source = self.original()
        before = ContractualRecord.objects.filter(pk=source.pk).values().get()
        latest = ("billing", "0017_cep037_variation_billing_eligibility")
        previous = ("billing", "0016_cep036_indexation")
        try:
            MigrationExecutor(connection).migrate([previous])
            self.assertNotIn(
                "billing_variationbillingeligibility",
                connection.introspection.table_names(),
            )
            MigrationExecutor(connection).migrate([latest])
            self.assertEqual(
                ContractualRecord.objects.filter(pk=source.pk).values().get(), before
            )
            self.assertFalse(VariationBillingEligibility.objects.exists())
            self.assertEqual(self.retry(source).source_id, source.pk)
            if path := os.environ.get("CEP037_MIGRATION_TRACE_PATH"):
                Path(path).write_text(
                    json.dumps(
                        {
                            "populated_source_before_after_equal": True,
                            "rollback_reapply": "PASS",
                            "inferred_eligibility_before_explicit_retry": 0,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        finally:
            MigrationExecutor(connection).migrate([latest])


class VariationConcurrencyTests(VariationFixture, TransactionTestCase):
    def test_concurrent_retries_preserve_one_source_occurrence(self):
        with patch("apps.billing.variation_handoffs.accept_approved_variation_event"):
            source = self.original()
        barrier = Barrier(2)

        def accept(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.retry(source, key=f"race037-{index}").pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, (1, 2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(VariationBillingEligibility.objects.count(), 1)
