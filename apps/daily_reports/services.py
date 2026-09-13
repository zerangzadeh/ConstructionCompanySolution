from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.daily_reports.models import (
    DailyActivity,
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DailyReportStatus,
    DelayEvent,
)
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.authorization import (
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
)
from apps.projects.models import (
    Activity,
    Project,
    ProjectPhase,
    ProjectPhaseStatus,
    ProjectSite,
)


def _validate_active_access(user: User, organization: Organization) -> None:
    if user.is_superuser and user.is_active:
        return
    get_active_membership(user=user, organization=organization)


def _validate_project(*, organization: Organization, project: Project) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("پروژه متعلق به این سازمان نیست.")


def _validate_site(
    *,
    organization: Organization,
    project: Project,
    site: ProjectSite,
) -> None:
    if (
        site.organization_id != organization.pk
        or site.project_id != project.pk
        or not site.is_active
    ):
        raise PermissionDenied("کارگاه متعلق به این پروژه نیست.")


def _validate_phase(
    *,
    organization: Organization,
    site: ProjectSite,
    phase: ProjectPhase,
) -> None:
    if (
        phase.organization_id != organization.pk
        or phase.site_id != site.pk
        or phase.status != ProjectPhaseStatus.ACTIVE
    ):
        raise PermissionDenied("فاز پروژه برای این کارگاه فعال نیست.")


def _can_create_daily_reports(user: User, organization: Organization) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_CREATE,
    )


def _can_approve_daily_reports(user: User, organization: Organization) -> bool:
    return has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_APPROVE,
    )


def _can_update_daily_report(
    *,
    organization: Organization,
    report: DailyReport,
    actor: User,
    permission: BusinessPermissionCode,
) -> bool:
    return has_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
    ) and (
        _can_approve_daily_reports(actor, organization)
        or report.created_by_id == actor.pk
    )


def _get_draft_report_for_update(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    permission: BusinessPermissionCode,
) -> DailyReport:
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if not _can_update_daily_report(
        organization=organization,
        report=report,
        actor=actor,
        permission=permission,
    ):
        raise PermissionDenied("اجازه به‌روزرسانی این گزارش روزانه را ندارید.")
    if report.status != DailyReportStatus.DRAFT:
        raise ValueError("فقط گزارش روزانه پیش‌نویس قابل به‌روزرسانی است.")
    return report


@transaction.atomic
def create_daily_report(
    *,
    organization: Organization,
    project: Project,
    site: ProjectSite,
    actor: User,
    reporting_date: date,
    phase: ProjectPhase | None = None,
    work_performed: str,
    weather_conditions: str = "",
    labor_count: int = 0,
    progress_summary: str = "",
    issues_and_delays: str = "",
    safety_notes: str = "",
    quality_notes: str = "",
) -> DailyReport:
    """Create a draft report after checking tenant, role, and project scope."""

    if not _can_create_daily_reports(actor, organization):
        raise PermissionDenied("اجازه ایجاد گزارش روزانه در این سازمان را ندارید.")
    _validate_project(organization=organization, project=project)
    _validate_site(organization=organization, project=project, site=site)
    if phase is not None:
        _validate_phase(organization=organization, site=site, phase=phase)
    if not work_performed.strip():
        raise ValueError("وارد کردن کارهای انجام‌شده الزامی است.")
    if labor_count < 0:
        raise ValueError("تعداد نیروی انسانی نمی‌تواند منفی باشد.")
    if DailyReport.objects.filter(
        organization=organization,
        site=site,
        reporting_date=reporting_date,
    ).exists():
        raise ValueError("برای این کارگاه و تاریخ، گزارش روزانه از قبل وجود دارد.")

    report = DailyReport.objects.create(
        organization=organization,
        project=project,
        site=site,
        phase=phase,
        reporting_date=reporting_date,
        weather_conditions=weather_conditions.strip(),
        labor_count=labor_count,
        work_performed=work_performed.strip(),
        progress_summary=progress_summary.strip(),
        issues_and_delays=issues_and_delays.strip(),
        safety_notes=safety_notes.strip(),
        quality_notes=quality_notes.strip(),
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        action=AuditAction.DAILY_REPORT_CREATED,
        entity_type="daily_report",
        entity_id=report.pk,
        organization=organization,
        actor=actor,
        metadata={
            "project_id": str(project.pk),
            "site_id": str(site.pk),
            "phase_id": str(phase.pk) if phase else None,
            "reporting_date": report.reporting_date.isoformat(),
        },
    )
    return report


def get_organization_daily_reports(
    *,
    user: User,
    organization: Organization,
) -> QuerySet[DailyReport]:
    """Return daily reports visible only to an active organization member."""

    _validate_active_access(user, organization)
    if not has_business_permission(
        user=user,
        organization=organization,
        permission=BusinessPermissionCode.DAILY_REPORTS_VIEW,
    ):
        raise PermissionDenied("اجازه مشاهده گزارش‌های روزانه این سازمان را ندارید.")
    return (
        DailyReport.objects.filter(
            organization=organization,
            project__deleted_at__isnull=True,
        )
        .select_related("project", "site", "phase", "created_by", "approved_by")
        .order_by("-reporting_date", "-created_at")
    )


