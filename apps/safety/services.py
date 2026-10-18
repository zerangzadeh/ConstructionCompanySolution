from datetime import date, datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.daily_reports.models import DailyReport
from apps.organizations.authorization import (
    get_active_membership,
    require_business_permission,
    scope_queryset,
)
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.parties.models import BusinessParty
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite
from apps.safety.models import SafetyIncident, SafetyIncidentStatus, SafetyReviewStatus
from apps.workforce.models import Employee

_STATUS_TRANSITIONS = {
    SafetyIncidentStatus.REPORTED: (SafetyIncidentStatus.UNDER_REVIEW,),
    SafetyIncidentStatus.UNDER_REVIEW: (SafetyIncidentStatus.ASSIGNED,),
    SafetyIncidentStatus.ASSIGNED: (SafetyIncidentStatus.ACTION_IN_PROGRESS,),
    SafetyIncidentStatus.ACTION_IN_PROGRESS: (SafetyIncidentStatus.RESOLVED,),
    SafetyIncidentStatus.RESOLVED: (SafetyIncidentStatus.CLOSED,),
    SafetyIncidentStatus.CLOSED: (),
}


def _require_permission(
    *,
    organization: Organization,
    user: User,
    permission: BusinessPermissionCode,
    project: Project | None = None,
    site: ProjectSite | None = None,
    allow_any_scope: bool = False,
) -> None:
    require_business_permission(
        user=user,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        allow_any_scope=allow_any_scope,
        allow_site_parent=True,
        message="اجازه انجام این عملیات ایمنی را ندارید.",
    )


def _save_validated(
    incident: SafetyIncident,
    message: str,
    *,
    allow_status_transition: bool = False,
) -> None:
    try:
        incident.full_clean()
        if allow_status_transition:
            incident._service_transition = True
        incident.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc


def _require_same_organization(
    organization: Organization,
    **records: Project
    | ProjectSite
    | ProjectPhase
    | Activity
    | DailyReport
    | Employee
    | BusinessParty
    | None,
) -> None:
    if any(
        record is not None and record.organization_id != organization.pk
        for record in records.values()
    ):
        raise PermissionDenied("رکورد مرتبط ایمنی متعلق به سازمان دیگری است.")


def _validate_structure(
    *,
    organization: Organization,
    project: Project,
    site: ProjectSite | None,
    phase: ProjectPhase | None,
    activity: Activity | None,
    daily_report: DailyReport | None,
    responsible_user: User | None,
    responsible_employee: Employee | None,
    responsible_party: BusinessParty | None,
) -> None:
    _require_same_organization(
        organization,
        project=project,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
        responsible_employee=responsible_employee,
        responsible_party=responsible_party,
    )
    if project.deleted_at:
        raise ValueError("برای پروژه بایگانی‌شده حادثه ایمنی ثبت نمی‌شود.")
    if site is not None and site.project_id != project.pk:
        raise ValueError("کارگاه باید متعلق به پروژه حادثه باشد.")
    if phase is not None and (site is None or phase.site_id != site.pk):
        raise ValueError("فاز باید متعلق به کارگاه حادثه باشد.")
    if activity is not None:
        if activity.project_id != project.pk:
            raise ValueError("فعالیت باید متعلق به پروژه حادثه باشد.")
        if activity.site_id and activity.site_id != getattr(site, "pk", None):
            raise ValueError("کارگاه فعالیت با کارگاه حادثه سازگار نیست.")
        if activity.phase_id and activity.phase_id != getattr(phase, "pk", None):
            raise ValueError("فاز فعالیت با فاز حادثه سازگار نیست.")
    if daily_report is not None:
        if daily_report.project_id != project.pk:
            raise ValueError("گزارش روزانه باید متعلق به پروژه حادثه باشد.")
        if daily_report.site_id != getattr(site, "pk", None):
            raise ValueError("کارگاه گزارش روزانه با حادثه سازگار نیست.")
        if daily_report.phase_id != getattr(phase, "pk", None):
            raise ValueError("فاز گزارش روزانه با حادثه سازگار نیست.")
    if (
        responsible_user is not None
        and not organization.memberships.filter(
            user=responsible_user,
            status="active",
            role_definition__is_active=True,
        ).exists()
    ):
        raise PermissionDenied("کاربر مسئول باید عضو فعال همین سازمان باشد.")


