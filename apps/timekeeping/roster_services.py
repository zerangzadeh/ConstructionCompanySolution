"""Effective planned shift history, independent of actual attendance and Payroll."""

from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import EmployeeProjectAssignment, WorkRelationship

from .models import RosterSlot, RosterVersion, ShiftDefinition, WorkCalendar


def _require(
    *,
    actor: User,
    organization: Organization,
    code: BusinessPermissionCode,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    organization = Organization.objects.get(pk=organization.pk)
    require_business_permission(
        user=actor,
        organization=organization,
        permission=code,
        project=project,
        site=site,
        message="برنامه مجاز یافت نشد.",
    )


def _shift(
    *, shift: ShiftDefinition, organization: Organization, start: date, end: date
) -> ShiftDefinition:
    try:
        item = (
            ShiftDefinition.objects.select_for_update()
            .select_related("calendar")
            .get(pk=shift.pk, organization=organization, is_active=True)
        )
    except ShiftDefinition.DoesNotExist as exc:
        raise PermissionDenied("شیفت مجاز یافت نشد.") from exc
    item.calendar = WorkCalendar.objects.select_for_update().get(
        pk=item.calendar_id, organization=organization
    )
    if not item.calendar.is_active or item.calendar.archived_at:
        raise ValidationError("تقویم فعال منبع لازم است.")
    if (
        item.effective_from > start
        or (item.effective_to and item.effective_to < end)
        or item.calendar.effective_from > start
        or (item.calendar.effective_to and item.calendar.effective_to < end)
    ):
        raise ValidationError("شیفت و تقویم باید در بازه برنامه معتبر باشند.")
    return item


def _snapshot(shift: ShiftDefinition) -> dict[str, Any]:
    return {
        "id": str(shift.pk),
        "code": shift.code,
        "name": shift.name,
        "starts_at": shift.starts_at.isoformat(),
        "ends_at": shift.ends_at.isoformat(),
        "crosses_midnight": shift.crosses_midnight,
        "effective_from": shift.effective_from.isoformat(),
        "effective_to": shift.effective_to.isoformat() if shift.effective_to else None,
        "source_updated_at": shift.updated_at.isoformat(),
        "calendar_id": str(shift.calendar_id),
        "timezone": shift.calendar.timezone,
        "calendar_updated_at": shift.calendar.updated_at.isoformat(),
        "working_weekdays": shift.calendar.working_weekdays,
        "breaks": [
            {
                "id": str(b.pk),
                "starts_at": b.starts_at.isoformat(),
                "ends_at": b.ends_at.isoformat(),
                "ends_next_day": b.ends_next_day,
                "is_paid": b.is_paid,
            }
            for b in shift.breaks.order_by("sequence")
        ],
    }


@transaction.atomic
def create_roster_version(
    *,
    actor: User,
    organization: Organization,
    relationship: WorkRelationship,
    effective_from: date,
    effective_to: date,
    rotation_anchor: date,
    rotation: list[tuple[ShiftDefinition, int]],
    overrides: list[tuple[date, ShiftDefinition]],
    reason: str,
    project: Project | None = None,
    site: ProjectSite | None = None,
    supersedes: RosterVersion | None = None,
) -> RosterVersion:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    try:
        if project is not None:
            project = Project.objects.get(pk=project.pk, organization=organization)
        if site is not None:
            site = ProjectSite.objects.get(
                pk=site.pk, organization=organization, project=project
            )
    except (Project.DoesNotExist, ProjectSite.DoesNotExist) as exc:
        raise PermissionDenied("زمینه پروژه و کارگاه مجاز یافت نشد.") from exc
    _require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.ROSTERS_MANAGE,
        project=project,
        site=site,
    )
    try:
        relationship = WorkRelationship.objects.select_for_update().get(
            pk=relationship.pk, organization=organization
        )
    except WorkRelationship.DoesNotExist as exc:
        raise PermissionDenied("رابطه کاری مجاز یافت نشد.") from exc
    if (
        not rotation
        or not isinstance(rotation, list)
        or not isinstance(overrides, list)
    ):
        raise ValidationError("ترتیب و تغییرات صریح برنامه لازم است.")
    if project is not None:
        assignment = EmployeeProjectAssignment.objects.filter(
            organization=organization,
            employee_id=relationship.legacy_employee_id,
            project=project,
            site=site,
            start_date__lte=effective_from,
        ).filter(models.Q(end_date__isnull=True) | models.Q(end_date__gte=effective_to))
        if not relationship.legacy_employee_id or not assignment.exists():
            raise ValidationError("زمینه پروژه باید تخصیص صریح منبع داشته باشد.")
    previous = None
    if supersedes:
        try:
            previous = RosterVersion.objects.select_for_update().get(
                pk=supersedes.pk, organization=organization, relationship=relationship
            )
        except RosterVersion.DoesNotExist as exc:
            raise PermissionDenied("نسخه پیشین مجاز یافت نشد.") from exc
        if RosterVersion.objects.filter(supersedes=previous).exists():
            raise ValidationError("نسخه پیشین قبلاً جایگزین شده است.")
    # Serialize allocation on the relationship; prevent competing latest plans.
    overlaps = RosterVersion.objects.filter(
        relationship=relationship,
        replacement__isnull=True,
        effective_from__lte=effective_to,
        effective_to__gte=effective_from,
    )
    if previous:
        overlaps = overlaps.exclude(pk=previous.pk)
    if overlaps.exists():
        raise ValidationError("برنامه جاری هم‌پوشان باید به‌صراحت جایگزین شود.")
    values = {
        "organization": organization,
        "relationship": relationship,
        "actor": actor,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "rotation_anchor": rotation_anchor,
        "project": project,
        "site": site,
        "supersedes": previous,
        "reason": reason,
        "version": previous.version + 1 if previous else 1,
    }
    if previous:
        values["series_id"] = previous.series_id
    roster = RosterVersion.objects.create(**values)
    for position, (shift, days) in enumerate(rotation):
        if type(days) is not int or days < 1:
            raise ValidationError("مدت صریح و معتبر برای هر بخش لازم است.")
        shift = _shift(
            shift=shift,
            organization=organization,
            start=effective_from,
            end=effective_to,
        )
        RosterSlot.objects.create(
            organization=organization,
            roster=roster,
            shift=shift,
            position=position,
            day_count=days,
            shift_snapshot=_snapshot(shift),
        )
    dates = set()
    for offset, (when, shift) in enumerate(overrides, len(rotation)):
        if when in dates:
            raise ValidationError("تغییر تکراری در یک روز مجاز نیست.")
        dates.add(when)
        shift = _shift(shift=shift, organization=organization, start=when, end=when)
        RosterSlot.objects.create(
            organization=organization,
            roster=roster,
            shift=shift,
            position=offset,
            day_count=1,
            override_date=when,
            shift_snapshot=_snapshot(shift),
        )
    return roster


