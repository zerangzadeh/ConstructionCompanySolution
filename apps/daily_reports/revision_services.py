"""Author-owned correction drafts and replay receipts."""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
)
from apps.workflows.runtime import WorkflowConflict, _lock_membership_authority

from .models import DailyReport, DailyReportStatus
from .services import (
    _validate_daily_activity_scope,
    _validate_phase,
    _validate_project,
    _validate_site,
)
from .submission_snapshots import (
    ENTRIES,
    HEADER_FIELDS,
    digest,
    entry_values,
    json_value,
    verify_submission,
)


def lock_report(organization: Organization, report_id: UUID | str) -> DailyReport:
    try:
        return (
            DailyReport.objects.select_for_update(of=("self",))
            .select_related("organization", "project", "site", "phase")
            .get(organization_id=organization.pk, pk=report_id)
        )
    except DailyReport.DoesNotExist as exc:
        raise PermissionDenied("گزارش روزانه در این شرکت یافت نشد.") from exc


def scoped_permission(
    report: DailyReport, actor: User, permission: str
) -> OrganizationMembership:
    # Refresh tenant state even for service callers holding an older Organization.
    organization = Organization.objects.get(pk=report.organization_id)
    _validate_project(organization=organization, project=report.project)
    _validate_site(organization=organization, project=report.project, site=report.site)
    return require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=report.project,
        site=report.site,
        message="مجوز این اقدام در محدوده گزارش وجود ندارد.",
    )


def require_author(
    report: DailyReport, actor: User, *, lock: bool = False
) -> OrganizationMembership:
    if not report.created_by_id or report.created_by_id != actor.pk:
        raise PermissionDenied("فقط نویسنده گزارش می‌تواند نسخه اصلاحی را تغییر دهد.")
    membership = scoped_permission(report, actor, BusinessPermissionCode.DAILY_REPORTS_CORRECT)
    if lock:
        _lock_membership_authority(
            organization=report.organization, membership_id=membership.pk
        )
        scoped_permission(report, actor, BusinessPermissionCode.DAILY_REPORTS_CORRECT)
    scoped_permission(report, actor, BusinessPermissionCode.DAILY_REPORTS_VIEW)
    return membership


def require_correction_draft(report: DailyReport, expected_version: int) -> None:
    if not report.previous_revision_id or report.status != DailyReportStatus.DRAFT:
        raise WorkflowConflict("فقط پیش‌نویس اصلاحی قابل ویرایش است.")
    if type(expected_version) is not int or report.edit_version != expected_version:
        raise WorkflowConflict("نسخه فرم قدیمی است. گزارش را دوباره باز کنید.")


def receipt(
    report: DailyReport, actor: User, key: UUID, action: str, payload: dict
) -> AuditEvent | None:
    if not isinstance(key, UUID):
        raise ValidationError("شناسه درخواست معتبر نیست.")
    event = AuditEvent.objects.filter(
        organization_id=report.organization_id,
        entity_type="daily_report",
        entity_id=str(report.pk),
        actor=actor,
        correlation_id=key,
    ).first()
    if event and (
        event.action != action or event.metadata.get("request_hash") != digest(payload)
    ):
        raise WorkflowConflict("شناسه درخواست با داده دیگری استفاده شده است.")
    return event


def write_receipt(
    report: DailyReport,
    actor: User,
    key: UUID | None,
    action: str,
    payload: dict,
    **metadata,
) -> AuditEvent:
    return record_audit_event(
        organization=report.organization,
        actor=actor,
        action=action,
        entity_type="daily_report",
        entity_id=str(report.pk),
        correlation_id=key,
        metadata={
            "request_hash": digest(payload),
            "project_id": str(report.project_id),
            "site_id": str(report.site_id),
            "revision_number": report.revision_number,
            "submission_hash": report.submission_hash,
            **metadata,
        },
    )


@transaction.atomic
def start_correction(
    *,
    organization: Organization,
    actor: User,
    report_id: UUID | str,
    operation_key: UUID,
) -> DailyReport:
    source = lock_report(organization, report_id)
    require_author(source, actor, lock=True)
    payload = {"action": "create_correction"}
    action = AuditAction.DAILY_REPORT_CORRECTION_CREATED
    previous = receipt(source, actor, operation_key, action, payload)
    if previous:
        return DailyReport.objects.get(
            organization=organization,
            previous_revision=source,
            pk=previous.metadata["successor_id"],
        )
    if source.status != DailyReportStatus.RETURNED:
        raise WorkflowConflict("فقط گزارش بازگشتی قابل اصلاح است.")
    verify_submission(source)
    if DailyReport.objects.filter(previous_revision=source).exists():
        raise WorkflowConflict("نسخه اصلاحی این گزارش قبلاً ایجاد شده است.")
    successor = DailyReport.objects.create(
        organization=source.organization,
        project=source.project,
        site=source.site,
        phase=source.phase,
        reporting_date=source.reporting_date,
        created_by=actor,
        updated_by=actor,
        previous_revision=source,
        revision_number=source.revision_number + 1,
        **{name: getattr(source, name) for name in HEADER_FIELDS},
    )
    copies = {}
    for kind, spec in ENTRIES.items():
        pairs = [
            (
                row.pk,
                spec.model(
                    organization=organization,
                    report=successor,
                    **entry_values(row, spec),
                ),
            )
            for row in getattr(source, spec.relation).order_by("created_at", "pk")
        ]
        spec.model.objects.bulk_create([entry for _, entry in pairs])
        copies[kind] = {str(original): str(entry.pk) for original, entry in pairs}
    write_receipt(
        source,
        actor,
        operation_key,
        action,
        payload,
        successor_id=str(successor.pk),
        before="returned",
        after="draft",
        entry_copies=copies,
    )
    return successor


