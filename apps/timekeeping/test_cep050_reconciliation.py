import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.organizations.catalog_bootstrap import synchronize_authorization_catalog
from apps.organizations.models import BusinessPermissionCode, OrganizationSettings
from apps.reporting import test_p10_s07_s13 as reporting_baseline
from apps.reporting.catalog_bootstrap import synchronize_metric_catalogue
from apps.reporting.models import ReconciliationRun
from apps.reporting.reconciliation import (
    PairData,
    SideData,
    execute_reconciliation,
    reconciliation_drillthrough,
    reconciliation_runs,
    record_exception_event,
    replay_reconciliation,
    review_reconciliation_run,
)
from apps.workforce.models import Employee, Person, WorkRelationship

from . import test_cep024_scope as scope_baseline
from .models import AttendanceRecord, Timesheet, TimesheetEntry, WorkCalendar
from .reconciliation import PAIR, compare, reconcile_attendance_timesheet
from .services import (
    add_timesheet_entry,
    capture_attendance,
    create_timesheet,
    finalize_attendance,
    request_attendance_correction,
    review_attendance_correction,
    review_timesheet,
    submit_timesheet,
)


class ObservationUnitTests(SimpleTestCase):
    def test_offsetting_daily_differences_do_not_disappear_in_a_total(self):
        data = PairData(
            SideData(
                "Attendance",
                "a",
                "ready",
                {"observed_seconds": {"day1": "3600", "day2": "1800"}},
                {},
            ),
            SideData(
                "Timesheet",
                "t",
                "ready",
                {"observed_seconds": {"day1": "1800", "day2": "3600"}},
                {},
            ),
            "observed_seconds",
        )
        outcome, differences, tolerance, _ = compare(data)
        self.assertEqual(outcome, "mismatch")
        self.assertEqual(
            [row["difference_seconds"] for row in differences["observations"]],
            ["1800", "-1800"],
        )
        self.assertFalse(tolerance["applied"])
        data = replace(data, left=replace(data.left, readiness="unknown"))
        self.assertEqual(compare(data)[0], "unknown")


