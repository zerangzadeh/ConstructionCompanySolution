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
from apps.quality.models import QualityIssue, QualityIssueStatus, QualityReviewStatus
from apps.workforce.models import Employee

_STATUS_TRANSITIONS = {
    QualityIssueStatus.REPORTED: (QualityIssueStatus.UNDER_REVIEW,),
    QualityIssueStatus.UNDER_REVIEW: (QualityIssueStatus.ASSIGNED,),
    QualityIssueStatus.ASSIGNED: (QualityIssueStatus.ACTION_IN_PROGRESS,),
    QualityIssueStatus.ACTION_IN_PROGRESS: (QualityIssueStatus.AWAITING_VERIFICATION,),
    QualityIssueStatus.AWAITING_VERIFICATION: (QualityIssueStatus.VERIFIED,),
    QualityIssueStatus.VERIFIED: (QualityIssueStatus.CLOSED,),
    QualityIssueStatus.CLOSED: (),
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
        message="اجازه انجام این عملیات کیفیت را ندارید.",
    )


def _save_validated(
    issue: QualityIssue,
    message: str,
    *,
    allow_status_transition: bool = False,
) -> None:
    try:
        issue.full_clean()
        if allow_status_transition:
            issue._service_transition = True
        issue.save()
    except (IntegrityError, ValidationError) as exc:
        raise ValueError(message) from exc
    finally:
        if hasattr(issue, "_service_transition"):
            del issue._service_transition


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
        raise PermissionDenied("رکورد مرتبط کیفیت متعلق به سازمان دیگری است.")


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
        raise ValueError("برای پروژه بایگانی‌شده مسئله کیفیت ثبت نمی‌شود.")
    if site is not None and site.project_id != project.pk:
        raise ValueError("کارگاه باید متعلق به پروژه مسئله باشد.")
    if phase is not None and (site is None or phase.site_id != site.pk):
        raise ValueError("فاز باید متعلق به کارگاه مسئله باشد.")
    if activity is not None:
        if activity.project_id != project.pk:
            raise ValueError("فعالیت باید متعلق به پروژه مسئله باشد.")
        if activity.site_id and activity.site_id != getattr(site, "pk", None):
            raise ValueError("کارگاه فعالیت با مسئله کیفیت سازگار نیست.")
        if activity.phase_id and activity.phase_id != getattr(phase, "pk", None):
            raise ValueError("فاز فعالیت با مسئله کیفیت سازگار نیست.")
    if daily_report is not None:
        if daily_report.project_id != project.pk:
            raise ValueError("گزارش روزانه باید متعلق به پروژه مسئله باشد.")
        if daily_report.site_id != getattr(site, "pk", None):
            raise ValueError("کارگاه گزارش روزانه با مسئله کیفیت سازگار نیست.")
        if daily_report.phase_id != getattr(phase, "pk", None):
            raise ValueError("فاز گزارش روزانه با مسئله کیفیت سازگار نیست.")
    if (
        responsible_user is not None
        and not organization.memberships.filter(
            user=responsible_user,
            status="active",
            role_definition__is_active=True,
        ).exists()
    ):
        raise PermissionDenied("کاربر مسئول باید عضو فعال همین سازمان باشد.")
    if responsible_employee is not None and responsible_employee.archived_at:
        raise ValueError("کارمند مسئول نباید بایگانی‌شده باشد.")
    if responsible_party is not None and responsible_party.archived_at:
        raise ValueError("طرف تجاری مسئول نباید بایگانی‌شده باشد.")


def _locked_issue(*, organization: Organization, issue_id: str) -> QualityIssue:
    try:
        return (
            QualityIssue.objects.select_for_update(of=("self",))
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
            .get(pk=issue_id, organization=organization)
        )
    except (QualityIssue.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("مسئله کیفیت در این سازمان یافت نشد.") from exc


def _record_transition(
    *,
    issue: QualityIssue,
    actor: User,
    action: AuditAction,
    previous_status: str,
    metadata: dict[str, object] | None = None,
) -> None:
    record_audit_event(
        action=action,
        entity_type="quality_issue",
        entity_id=issue.pk,
        organization=issue.organization,
        actor=actor,
        metadata={
            "issue_number": issue.issue_number,
            "previous_status": previous_status,
            "new_status": issue.status,
            **(metadata or {}),
        },
    )


@transaction.atomic
def _create_quality_issue_domain(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    issue_number: str,
    identified_at: datetime,
    issue_type: str,
    severity: str,
    description: str,
    specification_reference: str = "",
    site: ProjectSite | None = None,
    phase: ProjectPhase | None = None,
    activity: Activity | None = None,
    daily_report: DailyReport | None = None,
) -> QualityIssue:
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
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_CREATE,
        project=project,
        site=site,
    )
    issue = QualityIssue(
        organization=organization,
        project=project,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
        issue_number=issue_number,
        identified_at=identified_at,
        issue_type=issue_type,
        severity=severity,
        description=description,
        specification_reference=specification_reference,
        created_by=actor,
        updated_by=actor,
    )
    _save_validated(issue, "اطلاعات مسئله معتبر نیست یا شماره آن تکراری است.")
    record_audit_event(
        action=AuditAction.QUALITY_ISSUE_CREATED,
        entity_type="quality_issue",
        entity_id=issue.pk,
        organization=organization,
        actor=actor,
        metadata={
            "issue_number": issue.issue_number,
            "project_id": str(project.pk),
            "severity": severity,
        },
    )
    return issue