def _normalize_entry(report, kind, entry):
    activity = getattr(entry, "activity", None)
    if activity:
        _validate_daily_activity_scope(report=report, activity=activity)
    if kind == "materials":
        if entry.quantity <= 0:
            raise ValidationError("مقدار مصالح باید مثبت باشد.")
        if entry.material_id:
            material = entry.material
            if (
                material.organization_id != report.organization_id
                or not material.is_active
                or material.archived_at
            ):
                raise ValidationError("مصالح باید متعلق به همین شرکت و فعال باشد.")
            entry.material_name = material.name
            entry.unit_of_measure = material.unit_of_measure
        if entry.unit_of_measure_id:
            entry.unit = entry.unit_of_measure.symbol
    if kind == "activities" and activity:
        if not entry.description:
            entry.description = activity.name
        if activity.unit_of_measure_id:
            if (
                entry.unit_of_measure_id
                and entry.unit_of_measure_id != activity.unit_of_measure_id
            ):
                raise ValidationError(
                    "واحد باید با واحد اصلی فعالیت مطابقت داشته باشد."
                )
            entry.unit_of_measure = activity.unit_of_measure
    if kind == "labor" and (entry.worker_count < 1 or entry.hours_worked <= 0):
        raise ValidationError("تعداد نیرو و ساعات کار باید مثبت باشد.")
    if kind == "equipment" and entry.hours_used <= 0:
        raise ValidationError("ساعات کارکرد تجهیز باید مثبت باشد.")
    entry.full_clean()


def validate_correction(report: DailyReport) -> None:
    if report.phase_id:
        _validate_phase(
            organization=report.organization, site=report.site, phase=report.phase
        )
    report.full_clean()
    if not report.work_performed.strip():
        raise ValidationError("شرح کارهای انجام‌شده الزامی است.")
    for kind, spec in ENTRIES.items():
        for entry in getattr(report, spec.relation).all():
            before = entry_values(entry, spec)
            _normalize_entry(report, kind, entry)
            if before != entry_values(entry, spec):
                raise ValidationError(
                    "اطلاعات یکی از ردیف‌ها تغییر کرده است. پیش از ارسال آن را بازبینی کنید."
                )


@transaction.atomic
def save_correction(
    *,
    organization: Organization,
    actor: User,
    report_id: UUID | str,
    operation_key: UUID,
    expected_version: int,
    kind: str,
    values: dict,
    entry_id: UUID | None = None,
    remove: bool = False,
) -> int:
    report = lock_report(organization, report_id)
    require_author(report, actor, lock=True)
    if kind == "header":
        fields = HEADER_FIELDS
        if entry_id or remove:
            raise ValidationError("نوع تغییر گزارش معتبر نیست.")
    else:
        spec = ENTRIES.get(kind)
        if spec is None or (remove and not entry_id):
            raise ValidationError("نوع ردیف گزارش معتبر نیست.")
        fields = spec.fields
        if not entry_id:
            scoped_permission(report, actor, spec.permission)
    if set(values) != (set() if remove else set(fields)):
        raise ValidationError("فیلدهای تغییر گزارش معتبر نیست.")
    normalized = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in values.items()
    }
    payload = {
        "kind": kind,
        "values": {key: json_value(value) for key, value in normalized.items()},
        "edit_version": expected_version,
        "entry_id": json_value(entry_id),
        "remove": remove,
    }
    action = AuditAction.DAILY_REPORT_CORRECTION_SAVED
    previous = receipt(report, actor, operation_key, action, payload)
    if previous:
        return previous.metadata["result_edit_version"]
    require_correction_draft(report, expected_version)
    before = {}
    changed = None
    if kind == "header":
        before = {name: getattr(report, name) for name in fields}
        for name, value in normalized.items():
            setattr(report, name, value)
        if not report.work_performed:
            raise ValidationError("شرح کارهای انجام‌شده الزامی است.")
    else:
        if entry_id:
            try:
                entry = spec.model.objects.get(
                    report=report, organization=organization, pk=entry_id
                )
            except spec.model.DoesNotExist as exc:
                raise PermissionDenied("ردیف متعلق به این نسخه نیست.") from exc
            before = {
                key: json_value(value)
                for key, value in entry_values(entry, spec).items()
            }
        else:
            entry = spec.model(
                report=report, organization=organization, created_by=actor
            )
        changed = str(entry.pk)
        if remove:
            entry.delete()
        else:
            for name, value in normalized.items():
                setattr(entry, name, value)
            _normalize_entry(report, kind, entry)
            entry.save()
    report.edit_version += 1
    report.updated_by = actor
    report.save(
        update_fields=[
            "edit_version",
            "updated_by",
            "updated_at",
            *(fields if kind == "header" else ()),
        ]
    )
    write_receipt(
        report,
        actor,
        operation_key,
        action,
        payload,
        kind=kind,
        entry_id=changed,
        prior_edit_version=expected_version,
        result_edit_version=report.edit_version,
        operation="remove" if remove else "save",
        previous_value_hash=digest(before),
    )
    return report.edit_version