def get_roster(
    *, actor: User, organization: Organization, roster_id: object
) -> RosterVersion:
    try:
        item = RosterVersion.objects.select_related("project", "site").get(
            pk=roster_id, organization=organization
        )
    except RosterVersion.DoesNotExist as exc:
        raise PermissionDenied("برنامه مجاز یافت نشد.") from exc
    _require(
        actor=actor,
        organization=organization,
        code=BusinessPermissionCode.ROSTERS_VIEW,
        project=item.project,
        site=item.site,
    )
    return item


def planned_shift(
    *, actor: User, organization: Organization, roster_id: object, on_date: date
) -> dict[str, Any]:
    item = get_roster(actor=actor, organization=organization, roster_id=roster_id)
    if not item.effective_from <= on_date <= item.effective_to:
        raise ValidationError("تاریخ خارج از بازه نسخه برنامه است.")
    rows = list(item.slots.order_by("position"))
    for row in rows:
        if row.override_date == on_date:
            return row.shift_snapshot
    rotation = [r for r in rows if r.override_date is None]
    total = sum(r.day_count for r in rotation)
    if total == 0:
        raise ValidationError("ترتیب صریح برنامه موجود نیست.")
    offset = (on_date - item.rotation_anchor).days % total
    for row in rotation:
        if offset < row.day_count:
            return row.shift_snapshot
        offset -= row.day_count
    raise ValidationError("برنامه معتبر در دسترس نیست.")