def get_organization_quality_issues(
    *, user: User, organization: Organization, project: Project | None = None
) -> QuerySet[QualityIssue]:
    _require_permission(
        organization=organization,
        user=user,
        permission=BusinessPermissionCode.QUALITY_ISSUES_VIEW,
        project=project,
        allow_any_scope=project is None,
    )
    _require_same_organization(organization, project=project)
    issues = QualityIssue.objects.filter(organization=organization)
    if project is not None:
        issues = issues.filter(project=project)
    membership = get_active_membership(user=user, organization=organization)
    issues = scope_queryset(
        queryset=issues,
        membership=membership,
        project_lookup="project_id",
        site_lookup="site_id",
    )
    return issues.select_related(
        "project",
        "site",
        "phase",
        "responsible_user",
        "responsible_employee",
        "responsible_party",
    )


def get_organization_quality_issue(
    *, user: User, organization: Organization, issue_id: str
) -> QualityIssue:
    try:
        return get_organization_quality_issues(
            user=user, organization=organization
        ).get(pk=issue_id)
    except (QualityIssue.DoesNotExist, ValidationError) as exc:
        raise PermissionDenied("مسئله کیفیت در این سازمان یافت نشد.") from exc


@transaction.atomic
def _review_quality_issue_domain(
    *, organization: Organization, actor: User, issue_id: str
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_REVIEW,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if QualityIssueStatus.UNDER_REVIEW not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط مسئله ثبت‌شده قابل ورود به بررسی است.")
    issue.status = QualityIssueStatus.UNDER_REVIEW
    issue.reviewed_at = timezone.now()
    issue.reviewed_by = actor
    issue.updated_by = actor
    _save_validated(
        issue, "اطلاعات بررسی مسئله معتبر نیست.", allow_status_transition=True
    )
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_ISSUE_REVIEWED,
        previous_status=previous_status,
    )
    return issue


@transaction.atomic
def _assign_quality_issue_domain(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    due_date: date,
    responsible_user: User | None = None,
    responsible_employee: Employee | None = None,
    responsible_party: BusinessParty | None = None,
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_REVIEW,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if QualityIssueStatus.ASSIGNED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط مسئله در حال بررسی قابل تخصیص است.")
    _validate_structure(
        organization=organization,
        project=issue.project,
        site=issue.site,
        phase=issue.phase,
        activity=issue.activity,
        daily_report=issue.daily_report,
        responsible_user=responsible_user,
        responsible_employee=responsible_employee,
        responsible_party=responsible_party,
    )
    if not any((responsible_user, responsible_employee, responsible_party)):
        raise ValueError("حداقل یک کاربر، کارمند یا طرف تجاری مسئول تعیین کنید.")
    issue.responsible_user = responsible_user
    issue.responsible_employee = responsible_employee
    issue.responsible_party = responsible_party
    issue.due_date = due_date
    issue.status = QualityIssueStatus.ASSIGNED
    issue.updated_by = actor
    _save_validated(
        issue, "اطلاعات تخصیص مسئله معتبر نیست.", allow_status_transition=True
    )
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_ISSUE_ASSIGNED,
        previous_status=previous_status,
        metadata={"due_date": due_date.isoformat()},
    )
    return issue


@transaction.atomic
def _start_quality_corrective_action_domain(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    corrective_action: str,
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_MANAGE,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if (
        QualityIssueStatus.ACTION_IN_PROGRESS
        not in _STATUS_TRANSITIONS[previous_status]
    ):
        raise ValueError("فقط مسئله تخصیص‌یافته وارد اقدام اصلاحی می‌شود.")
    issue.corrective_action = corrective_action
    issue.status = QualityIssueStatus.ACTION_IN_PROGRESS
    issue.updated_by = actor
    _save_validated(issue, "اقدام اصلاحی معتبر نیست.", allow_status_transition=True)
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_CORRECTIVE_ACTION_STARTED,
        previous_status=previous_status,
    )
    return issue


@transaction.atomic
def _submit_quality_issue_for_verification_domain(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    corrective_action_result: str,
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_MANAGE,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if (
        QualityIssueStatus.AWAITING_VERIFICATION
        not in _STATUS_TRANSITIONS[previous_status]
    ):
        raise ValueError(
            "فقط اقدام اصلاحی در حال انجام قابل ارسال برای راستی‌آزمایی است."
        )
    issue.corrective_action_result = corrective_action_result
    issue.submitted_for_verification_at = timezone.now()
    issue.submitted_for_verification_by = actor
    issue.status = QualityIssueStatus.AWAITING_VERIFICATION
    issue.updated_by = actor
    _save_validated(
        issue,
        "نتیجه اقدام اصلاحی معتبر نیست.",
        allow_status_transition=True,
    )
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_ISSUE_SUBMITTED_FOR_VERIFICATION,
        previous_status=previous_status,
    )
    return issue