def _locked_incident(*, organization: Organization, incident_id: str) -> SafetyIncident:
    try:
        return (
            SafetyIncident.objects.select_for_update(of=("self",))
            .select_related(
                "project",
                "site",
                "phase",
                "activity",
                "daily_report",
                "responsible_user",
                "responsible_employee",
                "responsible_party",
            )
            .get(pk=incident_id, organization=organization)
        )
    except (SafetyIncident.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("حادثه ایمنی در این سازمان یافت نشد.") from exc


def _record_transition(
    *,
    incident: SafetyIncident,
    actor: User,
    action: AuditAction,
    previous_status: str,
    metadata: dict[str, object] | None = None,
) -> None:
    record_audit_event(
        action=action,
        entity_type="safety_incident",
        entity_id=incident.pk,
        organization=incident.organization,
        actor=actor,
        metadata={
            "incident_number": incident.incident_number,
            "previous_status": previous_status,
            "new_status": incident.status,
            **(metadata or {}),
        },
    )


@transaction.atomic
def _create_safety_incident_domain(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    incident_number: str,
    occurred_at: datetime,
    incident_type: str,
    severity: str,
    description: str,
    immediate_action: str = "",
    site: ProjectSite | None = None,
    phase: ProjectPhase | None = None,
    activity: Activity | None = None,
    daily_report: DailyReport | None = None,
) -> SafetyIncident:
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_CREATE,
        project=project,
        site=site,
    )
    _validate_structure(
        organization=organization,
        project=project,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
        responsible_user=None,
        responsible_employee=None,
        responsible_party=None,
    )
    incident = SafetyIncident(
        organization=organization,
        project=project,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
        incident_number=incident_number,
        occurred_at=occurred_at,
        incident_type=incident_type,
        severity=severity,
        description=description,
        immediate_action=immediate_action,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(incident, "اطلاعات حادثه معتبر نیست یا شماره آن تکراری است.")
    record_audit_event(
        action=AuditAction.SAFETY_INCIDENT_CREATED,
        entity_type="safety_incident",
        entity_id=incident.pk,
        organization=organization,
        actor=actor,
        metadata={
            "incident_number": incident.incident_number,
            "project_id": str(project.pk),
            "severity": severity,
        },
    )
    return incident


def get_organization_safety_incidents(
    *, user: User, organization: Organization, project: Project | None = None
) -> QuerySet[SafetyIncident]:
    _require_permission(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_VIEW,
        project=project,
        allow_any_scope=project is None,
    )
    _require_same_organization(organization, project=project)
    incidents = SafetyIncident.objects.filter(organization=organization)
    if project is not None:
        incidents = incidents.filter(project=project)
    membership = get_active_membership(user=user, organization=organization)
    incidents = scope_queryset(
        queryset=incidents,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    return incidents.select_related(
        "project",
        "site",
        "phase",
        "responsible_user",
        "responsible_employee",
        "responsible_party",
    )


def get_organization_safety_incident(
    *, user: User, organization: Organization, incident_id: str
) -> SafetyIncident:
    try:
        return get_organization_safety_incidents(
            user=user, organization=organization
        ).get(pk=incident_id)
    except (SafetyIncident.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("حادثه ایمنی در این سازمان یافت نشد.") from exc


@transaction.atomic
def _review_safety_incident_domain(
    *, organization: Organization, actor: User, incident_id: str
) -> SafetyIncident:
    incident = _locked_incident(organization=organization, incident_id=incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_REVIEW,
        project=incident.project,
        site=incident.site,
    )
    previous_status = incident.status
    if SafetyIncidentStatus.UNDER_REVIEW not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط حادثه ثبت‌شده قابل ورود به بررسی است.")
    incident.status = SafetyIncidentStatus.UNDER_REVIEW
    incident.reviewed_at = timezone.now()
    incident.reviewed_by = actor
    incident.updated_by = actor
    _save_validated(
        incident,
        "اطلاعات بررسی حادثه معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        incident=incident,
        actor=actor,
        action=AuditAction.SAFETY_INCIDENT_REVIEWED,
        previous_status=previous_status,
    )
    return incident


@transaction.atomic
def _assign_safety_incident_domain(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    due_date: date,
    responsible_user: User | None = None,
    responsible_employee: Employee | None = None,
    responsible_party: BusinessParty | None = None,
) -> SafetyIncident:
    incident = _locked_incident(organization=organization, incident_id=incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_REVIEW,
        project=incident.project,
        site=incident.site,
    )
    previous_status = incident.status
    if SafetyIncidentStatus.ASSIGNED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط حادثه در حال بررسی قابل تخصیص است.")
    _validate_structure(
        organization=organization,
        project=incident.project,
        site=incident.site,
        phase=incident.phase,
        activity=incident.activity,
        daily_report=incident.daily_report,
        responsible_user=responsible_user,
        responsible_employee=responsible_employee,
        responsible_party=responsible_party,
    )
    if not any((responsible_user, responsible_employee, responsible_party)):
        raise ValueError("حداقل یک کاربر، کارمند یا طرف تجاری مسئول تعیین کنید.")
    incident.responsible_user = responsible_user
    incident.responsible_employee = responsible_employee
    incident.responsible_party = responsible_party
    incident.due_date = due_date
    incident.status = SafetyIncidentStatus.ASSIGNED
    incident.updated_by = actor
    _save_validated(
        incident,
        "اطلاعات تخصیص حادثه معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        incident=incident,
        actor=actor,
        action=AuditAction.SAFETY_INCIDENT_ASSIGNED,
        previous_status=previous_status,
        metadata={"due_date": due_date.isoformat()},
    )
    return incident


@transaction.atomic
def _start_corrective_action_domain(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    corrective_action: str,
) -> SafetyIncident:
    incident = _locked_incident(organization=organization, incident_id=incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_MANAGE,
        project=incident.project,
        site=incident.site,
    )
    previous_status = incident.status
    if (
        SafetyIncidentStatus.ACTION_IN_PROGRESS
        not in _STATUS_TRANSITIONS[previous_status]
    ):
        raise ValueError("فقط حادثه تخصیص‌یافته وارد اقدام اصلاحی می‌شود.")
    incident.corrective_action = corrective_action
    incident.status = SafetyIncidentStatus.ACTION_IN_PROGRESS
    incident.updated_by = actor
    _save_validated(
        incident,
        "اقدام اصلاحی حادثه معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        incident=incident,
        actor=actor,
        action=AuditAction.SAFETY_CORRECTIVE_ACTION_STARTED,
        previous_status=previous_status,
    )
    return incident


@transaction.atomic
def _resolve_safety_incident_domain(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    resolution_summary: str,
) -> SafetyIncident:
    incident = _locked_incident(organization=organization, incident_id=incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_MANAGE,
        project=incident.project,
        site=incident.site,
    )
    previous_status = incident.status
    if SafetyIncidentStatus.RESOLVED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط حادثه دارای اقدام اصلاحی قابل رفع است.")
    incident.resolution_summary = resolution_summary
    incident.resolved_at = timezone.now()
    incident.resolved_by = actor
    incident.status = SafetyIncidentStatus.RESOLVED
    incident.updated_by = actor
    _save_validated(
        incident,
        "اطلاعات رفع حادثه معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        incident=incident,
        actor=actor,
        action=AuditAction.SAFETY_INCIDENT_RESOLVED,
        previous_status=previous_status,
    )
    return incident


@transaction.atomic
def _close_safety_incident_domain(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    closure_summary: str,
) -> SafetyIncident:
    incident = _locked_incident(organization=organization, incident_id=incident_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.SAFETY_INCIDENTS_CLOSE,
        project=incident.project,
        site=incident.site,
    )
    previous_status = incident.status
    if SafetyIncidentStatus.CLOSED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط حادثه رفع‌شده قابل بستن است.")
    if incident.review_status != SafetyReviewStatus.APPROVED:
        raise ValueError("بستن حادثه مستلزم تأیید جداگانه رکورد است.")
    incident.closure_summary = closure_summary
    incident.closed_at = timezone.now()
    incident.closed_by = actor
    incident.status = SafetyIncidentStatus.CLOSED
    incident.updated_by = actor
    _save_validated(
        incident,
        "جمع‌بندی بستن حادثه معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        incident=incident,
        actor=actor,
        action=AuditAction.SAFETY_INCIDENT_CLOSED,
        previous_status=previous_status,
    )
    return incident


@transaction.atomic
def create_safety_incident(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    incident_number: str,
    occurred_at: datetime,
    incident_type: str,
    severity: str,
    description: str,
    immediate_action: str = "",
    site: ProjectSite | None = None,
    phase: ProjectPhase | None = None,
    activity: Activity | None = None,
    daily_report: DailyReport | None = None,
) -> SafetyIncident:
    from .workflow import start_safety_workflow

    incident = _create_safety_incident_domain(
        organization=organization,
        actor=actor,
        project=project,
        incident_number=incident_number,
        occurred_at=occurred_at,
        incident_type=incident_type,
        severity=severity,
        description=description,
        immediate_action=immediate_action,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
    )
    from apps.workflows.runtime import WorkflowConflict

    try:
        with transaction.atomic():
            start_safety_workflow(
                organization=organization, incident=incident, actor=actor
            )
    except WorkflowConflict:
        # Leave an unroutable new incident on its existing domain path.
        pass
    return incident


def review_safety_incident(
    *, organization: Organization, actor: User, incident_id: str
) -> SafetyIncident:
    from .workflow import perform_safety_transition

    return perform_safety_transition(
        organization=organization,
        actor=actor,
        incident_id=incident_id,
        expected_status=SafetyIncidentStatus.REPORTED,
        outcome=SafetyIncidentStatus.UNDER_REVIEW,
        context={},
    )


def assign_safety_incident(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    due_date: date,
    responsible_user: User | None = None,
    responsible_employee: Employee | None = None,
    responsible_party: BusinessParty | None = None,
) -> SafetyIncident:
    from .workflow import perform_safety_transition

    return perform_safety_transition(
        organization=organization,
        actor=actor,
        incident_id=incident_id,
        expected_status=SafetyIncidentStatus.UNDER_REVIEW,
        outcome=SafetyIncidentStatus.ASSIGNED,
        context={
            "due_date": due_date,
            "responsible_user": responsible_user,
            "responsible_employee": responsible_employee,
            "responsible_party": responsible_party,
        },
    )


def start_corrective_action(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    corrective_action: str,
) -> SafetyIncident:
    from .workflow import perform_safety_transition

    return perform_safety_transition(
        organization=organization,
        actor=actor,
        incident_id=incident_id,
        expected_status=SafetyIncidentStatus.ASSIGNED,
        outcome=SafetyIncidentStatus.ACTION_IN_PROGRESS,
        context={"corrective_action": corrective_action},
    )


def resolve_safety_incident(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    resolution_summary: str,
) -> SafetyIncident:
    from .workflow import perform_safety_transition

    return perform_safety_transition(
        organization=organization,
        actor=actor,
        incident_id=incident_id,
        expected_status=SafetyIncidentStatus.ACTION_IN_PROGRESS,
        outcome=SafetyIncidentStatus.RESOLVED,
        context={"resolution_summary": resolution_summary},
    )


def close_safety_incident(
    *,
    organization: Organization,
    actor: User,
    incident_id: str,
    closure_summary: str,
) -> SafetyIncident:
    from .workflow import perform_safety_transition

    return perform_safety_transition(
        organization=organization,
        actor=actor,
        incident_id=incident_id,
        expected_status=SafetyIncidentStatus.RESOLVED,
        outcome=SafetyIncidentStatus.CLOSED,
        context={"closure_summary": closure_summary},
    )
