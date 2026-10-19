"""Synthetic historical preparation proofs; no EXT-0017 approval or backfill."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.workforce.models import Employee, Person, WorkRelationship

from . import test_cep025_cumulative as fixtures
from .cumulative_services import record_cumulative_for_run
from .models import (
    PayrollCumulativeState,
    PayrollResultLine,
    PayrollRun,
    PayrollRunKind,
    PayrollRunStatus,
)
from .opening_preparation import (
    HistoricalPayrollDataset,
    HistoricalPayrollRow,
    HistoricalPayrollTotal,
    prepare_historical_payroll,
)


class HistoricalPayrollPreparationTests(TestCase):
    _run = fixtures.OperationalCumulativeTests._run
    _lines = fixtures.OperationalCumulativeTests._lines
    _year = fixtures.OperationalCumulativeTests._year

    def setUp(self):
        fixtures.OperationalCumulativeTests.setUp(self)
        self.year = self._year()
        self.person = Person.objects.create(
            organization=self.organization, first_name="Synthetic", last_name="Worker"
        )
        self.relationship = WorkRelationship.objects.create(
            organization=self.organization,
            person=self.person,
            employee_number=self.employee.employee_number,
            effective_start=date(2026, 7, 1),
            legacy_employee=self.employee,
        )

    def dataset(self, lines=None):
        lines = self.lines[:5] if lines is None else lines
        rows = tuple(
            HistoricalPayrollRow(
                source_id=f"row-{line.pk}",
                source_version=line.run.calculation_digest,
                evidence_reference="synthetic-finalized-source-v1",
                source_line_id=line.pk,
                employee_id=self.employee.pk,
                relationship_id=self.relationship.pk,
                component_id=line.component_id,
                component_kind=line.component_kind,
                amount=line.amount,
            )
            for line in lines
        )
        return HistoricalPayrollDataset(
            source_reference="synthetic historical dataset",
            source_version="v1",
            approval_reference="synthetic claim, not EXT0017 approval",
            year_id=self.year.pk,
            as_of=date(2026, 10, 31),
            expected_count=len(rows),
            expected_totals=tuple(
                HistoricalPayrollTotal(row.component_id, row.component_kind, row.amount)
                for row in rows
            ),
            rows=rows,
        )

    def prepare(self, dataset=None):
        return prepare_historical_payroll(
            organization=self.organization,
            actor=self.actor,
            dataset=dataset or self.dataset(),
        )

    def test_reconciled_candidate_never_writes_or_claims_approval(self):
        with CaptureQueriesContext(connection) as captured:
            report = self.prepare()
        self.assertTrue(report["candidate_validation_passed"])
        self.assertEqual(report["source_count"], 5)
        self.assertEqual(report["existing_target_count"], 0)
        for key in (
            "approval_verified",
            "migration_execution_allowed",
            "authority_cutover",
        ):
            self.assertFalse(report[key])
        self.assertEqual(report["target_entries_created"], 0)
        writes = [
            item["sql"]
            for item in captured
            if item["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(writes, [])
        self.assertEqual(PayrollCumulativeState.objects.count(), 0)
        self.assertTrue(all(row["matched"] for row in report["reconciliation"]))
        self.assertTrue(all(row["target_id"] is None for row in report["mapping"]))

    def test_retry_and_reordered_rows_have_identical_evidence(self):
        dataset = self.dataset()
        first = self.prepare(dataset)
        self.assertEqual(first, self.prepare(dataset))
        self.assertEqual(
            first,
            self.prepare(
                replace(
                    dataset,
                    rows=tuple(reversed(dataset.rows)),
                    expected_totals=tuple(reversed(dataset.expected_totals)),
                )
            ),
        )
        self.assertNotEqual(
            first["input_fingerprint"],
            self.prepare(replace(dataset, source_version="v2"))["input_fingerprint"],
        )

    def test_existing_source_targets_are_referenced_without_double_inclusion(self):
        record_cumulative_for_run(
            organization=self.organization, actor=self.actor, run=self.run
        )
        before = list(PayrollCumulativeState.objects.values())
        report = self.prepare()
        self.assertTrue(report["candidate_validation_passed"])
        self.assertEqual(report["existing_target_count"], 5)
        self.assertTrue(
            all(row["status"] == "EXISTING_TARGET" for row in report["mapping"])
        )
        self.assertEqual(self.prepare(), report)
        self.assertEqual(list(PayrollCumulativeState.objects.values()), before)

    def test_finalized_reversal_signed_amounts_preserve_original_history(self):
        record_cumulative_for_run(
            organization=self.organization, actor=self.actor, run=self.run
        )
        original = list(PayrollCumulativeState.objects.values())
        reversal = self._run(
            code="CEP058-REV",
            digest="b" * 64,
            kind=PayrollRunKind.REVERSAL,
            reversal_of=self.run,
        )
        lines = self._lines(reversal, reversed_sign=True)[:5]
        report = self.prepare(self.dataset(lines))
        self.assertTrue(report["candidate_validation_passed"])
        self.assertTrue(
            all(Decimal(row["source"]["amount"]) < 0 for row in report["mapping"])
        )
        self.assertEqual(list(PayrollCumulativeState.objects.values()), original)

    def test_wrong_source_version_amount_component_and_informational_are_exceptions(
        self,
    ):
        dataset = self.dataset([self.lines[0]])
        row = dataset.rows[0]
        for changed in (
            replace(row, source_version="wrong-version"),
            replace(row, amount=Decimal("101.00")),
            replace(row, component_id=uuid4()),
            replace(row, component_kind="taxable"),
        ):
            with self.subTest(changed=changed):
                report = self.prepare(replace(dataset, rows=(changed,)))
                self.assertFalse(report["candidate_validation_passed"])
                self.assertEqual(report["exception_count"], 1)
        self.assertFalse(
            self.prepare(self.dataset([self.lines[-1]]))["candidate_validation_passed"]
        )

    def test_draft_source_or_missing_digest_is_never_finalized_by_preparation(self):
        for change in ({"status": PayrollRunStatus.DRAFT}, {"calculation_digest": ""}):
            with self.subTest(change=change):
                PayrollRun.objects.filter(pk=self.run.pk).update(**change)
                report = self.prepare()
                self.assertEqual(report["exception_count"], 5)
                self.assertIn(
                    "FINALIZED_VERSIONED_SOURCE_REQUIRED",
                    report["exceptions"][0]["errors"],
                )
                PayrollRun.objects.filter(pk=self.run.pk).update(
                    status=PayrollRunStatus.FINALIZED, calculation_digest="a" * 64
                )

    def test_explicit_cutoff_and_current_reset_version_are_required(self):
        dataset = self.dataset()
        report = self.prepare(replace(dataset, as_of=date(2026, 10, 30)))
        self.assertEqual(report["exception_count"], 5)
        self._year()
        report = self.prepare(dataset)
        self.assertIn(
            "PAYROLL_YEAR_NOT_CURRENT_APPROVED", report["exceptions"][0]["errors"]
        )

    def test_full_source_period_must_be_within_explicit_year(self):
        from .models import PayrollPeriod

        PayrollPeriod.objects.filter(pk=self.period.pk).update(
            starts_on=date(2026, 6, 1)
        )
        report = self.prepare()
        self.assertIn(
            "SOURCE_OUTSIDE_EXPLICIT_YEAR_OR_ASOF", report["exceptions"][0]["errors"]
        )

    def test_relationship_must_cover_the_source_period_end(self):
        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            effective_end=date(2026, 10, 30)
        )
        report = self.prepare()
        self.assertIn(
            "SOURCE_OUTSIDE_EXPLICIT_WORK_RELATIONSHIP",
            report["exceptions"][0]["errors"],
        )

    def test_cross_tenant_or_missing_objects_fail_before_evidence_is_returned(self):
        dataset = self.dataset()
        other = Organization.objects.create(name="Other", slug="cep058-other")
        person = Person.objects.create(
            organization=other, first_name="Other", last_name="Worker"
        )
        relationship = WorkRelationship.objects.create(
            organization=other,
            person=person,
            employee_number="OTHER",
            effective_start=date(2026, 1, 1),
        )
        for changed in (
            replace(dataset, year_id=uuid4()),
            replace(
                dataset,
                rows=(replace(dataset.rows[0], source_line_id=uuid4()),)
                + dataset.rows[1:],
            ),
            replace(
                dataset,
                rows=(replace(dataset.rows[0], relationship_id=relationship.pk),)
                + dataset.rows[1:],
            ),
            replace(
                dataset,
                rows=(replace(dataset.rows[0], employee_id=uuid4()),)
                + dataset.rows[1:],
            ),
        ):
            with self.subTest(changed=changed), self.assertRaises(PermissionDenied):
                self.prepare(changed)

    def test_permission_membership_and_scope_removal_are_enforced(self):
        membership = OrganizationMembership.objects.get(
            user=self.actor, organization=self.organization
        )
        membership.status = "suspended"
        membership.save(update_fields=["status"])
        with self.assertRaises(PermissionDenied):
            self.prepare()
        membership.status = "active"
        membership.save(update_fields=["status"])
        membership.scope_grants.all().delete()
        with self.assertRaises(PermissionDenied):
            self.prepare()

    def test_control_totals_missing_extra_or_mismatched_remain_open(self):
        dataset = self.dataset()
        first = dataset.expected_totals[0]
        for totals in (
            (replace(first, amount=Decimal("1.00")),) + dataset.expected_totals[1:],
            dataset.expected_totals[1:],
            dataset.expected_totals + (replace(first, component_id=uuid4()),),
        ):
            with self.subTest(totals=totals):
                report = self.prepare(replace(dataset, expected_totals=totals))
                self.assertFalse(report["candidate_validation_passed"])

    def test_role_label_does_not_replace_explicit_payroll_permission(self):
        membership = OrganizationMembership.objects.get(
            user=self.actor, organization=self.organization
        )
        membership.role_definition.permissions.remove(
            *membership.role_definition.permissions.filter(
                code=BusinessPermissionCode.PAYROLL_RESULTS_VIEW
            )
        )
        with self.assertRaises(PermissionDenied):
            self.prepare()

    def test_duplicate_source_ids_lines_or_total_keys_are_rejected(self):
        dataset = self.dataset()
        for changed in (
            replace(dataset, rows=(dataset.rows[0],) + dataset.rows[:-1]),
            replace(
                dataset,
                rows=(replace(dataset.rows[0], source_id="new"),) + dataset.rows[:-1],
            ),
            replace(
                dataset,
                expected_totals=dataset.expected_totals + dataset.expected_totals[:1],
            ),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                self.prepare(changed)

    def test_ambiguous_identity_is_never_resolved_by_names(self):
        employee = Employee.objects.create(
            organization=self.organization,
            employee_number="OTHER",
            first_name=self.employee.first_name,
            last_name=self.employee.last_name,
        )
        dataset = self.dataset()
        with self.assertRaises(PermissionDenied):
            self.prepare(
                replace(
                    dataset,
                    rows=tuple(
                        replace(row, employee_id=employee.pk) for row in dataset.rows
                    ),
                )
            )

    def test_malformed_approval_dates_counts_and_money_fail_closed(self):
        dataset = self.dataset()
        bad = [
            replace(dataset, approval_reference=""),
            replace(dataset, as_of=None),
            replace(dataset, year_id="inferred"),
            replace(dataset, expected_count=0),
            replace(dataset, expected_totals=()),
            replace(dataset, rows=list(dataset.rows)),
        ]
        for amount in (
            1.0,
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("0.001"),
            Decimal("1e1000000"),
        ):
            bad.append(
                replace(
                    dataset,
                    rows=(replace(dataset.rows[0], amount=amount),) + dataset.rows[1:],
                )
            )
        for changed in bad:
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                self.prepare(changed)

    def test_existing_target_without_identity_link_is_not_silently_rewritten(self):
        line = self.lines[0]
        PayrollCumulativeState.objects.create(
            organization=self.organization,
            year=self.year,
            employee=self.employee,
            work_relationship=None,
            component=line.component,
            component_kind=line.component_kind,
            state_version=1,
            source_run=self.run,
            source_line=line,
            source_version=self.run.calculation_digest,
            effective_on=self.period.ends_on,
            delta=line.amount,
            balance=line.amount,
        )
        before = list(PayrollCumulativeState.objects.values())
        report = self.prepare()
        self.assertEqual(report["exception_count"], 1)
        self.assertIn(
            "EXISTING_TARGET_REQUIRES_RECONCILIATION", report["exceptions"][0]["errors"]
        )
        self.assertEqual(list(PayrollCumulativeState.objects.values()), before)
        self.assertEqual(PayrollResultLine.objects.filter(run=self.run).count(), 6)