def get_organization_daily_report(
    *,
    user: User,
    organization: Organization,
    report_id: str,
) -> DailyReport:
    """Return one report after applying active-organization scope."""

    reports = get_organization_daily_reports(
        user=user,
        organization=organization,
    ).prefetch_related(
        "labor_entries",
        "equipment_entries",
        "material_entries__material",
        "material_entries__unit_of_measure",
        "daily_activities__activity",
        "daily_activities__unit_of_measure",
        "delay_events__activity",
    )
    try:
        return reports.get(pk=report_id)
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc


@transaction.atomic
def submit_daily_report(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
) -> DailyReport:
    """Submit a draft report; its author or a manager may submit it."""

    _validate_active_access(actor, organization)
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if not _can_update_daily_report(
        organization=organization,
        report=report,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_SUBMIT,
    ):
        raise PermissionDenied("اجازه ارسال این گزارش روزانه را ندارید.")
    if report.status != DailyReportStatus.DRAFT:
        raise ValueError("فقط گزارش روزانه پیش‌نویس قابل ارسال است.")

    report.status = DailyReportStatus.SUBMITTED
    report.submitted_at = timezone.now()
    report.updated_by = actor
    report.save(update_fields=["status", "submitted_at", "updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.DAILY_REPORT_SUBMITTED,
        entity_type="daily_report",
        entity_id=report.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(report.project_id), "site_id": str(report.site_id)},
    )
    return report


@transaction.atomic
def add_daily_report_labor_entry(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    team_name: str,
    worker_count: int,
    hours_worked: Decimal,
    notes: str = "",
) -> DailyReportLaborEntry:
    """Add a validated labor record to a draft daily report."""

    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_ADD_LABOR,
    )
    if not team_name.strip():
        raise ValueError("وارد کردن نام گروه کاری الزامی است.")
    if worker_count <= 0:
        raise ValueError("تعداد نیروی انسانی باید مثبت باشد.")
    if hours_worked <= Decimal("0.00"):
        raise ValueError("ساعات کارکرد نیروی انسانی باید مثبت باشد.")
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    entry = DailyReportLaborEntry.objects.create(
        organization=organization,
        report=report,
        team_name=team_name.strip(),
        worker_count=worker_count,
        hours_worked=hours_worked,
        notes=notes.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.DAILY_REPORT_LABOR_ADDED,
        entity_type="daily_report_labor_entry",
        entity_id=entry.pk,
        organization=organization,
        actor=actor,
        metadata={"report_id": str(report.pk), "worker_count": entry.worker_count},
    )
    return entry


@transaction.atomic
def add_daily_report_equipment_entry(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    equipment_name: str,
    hours_used: Decimal,
    notes: str = "",
) -> DailyReportEquipmentEntry:
    """Add validated equipment usage to a draft daily report."""

    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_ADD_EQUIPMENT,
    )
    if not equipment_name.strip():
        raise ValueError("وارد کردن نام تجهیز الزامی است.")
    if hours_used <= Decimal("0.00"):
        raise ValueError("ساعات کارکرد تجهیز باید مثبت باشد.")
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    entry = DailyReportEquipmentEntry.objects.create(
        organization=organization,
        report=report,
        equipment_name=equipment_name.strip(),
        hours_used=hours_used,
        notes=notes.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.DAILY_REPORT_EQUIPMENT_ADDED,
        entity_type="daily_report_equipment_entry",
        entity_id=entry.pk,
        organization=organization,
        actor=actor,
        metadata={"report_id": str(report.pk), "hours_used": str(entry.hours_used)},
    )
    return entry


@transaction.atomic
def add_daily_report_material_entry(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    material_name: str,
    quantity: Decimal,
    unit: str,
    notes: str = "",
    material: Material | None = None,
    unit_of_measure: UnitOfMeasure | None = None,
) -> DailyReportMaterialEntry:
    """Add validated material usage to a draft daily report."""

    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_ADD_MATERIAL,
    )
    if material is not None:
        if (
            material.organization_id != organization.id
            or not material.is_active
            or material.archived_at
        ):
            raise PermissionDenied("مصالح متعلق به این سازمان فعال نیست.")
        unit_of_measure = material.unit_of_measure
        material_name = material.name
        unit = unit_of_measure.symbol
    elif unit_of_measure is not None:
        if (
            unit_of_measure.organization_id != organization.id
            or not unit_of_measure.is_active
            or unit_of_measure.archived_at
        ):
            raise PermissionDenied("واحد اندازه‌گیری متعلق به این سازمان فعال نیست.")
        unit = unit_of_measure.symbol
    if not material_name.strip() or not unit.strip():
        raise ValueError("وارد کردن نام مصالح و واحد الزامی است.")
    if quantity <= Decimal("0.0000"):
        raise ValueError("مقدار مصالح باید مثبت باشد.")
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    entry = DailyReportMaterialEntry.objects.create(
        organization=organization,
        report=report,
        material_name=material_name.strip(),
        material=material,
        quantity=quantity,
        unit=unit.strip(),
        unit_of_measure=unit_of_measure,
        notes=notes.strip(),
        created_by=actor,
    )
    record_audit_event(
        action=AuditAction.DAILY_REPORT_MATERIAL_ADDED,
        entity_type="daily_report_material_entry",
        entity_id=entry.pk,
        organization=organization,
        actor=actor,
        metadata={
            "report_id": str(report.pk),
            "quantity": str(entry.quantity),
            "unit": entry.unit,
            "material_id": str(entry.material_id) if entry.material_id else None,
        },
    )
    return entry


