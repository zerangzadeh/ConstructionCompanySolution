"""Synthetic CEP-057 preparation evidence; never a tenant dataset approval."""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.organizations.models import OrganizationMembership

from . import test_cep023 as fixtures
from .leave_models import LeaveBalanceEntry, LeavePolicyVersion
from .leave_opening_preparation import (
    OpeningBalanceDataset,
    OpeningBalanceRow,
    OpeningBalanceTotal,
    prepare_leave_opening_import,
)


class LeaveOpeningPreparationTests(TestCase):
    setUp = fixtures.LeaveAuthorityTests.setUp
    policy = fixtures.LeaveAuthorityTests.policy
    credit = fixtures.LeaveAuthorityTests.credit

    def source(self, **changes):
        policy = self.policy()
        row = OpeningBalanceRow(
            source_id="row-1",
            source_version="source-row-v1",
            evidence_reference="synthetic-source-document-1",
            employee_id=self.employee.pk,
            relationship_id=self.relationship.pk,
            policy_id=policy.pk,
            unit="minutes",
            quantity=D("120.5000"),
        )
        dataset = OpeningBalanceDataset(
            source_reference="synthetic-source-dataset",
            source_version="dataset-v1",
            approval_reference="synthetic-approval-claim-not-verification",
            as_of=date(2026, 1, 1),
            cutover_on=date(2026, 1, 2),
            expected_count=1,
            expected_totals=(OpeningBalanceTotal(policy.pk, "minutes", row.quantity),),
            rows=(row,),
        )
        return replace(dataset, **changes)

    def prepare(self, dataset, **changes):
        return prepare_leave_opening_import(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "dataset": dataset,
                }
                | changes
            )
        )

    def test_validated_mapping_retains_evidence_without_writes_or_authority(self):
        dataset = self.source()
        with CaptureQueriesContext(connection) as captured:
            result = self.prepare(dataset)
        self.assertTrue(result["candidate_validation_passed"])
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["validated_count"], 1)
        self.assertEqual(result["exception_count"], 0)
        self.assertEqual(
            result["mapping"][0]["source"]["source_version"], "source-row-v1"
        )
        self.assertEqual(
            result["mapping"][0]["source"]["relationship_id"], str(self.relationship.pk)
        )
        self.assertEqual(result["as_of"], "2026-01-01")
        self.assertEqual(result["cutover_on"], "2026-01-02")
        self.assertFalse(result["approval_verified"])
        self.assertFalse(result["migration_execution_allowed"])
        self.assertFalse(result["authority_cutover"])
        self.assertEqual(result["target_entries_created"], 0)
        writes = [
            item["sql"]
            for item in captured
            if item["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(writes, [])
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_repeat_is_deterministic_and_changed_evidence_changes_fingerprint(self):
        dataset = self.source()
        first = self.prepare(dataset)
        self.assertEqual(self.prepare(dataset), first)
        changed = self.prepare(replace(dataset, source_version="dataset-v2"))
        self.assertNotEqual(changed["input_fingerprint"], first["input_fingerprint"])
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_control_total_mismatch_is_reported_without_import(self):
        dataset = self.source()
        result = self.prepare(
            replace(
                dataset,
                expected_totals=(replace(dataset.expected_totals[0], quantity=D(1)),),
            )
        )
        self.assertFalse(result["candidate_validation_passed"])
        self.assertFalse(result["reconciliation"][0]["matched"])
        self.assertEqual(result["reconciliation"][0]["source_quantity"], "120.5000")

    def test_missing_and_extra_control_groups_are_not_zero_balances(self):
        dataset = self.source()
        result = self.prepare(
            replace(
                dataset,
                expected_totals=(replace(dataset.expected_totals[0], unit="days"),),
            )
        )
        self.assertEqual(len(result["reconciliation"]), 2)
        self.assertFalse(result["candidate_validation_passed"])
        self.assertTrue(all(not row["matched"] for row in result["reconciliation"]))

    def test_empty_or_mismatched_dataset_and_duplicate_source_ids_fail_closed(self):
        dataset = self.source()
        for changes in (
            {"rows": (), "expected_count": 0},
            {"expected_count": 2},
            {"rows": (dataset.rows[0], dataset.rows[0]), "expected_count": 2},
            {"approval_reference": ""},
            {"source_version": ""},
            {"as_of": None},
            {"expected_totals": ()},
            {"expected_totals": dataset.expected_totals * 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.prepare(replace(dataset, **changes))

    def test_invalid_quantities_never_round_convert_or_infer(self):
        dataset = self.source()
        for quantity in (1.2, D("NaN"), D("Infinity"), D("1.00001"), D(10000000000)):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.prepare(
                    replace(
                        dataset, rows=(replace(dataset.rows[0], quantity=quantity),)
                    )
                )

    def test_missing_row_evidence_is_not_replaced_by_request_history(self):
        dataset = self.source()
        with self.assertRaises(ValidationError):
            self.prepare(
                replace(
                    dataset, rows=(replace(dataset.rows[0], evidence_reference=""),)
                )
            )

    def test_foreign_or_unknown_references_return_no_row_report(self):
        dataset = self.source()
        foreign_policy = self.policy(
            organization=self.other, actor=self.other_actor, category_code="FOREIGN"
        )
        for changes in (
            {"policy_id": foreign_policy.pk},
            {"relationship_id": uuid4()},
            {"employee_id": uuid4()},
        ):
            with self.subTest(changes=changes), self.assertRaises(PermissionDenied):
                self.prepare(
                    replace(dataset, rows=(replace(dataset.rows[0], **changes),))
                )
        with self.assertRaises(PermissionDenied):
            self.prepare(dataset, organization=self.other, actor=self.other_actor)

    def test_foreign_control_policy_is_denied_even_without_source_rows(self):
        dataset = self.source()
        with self.assertRaises(PermissionDenied):
            self.prepare(
                replace(
                    dataset,
                    expected_totals=(OpeningBalanceTotal(uuid4(), "days", D(0)),),
                )
            )

    def test_inactive_membership_and_actor_without_membership_are_denied(self):
        dataset = self.source()
        with self.assertRaises(PermissionDenied):
            self.prepare(dataset, actor=self.other_actor)
        OrganizationMembership.objects.filter(
            organization=self.organization, user=self.actor
        ).update(status="inactive")
        with self.assertRaises(PermissionDenied):
            self.prepare(dataset)

    def test_explicit_balance_permission_is_required_for_same_tenant_actor(self):
        dataset = self.source()
        membership = OrganizationMembership.objects.get(
            organization=self.organization, user=self.actor
        )
        membership.role_definition.permissions.clear()
        for assignment in membership.role_assignments.select_related("role"):
            assignment.role.permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.prepare(dataset)

    def test_policy_episode_unit_and_floor_exceptions_are_explicit(self):
        dataset = self.source()
        changed = replace(
            dataset,
            as_of=date(2024, 1, 1),
            rows=(replace(dataset.rows[0], unit="days", quantity=D(-1)),),
            expected_totals=(
                replace(dataset.expected_totals[0], unit="days", quantity=D(-1)),
            ),
        )
        result = self.prepare(changed)
        self.assertFalse(result["candidate_validation_passed"])
        self.assertEqual(result["exception_count"], 1)
        self.assertEqual(
            set(result["exceptions"][0]["errors"]),
            {
                "ASOF_OUTSIDE_EMPLOYMENT_EPISODE",
                "POLICY_NOT_EFFECTIVE_ASOF",
                "EXPLICIT_UNIT_MISMATCH",
                "SOURCE_BELOW_EXPLICIT_POLICY_FLOOR",
            },
        )

    def test_superseded_version_is_not_silently_rebound(self):
        dataset = self.source()
        policy = LeavePolicyVersion.objects.get(pk=dataset.rows[0].policy_id)
        self.policy(supersedes=policy, evidence_reference="synthetic-correction")
        result = self.prepare(dataset)
        self.assertIn("POLICY_VERSION_SUPERSEDED", result["exceptions"][0]["errors"])
        self.assertEqual(result["mapping"][0]["source"]["policy_id"], str(policy.pk))

    def test_zero_quantity_requires_disposition_and_never_creates_zero_target(self):
        dataset = self.source()
        result = self.prepare(
            replace(dataset, rows=(replace(dataset.rows[0], quantity=D(0)),))
        )
        self.assertIn(
            "ZERO_SOURCE_REQUIRES_EXPLICIT_TARGET_DISPOSITION",
            result["exceptions"][0]["errors"],
        )
        self.assertEqual(LeaveBalanceEntry.objects.count(), 0)

    def test_multiple_openings_for_one_subject_are_not_summed_into_authority(self):
        dataset = self.source()
        result = self.prepare(
            replace(
                dataset,
                expected_count=2,
                rows=dataset.rows + (replace(dataset.rows[0], source_id="row-2"),),
            )
        )
        self.assertEqual(
            result["source_count"],
            result["validated_count"] + result["exception_count"],
        )
        self.assertEqual(result["exception_count"], 2)
        for row in result["exceptions"]:
            self.assertIn(
                "MULTIPLE_OPENINGS_REQUIRE_SOURCE_RECONCILIATION", row["errors"]
            )

    def test_existing_history_is_preserved_and_requires_cutoff_reconciliation(self):
        dataset = self.source()
        source = self.credit()
        before = list(LeaveBalanceEntry.objects.values())
        result = self.prepare(dataset)
        self.assertEqual(result["mapping"][0]["existing_entry_ids"], [str(source.pk)])
        self.assertIn(
            "EXISTING_HISTORY_REQUIRES_CUTOFF_RECONCILIATION",
            result["exceptions"][0]["errors"],
        )
        self.assertEqual(list(LeaveBalanceEntry.objects.values()), before)
