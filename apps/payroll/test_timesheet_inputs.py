"""PD-WC-D02 approved revision selection, explicit unit mapping and source integrity."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.organizations.models import AuthorizationScopeType
from apps.payroll import test_p7_s13_s22_core_payroll as core
from apps.payroll.forms import InputForm
from apps.payroll.models import CalculationMethod, ComponentKind, NetEffect, RateSource
from apps.payroll.services import activate_rule, create_rule, lock_run_inputs
from apps.payroll.timesheet_inputs import eligible_timesheets, record_timesheet_input
from apps.projects.models import Project
from apps.timekeeping.models import Timesheet, TimesheetEntry, TimesheetReview


class TimesheetInputTests(TestCase):
    # Reuse the accepted authorization/monetary fixture, not unrelated test methods.
    setUp = core.CorePayrollTests.setUp
    _member = core.CorePayrollTests._member
    _activate_monetary_policies = core.CorePayrollTests._activate_monetary_policies
    _component = core.CorePayrollTests._component
    _run = core.CorePayrollTests._run

    def source(self, *, minutes=120, unit="hour"):
        project = Project.objects.create(
            organization=self.organization, code="TS-PAY", name="Test project"
        )
        sheet = Timesheet.objects.create(
            organization=self.organization,
            employee=self.employee,
            period_start=self.period.starts_on,
            period_end=self.period.ends_on,
            declared_minutes=minutes,
            prepared_by=self.actor,
        )
        TimesheetEntry.objects.create(
            organization=self.organization,
            timesheet=sheet,
            project=project,
            work_date=self.period.ends_on,
            minutes=minutes,
        )
        Timesheet.objects.filter(pk=sheet.pk).update(state="approved")
        sheet.refresh_from_db()
        TimesheetReview.objects.create(
            organization=self.organization,
            timesheet=sheet,
            decision="approved",
            reason="Explicit independent source evidence",
            reviewer=self.owner,
        )
        component = self._component("TS", ComponentKind.EARNING, NetEffect.ADD)
        rule = create_rule(
            organization=self.organization,
            actor=self.actor,
            component=component,
            code="TS-RULE",
            name="Approved minutes",
            sequence=10,
            method=CalculationMethod.QUANTITY_TIMES_RATE,
            rate_source=RateSource.EMPLOYMENT,
            effective_from=date(2026, 1, 1),
            source_reference="PD-WC-D02 test mapping",
            evidence={"timesheet_input_mapping": {"version": 1, "quantity_unit": unit}},
        )
        activate_rule(organization=self.organization, actor=self.actor, rule=rule)
        return sheet, rule, self._run()

    def test_source_derives_quantity_identity_and_provenance_then_locks(self):
        sheet, rule, run = self.source()
        item = record_timesheet_input(
            organization=self.organization,
            actor=self.actor,
            run=run,
            timesheet=sheet,
            rule=rule,
        )
        self.assertEqual(item.quantity, Decimal(2))
        self.assertEqual(item.employee_id, sheet.employee_id)
        self.assertEqual(item.source_reference, str(sheet.pk))
        self.assertEqual(item.source_version, "1")
        self.assertEqual(item.source_status, "approved")
        self.assertEqual(item.source_payload["declared_minutes"], 120)
        self.assertEqual(len(item.source_payload["digest"]), 64)
        retry = record_timesheet_input(
            organization=self.organization,
            actor=self.actor,
            run=run,
            timesheet=sheet,
            rule=rule,
        )
        self.assertEqual(item.pk, retry.pk)
        lock_run_inputs(organization=self.organization, actor=self.actor, run=run)

    def test_selector_has_no_manual_source_or_quantity_fields(self):
        sheet, _rule, run = self.source()
        form = InputForm(organization=self.organization, actor=self.actor, run=run)
        self.assertEqual(set(form.fields), {"timesheet", "rule"})
        self.assertEqual(list(form.fields["timesheet"].queryset), [sheet])
        denied = InputForm(organization=self.organization, actor=self.denied, run=run)
        self.assertFalse(denied.fields["timesheet"].queryset.exists())

    def test_nonapproved_or_out_of_period_source_denied(self):
        sheet, rule, run = self.source()
        for changes in [
            {"state": "draft"},
            {"state": "approved", "period_start": date(2026, 9, 22)},
        ]:
            Timesheet.objects.filter(pk=sheet.pk).update(**changes)
            self.assertFalse(
                eligible_timesheets(
                    organization=self.organization, actor=self.actor, run=run
                ).exists()
            )
            with self.assertRaises(ValidationError):
                record_timesheet_input(
                    organization=self.organization,
                    actor=self.actor,
                    run=run,
                    timesheet=sheet,
                    rule=rule,
                )

    def test_missing_mapping_or_inexact_unit_conversion_fails_closed(self):
        sheet, rule, run = self.source(minutes=1)
        with self.assertRaises(ValidationError):
            record_timesheet_input(
                organization=self.organization,
                actor=self.actor,
                run=run,
                timesheet=sheet,
                rule=rule,
            )
        type(rule).objects.filter(pk=rule.pk).update(evidence={})
        with self.assertRaises(ValidationError):
            record_timesheet_input(
                organization=self.organization,
                actor=self.actor,
                run=run,
                timesheet=sheet,
                rule=rule,
            )

    def test_unauthorized_actor_denied_and_source_tamper_prevents_lock(self):
        sheet, rule, run = self.source()
        with self.assertRaises(PermissionDenied):
            record_timesheet_input(
                organization=self.organization,
                actor=self.denied,
                run=run,
                timesheet=sheet,
                rule=rule,
            )
        item = record_timesheet_input(
            organization=self.organization,
            actor=self.actor,
            run=run,
            timesheet=sheet,
            rule=rule,
        )
        item.source_payload["declared_minutes"] = 999
        item.save()
        with self.assertRaises(ValidationError):
            lock_run_inputs(organization=self.organization, actor=self.actor, run=run)

    def test_source_selector_and_service_reject_unrelated_project_scope(self):
        sheet, rule, run = self.source()
        other = Project.objects.create(
            organization=self.organization, code="OUTSIDE", name="Outside scope"
        )
        membership = self.organization.memberships.get(user=self.actor)
        membership.scope_grants.update(
            scope_type=AuthorizationScopeType.PROJECT, project=other
        )
        self.assertFalse(
            eligible_timesheets(
                organization=self.organization, actor=self.actor, run=run
            ).exists()
        )
        with self.assertRaises(PermissionDenied):
            record_timesheet_input(
                organization=self.organization,
                actor=self.actor,
                run=run,
                timesheet=sheet,
                rule=rule,
            )