class TimeReconciliationTests(TestCase):
    _grant = reporting_baseline.P10S07S13AcceptanceTests.__dict__["_grant"]

    @classmethod
    def setUpTestData(cls):
        synchronize_authorization_catalog(using="default")
        synchronize_metric_catalogue(using="default")
        reporting_baseline.P10S07S13AcceptanceTests.setUpTestData.__func__(cls)
        cls.corrector = User.objects.create_user(username="time050-corrector")
        cls._grant(cls.corrector, set(BusinessPermissionCode.values))
        OrganizationSettings.objects.create(
            organization=cls.organization, timezone="Asia/Tehran"
        )
        cls.employee = Employee.objects.create(
            organization=cls.organization,
            employee_number="TIME050",
            first_name="Fixture",
            last_name="Worker",
        )
        cls.person = Person.objects.create(
            organization=cls.organization, first_name="Fixture", last_name="Worker"
        )
        cls.relationship = WorkRelationship.objects.create(
            organization=cls.organization,
            person=cls.person,
            legacy_employee=cls.employee,
            employee_number=cls.employee.employee_number,
            effective_start=date(2026, 1, 1),
        )
        cls.calendar = WorkCalendar.objects.create(
            organization=cls.organization,
            code="CEP050",
            name="Fixture calendar",
            timezone="Asia/Tehran",
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
            created_by=cls.user,
        )
        cls.start = datetime(2026, 2, 1, 8, tzinfo=ZoneInfo("Asia/Tehran"))
        cls.attendance = capture_attendance(
            organization=cls.organization,
            actor=cls.user,
            employee=cls.employee,
            calendar=cls.calendar,
            project=cls.project,
            work_date=cls.start.date(),
            check_in_at=cls.start,
            check_out_at=cls.start + timedelta(hours=1),
        )
        cls.attendance = finalize_attendance(
            organization=cls.organization, actor=cls.reviewer, attendance=cls.attendance
        )
        cls.sheet = cls._sheet(50)

    @classmethod
    def _sheet(cls, minutes, supersedes=None):
        sheet = create_timesheet(
            organization=cls.organization,
            actor=cls.user,
            employee=cls.employee,
            period_start=cls.start.date(),
            period_end=cls.start.date(),
            declared_minutes=minutes,
            supersedes=supersedes,
            correction_reason="native correction" if supersedes else "",
        )
        add_timesheet_entry(
            organization=cls.organization,
            actor=cls.user,
            timesheet=sheet,
            work_date=cls.start.date(),
            project=cls.project,
            minutes=minutes,
        )
        submit_timesheet(organization=cls.organization, actor=cls.user, timesheet=sheet)
        review_timesheet(
            organization=cls.organization,
            actor=cls.reviewer,
            timesheet=sheet,
            approve=True,
            reason="Native source review",
        )
        sheet.refresh_from_db()
        return sheet

    def _run(self, key="time050", **kwargs):
        return reconcile_attendance_timesheet(
            organization=self.organization,
            actor=self.user,
            relationship=self.relationship,
            timesheet=kwargs.pop("timesheet", self.sheet),
            idempotency_key=key,
            **kwargs,
        )

    def _evidence(self, scenario, run):
        print(
            "CEP050 RECON "
            + json.dumps(
                {
                    "scenario": scenario,
                    "run_id": str(run.pk),
                    "replaces": str(run.replaces_id),
                    "source_watermark": run.source_watermark,
                    "outcome": run.tie_out.outcome,
                    "difference": run.tie_out.difference,
                    "tolerance": run.tie_out.tolerance_result,
                    "source_versions": [
                        side.source_manifest
                        for side in run.side_snapshots.order_by("side")
                    ],
                    "exceptions": run.exceptions.count(),
                    "source_mutations_by_reconciliation": 0,
                },
                sort_keys=True,
            )
        )

    def test_mismatch_snapshots_review_and_source_immutability(self):
        before = (
            list(AttendanceRecord.objects.values()),
            list(Timesheet.objects.values()),
            list(TimesheetEntry.objects.values()),
        )
        run = self._run(project=self.project)
        from apps.reporting.project_closeout import _family_queryset

        self.assertFalse(
            _family_queryset(
                model_label="reporting.ReconciliationRun",
                project_lookup="project",
                organization=self.organization,
                project=self.project,
            )
            .filter(pk=run.pk)
            .exists()
        )
        self.assertEqual(run.tie_out.outcome, "mismatch")
        self.assertEqual(
            run.tie_out.difference["observations"][0]["difference_seconds"], "600"
        )
        self.assertFalse(run.tie_out.tolerance_result["applied"])
        self.assertEqual(
            before,
            (
                list(AttendanceRecord.objects.values()),
                list(Timesheet.objects.values()),
                list(TimesheetEntry.objects.values()),
            ),
        )
        for side in run.side_snapshots.all():
            self.assertEqual(
                side.source_manifest["context"]["relationship_id"],
                str(self.relationship.pk),
            )
            self.assertEqual(len(side.source_manifest["records"][0]["version"]), 64)
            side.value = {}
            with self.assertRaises(ValidationError):
                side.save()
        with self.assertRaises(PermissionDenied):
            review_reconciliation_run(
                run=run, reviewer=self.user, decision="accepted", reason="self"
            )
        review = review_reconciliation_run(
            run=run,
            reviewer=self.reviewer,
            decision="accepted",
            reason="Observed source difference only",
        )
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertTrue(AuditEvent.objects.filter(entity_id=str(review.pk)).exists())
        self._evidence("native_observed_mismatch_independent_review", run)

    def test_native_corrections_successor_and_exception_history(self):
        first = self._run()
        source_hash = first.source_watermark
        correction = request_attendance_correction(
            organization=self.organization,
            requester=self.corrector,
            attendance=self.attendance,
            reason="Correct native interval",
            replacement_values={"check_out_at": self.start + timedelta(minutes=50)},
        )
        correction = review_attendance_correction(
            organization=self.organization,
            approver=self.reviewer,
            correction_request=correction,
            approve=True,
            review_reason="Approve native correction",
        )
        exception = first.exceptions.get()
        record_exception_event(
            exception=exception,
            actor=self.user,
            action="disposition",
            reason="Native correction approved",
            operation_key="native-correction",
            correction_reference={
                "model": "timekeeping.AttendanceCorrectionRequest",
                "id": str(correction.pk),
            },
        )
        with self.assertRaises(PermissionDenied):
            record_exception_event(
                exception=exception,
                actor=self.user,
                action="close",
                reason="self close",
                operation_key="close-denied",
            )
        record_exception_event(
            exception=exception,
            actor=self.reviewer,
            action="close",
            reason="Independent review",
            operation_key="closed",
        )
        second = self._run(key="successor", replaces=first)
        self.assertEqual(second.tie_out.outcome, "matched_exact")
        self.assertEqual(second.replaces_id, first.pk)
        first.refresh_from_db()
        self.assertEqual(first.source_watermark, source_hash)
        self.assertEqual(first.tie_out.outcome, "mismatch")
        self.assertEqual(first.exceptions.get().events.count(), 2)
        replay = replay_reconciliation(
            original_run=first, actor=self.user, idempotency_key="replay"
        )
        self.assertEqual(replay.outcome, "mismatched")
        self.assertEqual(first.side_snapshots.count(), 2)
        self._evidence("approved_attendance_correction_successor", second)

    def test_timesheet_revision_correction_link_and_prior_versions(self):
        first = self._run()
        revision = self._sheet(60, supersedes=self.sheet)
        record_exception_event(
            exception=first.exceptions.get(),
            actor=self.user,
            action="disposition",
            reason="Approved native revision",
            operation_key="revision",
            correction_reference={
                "model": "timekeeping.Timesheet",
                "id": str(revision.pk),
            },
        )
        second = self._run("revision-run", timesheet=revision, replaces=first)
        self.assertEqual(second.tie_out.outcome, "matched_exact")
        self.assertEqual(
            first.side_snapshots.get(side="right").source_manifest["sheet"]["id"],
            str(self.sheet.pk),
        )
        self.assertEqual(
            second.side_snapshots.get(side="right").source_manifest["sheet"][
                "supersedes_id"
            ],
            str(self.sheet.pk),
        )

        self._evidence("approved_timesheet_revision_successor", second)

    def test_missing_context_identity_policy_and_correction_fail_closed(self):
        with self.assertRaises(ValidationError):
            execute_reconciliation(
                organization=self.organization,
                actor=self.user,
                pair_code=PAIR,
                idempotency_key="no-context",
            )
        original_employee = self.relationship.legacy_employee_id
        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            legacy_employee=None
        )
        with self.assertRaises(ValidationError):
            self._run("unlinked")
        WorkRelationship.objects.filter(pk=self.relationship.pk).update(
            legacy_employee_id=original_employee
        )
        run = self._run()
        with self.assertRaises(ValidationError):
            record_exception_event(
                exception=run.exceptions.get(),
                actor=self.user,
                action="disposition",
                reason="Invalid cross-domain correction",
                operation_key="invalid",
                correction_reference={"model": "payroll.Run", "id": str(self.sheet.pk)},
            )
        Timesheet.objects.filter(pk=self.sheet.pk).update(state="draft")
        incomplete = self._run("unapproved")
        self.assertEqual(incomplete.tie_out.outcome, "incomplete")
        AttendanceRecord.objects.filter(pk=self.attendance.pk).update(state="reversed")
        missing = self._run("missing")
        self.assertNotEqual(missing.tie_out.outcome, "matched_exact")
        self.assertEqual(
            missing.side_snapshots.get(side="left").value["observed_seconds"], {}
        )

    def test_idempotency_rollback_scope_and_read_paths(self):
        cutoff = timezone.now()
        first = self._run(cutoff_at=cutoff)
        self.assertEqual(self._run(cutoff_at=cutoff).pk, first.pk)
        with self.assertRaises(ValidationError):
            self._run(cutoff_at=cutoff + timedelta(seconds=1))
        before = ReconciliationRun.objects.count()
        with (
            patch(
                "apps.timekeeping.reconciliation.capture",
                side_effect=ValidationError("source failure"),
            ),
            self.assertRaises(ValidationError),
        ):
            self._run("rollback")
        self.assertEqual(before, ReconciliationRun.objects.count())
        self._grant(
            self.other,
            {
                value
                for value in BusinessPermissionCode.values
                if value.startswith("reporting.")
            },
        )
        self.assertFalse(
            reconciliation_runs(organization=self.organization, actor=self.other)
            .filter(pk=first.pk)
            .exists()
        )
        with self.assertRaises(PermissionDenied):
            reconciliation_drillthrough(
                organization=self.organization, actor=self.other, run_id=str(first.pk)
            )
        with self.assertRaises(PermissionDenied):
            reconciliation_drillthrough(
                organization=self.other_organization,
                actor=self.user,
                run_id=str(first.pk),
            )
        self.assertEqual(
            reconciliation_drillthrough(
                organization=self.organization, actor=self.user, run_id=str(first.pk)
            ),
            first,
        )


class RetainedScopeRegression(scope_baseline.Cep024TimekeepingScopeTests):
    def setUp(self):
        from apps.workflows.catalog_bootstrap import synchronize_workflow_catalog

        synchronize_authorization_catalog(using="default")
        synchronize_workflow_catalog(using="default")
        super().setUp()
