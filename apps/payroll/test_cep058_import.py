"""Synthetic external openings, native YTD continuation and preserved source authority."""

from copy import deepcopy
from datetime import date
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from apps.workforce.person_services import create_person, create_work_relationship
from scripts.cep057_058_package import read_csv

from . import test_cep025_cumulative as fixtures
from .cumulative_services import (
    approve_payroll_year,
    create_payroll_year_draft,
    cumulative_balances,
    record_cumulative_for_run,
)
from .models import (
    PayrollComponent,
    PayrollCumulativeState,
    PayrollPeriod,
    PayrollResultLine,
    PayrollRunEmployee,
)
from .opening_import import import_payroll_opening, reverse_payroll_opening
from .services import create_component

PACKAGE = (
    Path(__file__).resolve().parents[2]
    / "docs/governance/cep/supporting/synthetic-dev-v2"
)


class PayrollOpeningImportTests(TestCase):
    _run = fixtures.OperationalCumulativeTests._run
    _lines = fixtures.OperationalCumulativeTests._lines

    def setUp(self):
        fixtures.OperationalCumulativeTests.setUp(self)
        person = create_person(
            organization=self.organization,
            actor=self.actor,
            first_name="Synthetic",
            last_name="Opening",
        )
        self.relationship = create_work_relationship(
            organization=self.organization,
            actor=self.actor,
            person=person,
            employee_number="CEP025",
            effective_start=date(2025, 1, 1),
            legacy_employee=self.employee,
        )
        for version in (1, 2):
            year = create_payroll_year_draft(
                organization=self.organization,
                actor=self.actor,
                code="DEV-PY-2026-A",
                starts_on=date(2026, 1, 1),
                ends_on=date(2026, 12, 31),
                reason=f"Synthetic fixture v{version}",
            )
        self.year = approve_payroll_year(
            organization=self.organization, actor=self.actor, year=year
        )
        self.rows = [
            r
            for r in read_csv(PACKAGE, "CEP058_PAYROLL_YTD_SOURCE_SYNTHETIC.csv")
            if r["source_employee_key"] == "DEV-HR-004"
        ]
        self.ids = {
            "DEV-HR-004": {
                "employee_id": str(self.employee.pk),
                "relationship_id": str(self.relationship.pk),
            }
        }
        self.dev_components = {}
        for c in read_csv(PACKAGE, "CEP058_COMPONENT_CROSSWALK_SYNTHETIC.csv"):
            kind = c["approved_operational_kind"].lower()
            obj = create_component(
                organization=self.organization,
                actor=self.actor,
                code=c["target_component_code"],
                name="Synthetic",
                kind=kind,
                net_effect="subtract"
                if kind == "deduction"
                else ("none" if kind == "employer" else "add"),
            )
            self.dev_components[obj.code] = obj.pk
        self.totals = {
            r["external_component_key"]: D(r["signed_amount"])
            for r in self.rows
            if r["included_in_opening"] == "YES"
        }

    def execute(self, **changes):
        return import_payroll_opening(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "year": self.year,
                    "rows": self.rows,
                    "identities": self.ids,
                    "components": self.dev_components,
                    "totals": self.totals,
                }
                | changes
            )
        )

    def test_source_target_counts_controls_and_retry(self):
        first = self.execute()
        retry = self.execute()
        self.assertEqual(
            (first["source_count"], first["included_count"], first["excluded_count"]),
            (9, 8, 1),
        )
        self.assertEqual(first["mapping"], retry["mapping"])
        self.assertEqual(retry["created"], 0)
        self.assertEqual(
            sum(s.delta for s in PayrollCumulativeState.objects.all()),
            sum(self.totals.values()),
        )
        self.assertTrue(
            all(
                s.source_run_id is None and s.source_line_id is None
                for s in PayrollCumulativeState.objects.all()
            )
        )

    def test_correction_retains_excluded_predecessor_exactly_once(self):
        self.execute()
        state = PayrollCumulativeState.objects.get(component__code="DEV_OVERTIME")
        self.assertEqual(state.delta, D(238000000))
        self.assertEqual(
            state.opening_evidence["excluded_lineage"][0]["signed_amount"], "188000000"
        )
        self.assertEqual(
            state.opening_evidence["source"]["correction_reference"],
            "DEV-PAY-CORR-0001",
        )

    def test_broken_replacement_is_atomic_exception(self):
        rows = deepcopy(self.rows)
        rows[-1]["replacement_reference"] = "missing"
        with self.assertRaises(ValidationError):
            self.execute(rows=rows)
        self.assertFalse(PayrollCumulativeState.objects.exists())

    def test_control_mismatch_never_writes(self):
        with self.assertRaises(ValidationError):
            self.execute(totals={})
        self.assertFalse(PayrollCumulativeState.objects.exists())

    def test_changed_evidence_same_source_rejected(self):
        self.execute()
        rows = deepcopy(self.rows)
        rows[0]["evidence_reference"] = "different"
        with self.assertRaises(ValidationError):
            self.execute(rows=rows)
        self.assertEqual(PayrollCumulativeState.objects.count(), 8)

    def test_cross_tenant_identity_denied(self):
        ids = deepcopy(self.ids)
        ids["DEV-HR-004"]["relationship_id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(PermissionDenied):
            self.execute(identities=ids)

    def test_inactive_membership_denied(self):
        self.organization.memberships.filter(user=self.actor).update(status="inactive")
        with self.assertRaises(PermissionDenied):
            self.execute()

    @override_settings(SETTINGS_MODULE="config.settings.production")
    def test_production_denied(self):
        with self.assertRaises(PermissionDenied):
            self.execute()

    def test_wrong_year_binding_rejected(self):
        from .models import PayrollYearInterval

        PayrollYearInterval.objects.filter(pk=self.year.pk).update(version=3)
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(PayrollCumulativeState.objects.exists())

    def test_retry_rechecks_current_year_binding(self):
        from .models import PayrollYearInterval

        self.execute()
        PayrollYearInterval.objects.filter(pk=self.year.pk).update(status="superseded")
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertEqual(PayrollCumulativeState.objects.count(), 8)

    def test_currency_binding_rejected(self):
        from apps.organizations.models import OrganizationSettings

        OrganizationSettings.objects.filter(organization=self.organization).update(
            currency="USD"
        )
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(PayrollCumulativeState.objects.exists())

    def test_failure_after_first_insert_rolls_back_then_recovers(self):
        from .opening_import import _audit

        def fail(state, actor):
            _audit(state, actor)
            raise RuntimeError("Injected failure after insert")

        with (
            patch("apps.payroll.opening_import._audit", side_effect=fail),
            self.assertRaises(RuntimeError),
        ):
            self.execute()
        self.assertFalse(PayrollCumulativeState.objects.exists())
        self.assertEqual(self.execute()["created"], 8)

    def test_compensating_rollback_retains_history_and_retry_does_not_reactivate(self):
        self.execute()
        originals = list(PayrollCumulativeState.objects.all())
        for _ in range(2):
            inverse = reverse_payroll_opening(
                organization=self.organization, actor=self.actor, entries=originals
            )
            self.assertTrue(all(s.balance == 0 for s in inverse))
        self.assertEqual(PayrollCumulativeState.objects.count(), 16)
        with self.assertRaises(ValidationError):
            self.execute()

    def test_immutable_history_and_database_origin_guard(self):
        self.execute()
        state = PayrollCumulativeState.objects.first()
        with self.assertRaises(ValidationError):
            state.delete()
        with self.assertRaises(ValidationError):
            PayrollCumulativeState.objects.filter(pk=state.pk).update(delta=0)
        state.pk = None
        state.opening_key = None
        with transaction.atomic(), self.assertRaises(IntegrityError):
            # Deliberately bypass model validation to prove the database origin constraint.
            PayrollCumulativeState.objects.bulk_create([state])

    def native_line(self, starts_on=date(2026, 10, 1)):
        self.execute()
        PayrollPeriod.objects.filter(pk=self.period.pk).update(starts_on=starts_on)
        component = PayrollComponent.objects.get(pk=self.dev_components["DEV_BASE_PAY"])
        result = PayrollRunEmployee.objects.get(run=self.run, employee=self.employee)
        line = PayrollResultLine.objects.create(
            organization=self.organization,
            run=self.run,
            run_employee=result,
            component=component,
            sequence=20,
            component_kind=component.kind,
            unrounded_amount=D(100),
            amount=D(100),
            explanation={"synthetic": True},
        )
        return line

    def test_native_continuation_uses_existing_balance_and_is_idempotent(self):
        line = self.native_line()
        record_cumulative_for_run(
            organization=self.organization, actor=self.actor, run=self.run
        )
        state = PayrollCumulativeState.objects.get(source_line=line)
        self.assertEqual(state.balance, self.totals["DEV_BASE_PAY"] + 100)
        self.assertEqual(state.state_version, 2)
        self.assertEqual(
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            ),
            0,
        )

    def test_native_overlap_is_rejected_atomically(self):
        self.native_line(starts_on=date(2026, 9, 1))
        with self.assertRaises(ValidationError):
            record_cumulative_for_run(
                organization=self.organization, actor=self.actor, run=self.run
            )
        self.assertEqual(PayrollCumulativeState.objects.count(), 8)

    def test_reset_year_does_not_include_previous_openings(self):
        self.execute()
        year = approve_payroll_year(
            organization=self.organization,
            actor=self.actor,
            year=create_payroll_year_draft(
                organization=self.organization,
                actor=self.actor,
                code="DEV-NEXT-YEAR",
                starts_on=date(2027, 1, 1),
                ends_on=date(2027, 12, 31),
                reason="Explicit synthetic next interval",
            ),
        )
        self.assertEqual(
            cumulative_balances(
                organization=self.organization,
                actor=self.actor,
                year=year,
                employee=self.employee,
            ),
            (),
        )