@transaction.atomic
def _verify_quality_issue_domain(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    verification_summary: str,
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_VERIFY,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if QualityIssueStatus.VERIFIED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط مسئله در انتظار راستی‌آزمایی قابل تأیید است.")
    issue.verification_summary = verification_summary
    issue.verified_at = timezone.now()
    issue.verified_by = actor
    issue.status = QualityIssueStatus.VERIFIED
    issue.updated_by = actor
    _save_validated(
        issue, "اطلاعات راستی‌آزمایی معتبر نیست.", allow_status_transition=True
    )
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_ISSUE_VERIFIED,
        previous_status=previous_status,
    )
    return issue


@transaction.atomic
def _close_quality_issue_domain(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    closure_summary: str,
) -> QualityIssue:
    issue = _locked_issue(organization=organization, issue_id=issue_id)
    _require_permission(
        organization=organization,
        user=actor,
        permission=BusinessPermissionCode.QUALITY_ISSUES_CLOSE,
        project=issue.project,
        site=issue.site,
    )
    previous_status = issue.status
    if QualityIssueStatus.CLOSED not in _STATUS_TRANSITIONS[previous_status]:
        raise ValueError("فقط مسئله راستی‌آزمایی‌شده قابل بستن است.")
    if issue.review_status != QualityReviewStatus.APPROVED:
        raise ValueError("بستن مسئله مستلزم تأیید جداگانه رکورد است.")
    issue.closure_summary = closure_summary
    issue.closed_at = timezone.now()
    issue.closed_by = actor
    issue.status = QualityIssueStatus.CLOSED
    issue.updated_by = actor
    _save_validated(issue, "جمع‌بندی بستن معتبر نیست.", allow_status_transition=True)
    _record_transition(
        issue=issue,
        actor=actor,
        action=AuditAction.QUALITY_ISSUE_CLOSED,
        previous_status=previous_status,
    )
    return issue


@transaction.atomic
def create_quality_issue(
    *,
    organization: Organization,
    actor: User,
    project: Project,
    issue_number: str,
    identified_at: datetime,
    issue_type: str,
    severity: str,
    description: str,
    specification_reference: str = "",
    site: ProjectSite | None = None,
    phase: ProjectPhase | None = None,
    activity: Activity | None = None,
    daily_report: DailyReport | None = None,
) -> QualityIssue:
    from apps.workflows.runtime import WorkflowConflict

    from .workflow import start_quality_workflow

    issue = _create_quality_issue_domain(
        organization=organization,
        actor=actor,
        project=project,
        issue_number=issue_number,
        identified_at=identified_at,
        issue_type=issue_type,
        severity=severity,
        description=description,
        specification_reference=specification_reference,
        site=site,
        phase=phase,
        activity=activity,
        daily_report=daily_report,
    )
    try:
        start_quality_workflow(organization=organization, issue=issue, actor=actor)
    except WorkflowConflict:
        # An unroutable record retains its approved legacy domain path.
        pass
    return issue


def review_quality_issue(
    *, organization: Organization, actor: User, issue_id: str
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.REPORTED,
        outcome=QualityIssueStatus.UNDER_REVIEW,
        context={},
    )


def assign_quality_issue(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    due_date: date,
    responsible_user: User | None = None,
    responsible_employee: Employee | None = None,
    responsible_party: BusinessParty | None = None,
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.UNDER_REVIEW,
        outcome=QualityIssueStatus.ASSIGNED,
        context={
            "due_date": due_date,
            "responsible_user": responsible_user,
            "responsible_employee": responsible_employee,
            "responsible_party": responsible_party,
        },
    )


def start_quality_corrective_action(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    corrective_action: str,
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.ASSIGNED,
        outcome=QualityIssueStatus.ACTION_IN_PROGRESS,
        context={"corrective_action": corrective_action},
    )


def submit_quality_issue_for_verification(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    corrective_action_result: str,
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.ACTION_IN_PROGRESS,
        outcome=QualityIssueStatus.AWAITING_VERIFICATION,
        context={"corrective_action_result": corrective_action_result},
    )


def verify_quality_issue(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    verification_summary: str,
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.AWAITING_VERIFICATION,
        outcome=QualityIssueStatus.VERIFIED,
        context={"verification_summary": verification_summary},
    )


def close_quality_issue(
    *,
    organization: Organization,
    actor: User,
    issue_id: str,
    closure_summary: str,
) -> QualityIssue:
    from .workflow import perform_quality_transition

    return perform_quality_transition(
        organization=organization,
        actor=actor,
        issue_id=issue_id,
        expected_status=QualityIssueStatus.VERIFIED,
        outcome=QualityIssueStatus.CLOSED,
        context={"closure_summary": closure_summary},
    )
