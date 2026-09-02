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
    DailyReport,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DailyReportStatus,
)
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationStatus,
)
from apps.projects.models import Project, ProjectPhase, ProjectPhaseStatus, ProjectSite


def _get_active_role(user: User, organization: Organization) -> str:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Authentication is required.")
    if (
        organization.status != OrganizationStatus.ACTIVE
        or organization.deleted_at is not None
    ):
        raise PermissionDenied("The organization is not active.")
    try:
        return organization.memberships.get(
            user=user,
            status=MembershipStatus.ACTIVE,
        ).role
    except organization.memberships.model.DoesNotExist as exc:
        raise PermissionDenied("You do not have access to this organization.") from exc


def _validate_project(*, organization: Organization, project: Project) -> None:
    if project.organization_id != organization.pk or project.deleted_at is not None:
        raise PermissionDenied("The project does not belong to this organization.")


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
        raise PermissionDenied("The worksite does not belong to this project.")


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
        raise PermissionDenied("The project phase is not active for this worksite.")


def _can_create_daily_reports(role: str) -> bool:
    return role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        MembershipRole.MANAGER,
        MembershipRole.MEMBER,
    }


def _can_approve_daily_reports(role: str) -> bool:
    return role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        MembershipRole.MANAGER,
    }


def _can_update_daily_report(
    *,
    role: str,
    report: DailyReport,
    actor: User,
) -> bool:
    return _can_approve_daily_reports(role) or report.created_by_id == actor.pk


def _get_draft_report_for_update(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
) -> DailyReport:
    role = _get_active_role(actor, organization)
    if not _can_create_daily_reports(role):
        raise PermissionDenied("You cannot update daily reports in this organization.")
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("Daily report not found in this organization.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if not _can_update_daily_report(role=role, report=report, actor=actor):
        raise PermissionDenied("You cannot update this daily report.")
    if report.status != DailyReportStatus.DRAFT:
        raise ValueError("Only draft daily reports can be updated.")
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

    role = _get_active_role(actor, organization)
    if not _can_create_daily_reports(role):
        raise PermissionDenied("You cannot create daily reports in this organization.")
    _validate_project(organization=organization, project=project)
    _validate_site(organization=organization, project=project, site=site)
    if phase is not None:
        _validate_phase(organization=organization, site=site, phase=phase)
    if not work_performed.strip():
        raise ValueError("Work performed is required.")
    if labor_count < 0:
        raise ValueError("Labor count cannot be negative.")
    if DailyReport.objects.filter(
        organization=organization,
        site=site,
        reporting_date=reporting_date,
    ).exists():
        raise ValueError("A daily report already exists for this worksite and date.")

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

    _get_active_role(user, organization)
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
    ).prefetch_related("labor_entries", "equipment_entries", "material_entries")
    try:
        return reports.get(pk=report_id)
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("Daily report not found in this organization.") from exc


@transaction.atomic
def submit_daily_report(
    *,
    organization: Organization,
    report_id: str,
    actor: User,
) -> DailyReport:
    """Submit a draft report; its author or a manager may submit it."""

    role = _get_active_role(actor, organization)
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("Daily report not found in this organization.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if not (_can_approve_daily_reports(role) or report.created_by_id == actor.pk):
        raise PermissionDenied("You cannot submit this daily report.")
    if report.status != DailyReportStatus.DRAFT:
        raise ValueError("Only draft daily reports can be submitted.")

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
    )
    if not team_name.strip():
        raise ValueError("Labor team name is required.")
    if worker_count <= 0:
        raise ValueError("Labor worker count must be positive.")
    if hours_worked <= Decimal("0.00"):
        raise ValueError("Labor hours worked must be positive.")
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
    )
    if not equipment_name.strip():
        raise ValueError("Equipment name is required.")
    if hours_used <= Decimal("0.00"):
        raise ValueError("Equipment hours used must be positive.")
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
) -> DailyReportMaterialEntry:
    """Add validated material usage to a draft daily report."""

    report = _get_draft_report_for_update(
        organization=organization,
        report_id=report_id,
        actor=actor,
    )
    if not material_name.strip() or not unit.strip():
        raise ValueError("Material name and unit are required.")
    if quantity <= Decimal("0.0000"):
        raise ValueError("Material quantity must be positive.")
    report.updated_by = actor
    report.save(update_fields=["updated_by", "updated_at"])
    entry = DailyReportMaterialEntry.objects.create(
        organization=organization,
        report=report,
        material_name=material_name.strip(),
        quantity=quantity,
        unit=unit.strip(),
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

    role = _get_active_role(actor, organization)
    if not _can_approve_daily_reports(role):
        raise PermissionDenied("You cannot approve daily reports in this organization.")
    try:
        report = (
            DailyReport.objects.select_for_update()
            .select_related("project", "site")
            .get(pk=report_id, organization=organization)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("Daily report not found in this organization.") from exc
    _validate_project(organization=organization, project=report.project)
    _validate_site(
        organization=organization,
        project=report.project,
        site=report.site,
    )
    if report.status != DailyReportStatus.SUBMITTED:
        raise ValueError("Only submitted daily reports can be approved.")

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