def _validate_daily_activity_scope(*, report: DailyReport, activity: Activity) -> None:
    if (
        activity.organization_id != report.organization_id
        or activity.project_id != report.project_id
        or not activity.is_active
        or activity.archived_at is not None
    ):
        raise PermissionDenied("فعالیت متعلق به پروژه فعال این گزارش نیست.")
    if activity.site_id and activity.site_id != report.site_id:
        raise PermissionDenied("فعالیت متعلق به کارگاه گزارش نیست.")
    if activity.phase_id and activity.phase_id != report.phase_id:
        raise PermissionDenied("فعالیت متعلق به فاز گزارش نیست.")


@transaction.atomic
def add_daily_activity(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    description: str,
    activity: Activity | None = None,
    quantity: Decimal | None = None,
    unit_of_measure: UnitOfMeasure | None = None,
    progress_percent: Decimal | None = None,
    notes: str = "",
) -> DailyActivity:
    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_ADD_ACTIVITY,
    )
    if activity is not None:
        _validate_daily_activity_scope(report=report, activity=activity)
        if not description.strip():
            description = activity.name
        if (
            activity.unit_of_measure_id
            and unit_of_measure
            and activity.unit_of_measure_id != unit_of_measure.id
        ):
            raise ValueError("واحد باید با واحد اصلی فعالیت مطابقت داشته باشد.")
        if activity.unit_of_measure_id and unit_of_measure is None:
            unit_of_measure = activity.unit_of_measure
    if unit_of_measure is not None and (
        unit_of_measure.organization_id != organization.id
        or not unit_of_measure.is_active
        or unit_of_measure.archived_at
    ):
        raise PermissionDenied("واحد اندازه‌گیری متعلق به این سازمان فعال نیست.")
    entry = DailyActivity.objects.create(
        organization=organization,
        report=report,
        activity=activity,
        description=description.strip(),
        quantity=quantity,
        unit_of_measure=unit_of_measure,
        progress_percent=progress_percent,
        notes=notes.strip(),
        created_by=actor,
    )
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.DAILY_ACTIVITY_ADDED,
        entity_type="daily_activity",
        entity_id=entry.pk,
        organization=organization,
        actor=actor,
        metadata={
            "report_id": str(report.pk),
            "activity_id": str(activity.pk) if activity else None,
        },
    )
    return entry


@transaction.atomic
def add_delay_event(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
    occurred_on: date,
    cause: str,
    activity: Activity | None = None,
    category: str = "",
    impact: str = "",
    responsible_party: str = "",
    duration_hours: Decimal | None = None,
) -> DelayEvent:
    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
        permission=BusinessPermissionCode.DAILY_REPORTS_ADD_DELAY,
    )
    if activity is not None:
        _validate_daily_activity_scope(report=report, activity=activity)
    entry = DelayEvent.objects.create(
        organization=organization,
        report=report,
        activity=activity,
        occurred_on=occurred_on,
        cause=cause.strip(),
        category=category.strip(),
        impact=impact.strip(),
        responsible_party=responsible_party.strip(),
        duration_hours=duration_hours,
        created_by=actor,
    )
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    record_audit_event(
        action=AuditAction.DELAY_EVENT_ADDED,
        entity_type="delay_event",
        entity_id=entry.pk,
        organization=organization,
        actor=actor,
        metadata={
            "report_id": str(report.pk),
            "activity_id": str(activity.pk) if activity else None,
        },
    )
    return entry


@transaction.atomic
def approve_daily_report(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
) -> DailyReport:
    """Approve a submitted report and make its operational history final."""

    if not _can_approve_daily_reports(actor, organization):
        raise PermissionDenied("اجازه تأیید گزارش‌های روزانه این سازمان را ندارید.")
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این سازمان یافت نشد.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if report.status != DailyReportStatus.SUBMITTED:
        raise ValueError("فقط گزارش‌های روزانه ارسال‌شده قابل تأیید هستند.")

    now = timezone.now()
    report.status = DailyReportStatus.APPROVED
    report.approved_at = now
    report.approved_by = actor
    report.updated_by = actor
    report.save(
        update_fields=[
            "status",
            "approved_at",
            "approved_by",
            "updated_by",
            "updated_at",
        ]
    )
    record_audit_event(
        action=AuditAction.DAILY_REPORT_APPROVED,
        entity_type="daily_report",
        entity_id=report.pk,
        organization=organization,
        actor=actor,
        metadata={"project_id": str(report.project_id), "site_id": str(report.site_id)},
    )
    return report
