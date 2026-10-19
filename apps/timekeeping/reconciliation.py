"""SPEC-012 observations, persisted only in the existing reconciliation read model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode as Permission
from apps.organizations.models import Organization
from apps.projects.models import Project, ProjectSite
from apps.reporting.reconciliation import PairData, SideData, _hash
from apps.workforce.models import Employee, WorkRelationship

from .models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    AttendanceState,
    Timesheet,
    TimesheetEntry,
    TimesheetState,
)

PAIR = "attendance_timesheet"

if TYPE_CHECKING:
    from apps.reporting.models import ReconciliationRun


def _require(
    actor: User,
    organization: Organization,
    permission: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        message="مجوز یا دامنه منبع تطبیق کارکرد وجود ندارد.",
    )


def validate_context(
    organization: Organization,
    actor: User,
    project: Project | None,
    context: dict[str, str] | None,
) -> tuple[WorkRelationship, Timesheet]:
    if not isinstance(context, dict) or set(context) != {
        "relationship_id",
        "timesheet_id",
    }:
        raise ValidationError("رابطه کاری و نسخه کارکرد صریح الزامی است.")
    for permission in (
        Permission.EMPLOYEES_VIEW,
        Permission.ATTENDANCE_VIEW,
        Permission.TIMESHEETS_VIEW,
    ):
        _require(actor, organization, permission, project)
    try:
        relationship = WorkRelationship.objects.get(
            organization=organization, pk=context["relationship_id"]
        )
        sheet = Timesheet.objects.get(
            organization=organization, pk=context["timesheet_id"]
        )
    except (WorkRelationship.DoesNotExist, Timesheet.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("منبع تطبیق در شرکت فعال وجود ندارد.") from exc
    if (
        not relationship.legacy_employee_id
        or sheet.employee_id != relationship.legacy_employee_id
        or relationship.person.organization_id != organization.pk
        or sheet.employee.organization_id != organization.pk
        or sheet.period_start < relationship.effective_start
        or (
            relationship.effective_end and sheet.period_end > relationship.effective_end
        )
    ):
        raise ValidationError("پیوند صریح هویت و دوره رابطه کاری معتبر نیست.")
    return relationship, sheet


def _version(row: object, fields: tuple[str, ...]) -> dict[str, str]:
    payload = {field: str(getattr(row, field)) for field in fields}
    return {"id": str(row.pk), "version": _hash(payload), **payload}


def _grain(row: AttendanceRecord | TimesheetEntry) -> str:
    return "/".join(
        str(value or "") for value in (row.work_date, row.project_id, row.site_id)
    )


def capture(
    organization: Organization,
    actor: User,
    project: Project | None,
    cutoff: datetime,
    context: dict[str, str],
) -> PairData:
    relationship, sheet = validate_context(organization, actor, project, context)
    relationship = WorkRelationship.objects.select_for_update().get(pk=relationship.pk)
    Employee.objects.select_for_update().get(
        pk=relationship.legacy_employee_id, organization=organization
    )
    sheet = Timesheet.objects.select_for_update().get(pk=sheet.pk)
    validate_context(organization, actor, project, context)
    entries = list(
        TimesheetEntry.objects.select_for_update(of=("self",))
        .filter(timesheet=sheet)
        .select_related("project", "site", "activity")
        .order_by("pk")
    )
    attendance = list(
        AttendanceRecord.objects.select_for_update(of=("self",))
        .filter(
            organization=organization,
            employee_id=relationship.legacy_employee_id,
            work_date__range=(sheet.period_start, sheet.period_end),
        )
        .select_related("project", "site")
        .order_by("pk")
    )
    for row in [*attendance, *entries]:
        if (
            row.organization_id != organization.pk
            or (row.project_id and row.project.organization_id != organization.pk)
            or (
                row.site_id
                and (
                    row.site.organization_id != organization.pk
                    or row.site.project_id != row.project_id
                )
            )
        ):
            raise ValidationError("ابعاد منبع تطبیق ناسازگار است.")
        if isinstance(row, TimesheetEntry) and (
            not sheet.period_start <= row.work_date <= sheet.period_end
            or (
                row.activity_id
                and (
                    row.activity.organization_id != organization.pk
                    or row.activity.project_id != row.project_id
                    or row.activity.site_id != row.site_id
                )
            )
        ):
            raise ValidationError("ردیف کارکرد خارج از دامنه مصوب است.")
        if project is None or row.project_id == project.pk:
            for permission in (Permission.ATTENDANCE_VIEW, Permission.TIMESHEETS_VIEW):
                _require(actor, organization, permission, row.project, row.site)
    manifest = {
        "context": context,
        "period": [str(sheet.period_start), str(sheet.period_end)],
        "relationship": _version(
            relationship,
            (
                "person_id",
                "legacy_employee_id",
                "effective_start",
                "effective_end",
                "updated_at",
            ),
        ),
        "grain": "work_date/project/site; no activity inference",
        "basis": "observed clock interval seconds versus recorded allocation minutes times60; no payable-time policy",
    }
    left_rows, right_rows, left, right = [], [], {}, {}
    incomplete = False
    for row in attendance:
        if project is not None and row.project_id != project.pk:
            continue
        left_rows.append(
            _version(
                row,
                (
                    "work_date",
                    "project_id",
                    "site_id",
                    "check_in_at",
                    "check_out_at",
                    "state",
                    "finalized_at",
                    "updated_at",
                ),
            )
        )
        if row.state in {AttendanceState.SUPERSEDED, AttendanceState.REVERSED}:
            continue
        if (
            row.state != AttendanceState.FINALIZED
            or row.updated_at > cutoff
            or not row.finalized_at
            or row.finalized_at > cutoff
            or not row.check_out_at
        ):
            incomplete = True
            continue
        delta = row.check_out_at - row.check_in_at
        seconds = (
            Decimal(delta.days * 86400 + delta.seconds)
            + Decimal(delta.microseconds) / 1000000
        )
        if seconds <= 0:
            raise ValidationError("بازه حضور معتبر نیست.")
        key = _grain(row)
        left[key] = left.get(key, Decimal(0)) + seconds
    for row in entries:
        if project is not None and row.project_id != project.pk:
            continue
        right_rows.append(
            _version(
                row,
                (
                    "work_date",
                    "project_id",
                    "site_id",
                    "activity_id",
                    "minutes",
                    "updated_at",
                ),
            )
        )
        key = _grain(row)
        right[key] = right.get(key, Decimal(0)) + Decimal(row.minutes) * 60
    sheet_version = _version(
        sheet,
        (
            "employee_id",
            "period_start",
            "period_end",
            "revision",
            "declared_minutes",
            "state",
            "supersedes_id",
            "updated_at",
        ),
    )
    if sum(row.minutes for row in entries) != sheet.declared_minutes:
        raise ValidationError("جمع ردیف‌های نسخه کارکرد با منبع برابر نیست.")
    reviews = list(
        sheet.reviews.filter(organization=organization, decision="approved").order_by(
            "created_at", "pk"
        )
    )
    sheet_version["review_versions"] = [
        _version(review, ("decision", "reviewer_id", "created_at"))
        for review in reviews
    ]
    eligible_sheet = (
        sheet.state == TimesheetState.APPROVED
        and sheet.updated_at <= cutoff
        and bool(reviews)
        and reviews[-1].created_at <= cutoff
    )
    return PairData(
        SideData(
            "Timekeeping / Attendance",
            "timekeeping.AttendanceRecord",
            "incomplete" if incomplete else "ready" if left else "unknown",
            {"observed_seconds": {k: str(v) for k, v in sorted(left.items())}},
            {**manifest, "records": left_rows},
        ),
        SideData(
            "Timekeeping / Timesheet",
            "timekeeping.Timesheet",
            "ready"
            if eligible_sheet and right
            else "incomplete"
            if not eligible_sheet
            else "unknown",
            {"observed_seconds": {k: str(v) for k, v in sorted(right.items())}},
            {**manifest, "sheet": sheet_version, "records": right_rows},
        ),
        "observed_seconds",
        unit="seconds",
    )


def compare(
    data: PairData,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    left = data.left.value["observed_seconds"]
    right = data.right.value["observed_seconds"]
    rows = [
        {
            "grain": key,
            "attendance_seconds": left.get(key),
            "timesheet_seconds": right.get(key),
            "difference_seconds": str(Decimal(left[key]) - Decimal(right[key]))
            if key in left and key in right
            else None,
        }
        for key in sorted(left.keys() | right.keys())
    ]
    readiness = {data.left.readiness, data.right.readiness}
    outcome = (
        "incomplete"
        if "incomplete" in readiness
        else "unknown"
        if "unknown" in readiness
        else "matched_exact"
        if rows
        and all(
            row["difference_seconds"] is not None
            and Decimal(row["difference_seconds"]) == 0
            for row in rows
        )
        else "mismatch"
    )
    return (
        outcome,
        {"observations": rows},
        {
            "kind": "source_policy",
            "status": "unconfigured",
            "applied": False,
            "difference_visible": True,
            "reason": "no_approved_tolerance",
        },
        {
            "material": outcome != "matched_exact",
            "reason": "observed_difference_requires_review"
            if outcome != "matched_exact"
            else "observed_equality",
        },
    )


def guard_run(
    run: ReconciliationRun,
    actor: User,
    *,
    review: bool = False,
    correction_reference: dict[str, object] | None = None,
) -> None:
    """Apply native object scope to every generic path exposing this workforce pair."""
    if run.pair_version.definition.code != PAIR:
        return
    sides = list(run.side_snapshots.order_by("side"))
    if len(sides) != 2 or sides[0].source_manifest.get("context") != sides[
        1
    ].source_manifest.get("context"):
        raise ValidationError("شاهد نسخه‌دار تطبیق ناقص است.")
    context = sides[0].source_manifest["context"]
    validate_context(run.organization, actor, run.project, context)
    if review:
        for permission in (Permission.ATTENDANCE_REVIEW, Permission.TIMESHEETS_REVIEW):
            _require(actor, run.organization, permission, run.project)
    for side in sides:
        for record in side.source_manifest["records"]:
            model = AttendanceRecord if side.side == "left" else TimesheetEntry
            row = (
                model.objects.select_related("project", "site")
                .filter(organization=run.organization, pk=record["id"])
                .first()
            )
            if row is None:
                raise PermissionDenied("شاهد منبع در دامنه فعال نیست.")
            for permission in (Permission.ATTENDANCE_VIEW, Permission.TIMESHEETS_VIEW):
                _require(actor, run.organization, permission, row.project, row.site)
            if review:
                _require(
                    actor,
                    run.organization,
                    Permission.ATTENDANCE_REVIEW,
                    row.project,
                    row.site,
                )
                _require(
                    actor,
                    run.organization,
                    Permission.TIMESHEETS_REVIEW,
                    row.project,
                    row.site,
                )
    if correction_reference:
        if set(correction_reference) != {"model", "id"}:
            raise ValidationError("پیوند اصلاح باید شناسه صریح منبع باشد.")
        if correction_reference["model"] == "timekeeping.AttendanceCorrectionRequest":
            request = AttendanceCorrectionRequest.objects.filter(
                organization=run.organization,
                pk=correction_reference["id"],
                status="approved",
                adjustment__isnull=False,
            ).first()
            ids = {
                row["id"]
                for side in sides
                if side.side == "left"
                for row in side.source_manifest["records"]
            }
            valid = request is not None and str(request.attendance_id) in ids
        elif correction_reference["model"] == "timekeeping.Timesheet":
            sheet = Timesheet.objects.filter(
                organization=run.organization,
                pk=correction_reference["id"],
                state=TimesheetState.APPROVED,
            ).first()
            valid = (
                sheet is not None
                and str(sheet.supersedes_id) == context["timesheet_id"]
                and str(sheet.employee_id)
                == sides[0].source_manifest["relationship"]["legacy_employee_id"]
                and [str(sheet.period_start), str(sheet.period_end)]
                == sides[0].source_manifest["period"]
                and sheet.reviews.filter(
                    organization=run.organization, decision="approved"
                ).exists()
            )
        else:
            valid = False
        if not valid:
            raise ValidationError("پیوند به اصلاح مصوب همین منبع الزامی است.")


@transaction.atomic
def reconcile_attendance_timesheet(
    *,
    organization: Organization,
    actor: User,
    relationship: WorkRelationship,
    timesheet: Timesheet,
    idempotency_key: str,
    project: Project | None = None,
    cutoff_at: datetime | None = None,
    replaces: ReconciliationRun | None = None,
) -> ReconciliationRun:
    from apps.reporting.reconciliation import execute_reconciliation

    return execute_reconciliation(
        organization=organization,
        actor=actor,
        pair_code=PAIR,
        comparison_context={
            "relationship_id": str(relationship.pk),
            "timesheet_id": str(timesheet.pk),
        },
        project=project,
        cutoff_at=cutoff_at,
        idempotency_key=idempotency_key,
        replaces=replaces,
    )
