"""PD-WC-D02: explicit approved Timesheet-to-Payroll quantity mapping.

Mapping lives in immutable PayrollRule.evidence['timesheet_input_mapping']:
{'version': 1, 'quantity_unit': 'minute' | 'hour'}.
Only recorded approved minutes are consumed (1 minute or 1/60 hour). This is
not a payable-hours, premium, attendance, rate or statutory interpretation.
Mixed project/site sheets and partial-period inference are unsupported.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.timekeeping.models import Timesheet, TimesheetEntry, TimesheetState

from .models import (
    CalculationMethod,
    ConfigurationStatus,
    EmploymentPayConfiguration,
    PayrollInput,
    PayrollInputSource,
    PayrollRule,
    PayrollRun,
    PayrollRunStatus,
    RateSource,
)

PRODUCER = "payroll.approved_timesheet.v1"


def _source(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    timesheet: Timesheet,
    lock: bool = False,
) -> tuple[Timesheet, list[TimesheetEntry]]:
    query = Timesheet.objects.filter(organization=organization)
    if lock:
        query = query.select_for_update()
    try:
        sheet = query.get(pk=timesheet.pk)
    except Timesheet.DoesNotExist as exc:
        raise PermissionDenied("منبع کارکرد در این شرکت مجاز نیست.") from exc
    if (
        sheet.state != TimesheetState.APPROVED
        or sheet.employee.organization_id != organization.pk
        or not sheet.reviews.filter(
            organization=organization, decision="approved"
        ).exists()
        or sheet.period_start != run.period.starts_on
        or sheet.period_end != run.period.ends_on
        or not run.employee_results.filter(employee_id=sheet.employee_id).exists()
        or sheet.superseded_by.filter(state=TimesheetState.APPROVED).exists()
    ):
        raise ValidationError("نسخه تأییدشده جاری با کارمند و کل دوره اجرا لازم است.")
    entries = list(sheet.entries.select_related("project", "site").order_by("pk"))
    if not entries or sum(e.minutes for e in entries) != sheet.declared_minutes:
        raise ValidationError("جمع ردیف‌های کارکرد باید با مقدار تأییدشده یکسان باشد.")
    contexts = {(e.project_id, e.site_id) for e in entries}
    if len(contexts) != 1:
        raise ValidationError(
            "کارکرد چندپروژه‌ای یا چندکارگاهی در این نگاشت پشتیبانی نمی‌شود."
        )
    for entry in entries:
        if (
            entry.organization_id != organization.pk
            or entry.project.organization_id != organization.pk
            or not sheet.period_start <= entry.work_date <= sheet.period_end
            or (
                entry.site_id
                and (
                    entry.site.organization_id != organization.pk
                    or entry.site.project_id != entry.project_id
                )
            )
        ):
            raise ValidationError("ردیف کارکرد با شرکت، پروژه یا دوره سازگار نیست.")
        require_business_permission(
            user=actor,
            organization=organization,
            permission=BusinessPermissionCode.PAYROLL_PREPARE,
            project=entry.project,
            site=entry.site,
            message="دامنه کارکرد برای آماده‌سازی حقوق مجاز نیست.",
        )
    return sheet, entries


def eligible_timesheets(
    *,
    organization: Organization,
    actor: User | None,
    run: PayrollRun,
) -> QuerySet[Timesheet]:
    """Minimal approved-source projection, authorized by Payroll preparation scope."""
    query = Timesheet.objects.filter(
        organization=organization,
        state=TimesheetState.APPROVED,
        employee_id__in=run.employee_results.values("employee_id"),
        period_start=run.period.starts_on,
        period_end=run.period.ends_on,
    )
    if actor is None:
        return query.none()
    eligible = []
    for sheet in query:
        try:
            _source(organization=organization, actor=actor, run=run, timesheet=sheet)
        except (PermissionDenied, ValidationError):
            continue
        eligible.append(sheet.pk)
    return query.filter(pk__in=eligible).select_related("employee")


def _derive(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    timesheet: Timesheet,
    rule: PayrollRule,
    lock: bool = False,
) -> tuple[Timesheet, TimesheetEntry, Decimal, dict[str, Any]]:
    from .services import _applicable_rules

    sheet, entries = _source(
        organization=organization,
        actor=actor,
        run=run,
        timesheet=timesheet,
        lock=lock,
    )
    try:
        rule = PayrollRule.objects.get(pk=rule.pk, organization=organization)
    except PayrollRule.DoesNotExist as exc:
        raise PermissionDenied("قاعده حقوق در این شرکت مجاز نیست.") from exc
    mapping = (
        rule.evidence.get("timesheet_input_mapping", {})
        if isinstance(rule.evidence, dict)
        else {}
    )
    if (
        rule.method != CalculationMethod.QUANTITY_TIMES_RATE
        or not isinstance(mapping, dict)
        or mapping.get("version") != 1
        or mapping.get("quantity_unit") not in {"minute", "hour"}
    ):
        raise ValidationError("نگاشت صریح واحد کارکرد در نسخه قاعده لازم است.")
    configuration = (
        EmploymentPayConfiguration.objects.filter(
            organization=organization,
            employee=sheet.employee,
            status__in=[ConfigurationStatus.ACTIVE, ConfigurationStatus.RETIRED],
            effective_from__lte=run.period.ends_on,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=run.period.ends_on))
        .first()
    )
    if configuration is None or rule not in _applicable_rules(
        organization=organization,
        configuration=configuration,
        as_of=run.period.ends_on,
    ):
        raise ValidationError("قاعده و پیکربندی مؤثر پرداخت با کارکرد سازگار نیستند.")
    first = entries[0]
    if (
        (configuration.project_id and configuration.project_id != first.project_id)
        or (configuration.site_id and configuration.site_id != first.site_id)
        or (rule.project_id and rule.project_id != first.project_id)
        or (rule.site_id and rule.site_id != first.site_id)
        or (
            rule.rate_source == RateSource.EMPLOYMENT
            and configuration.rate_unit != mapping["quantity_unit"]
        )
    ):
        raise ValidationError("واحد نرخ یا دامنه قاعده/پیکربندی با کارکرد یکسان نیست.")
    quantity = Decimal(sheet.declared_minutes)
    if mapping["quantity_unit"] == "hour":
        quantity /= Decimal(60)
    # PayrollInput has eight decimal places; no silent quantity rounding.
    if quantity != quantity.quantize(Decimal("0.00000001")):
        raise ValidationError(
            "تبدیل مقدار به هشت رقم اعشار دقیق نیست؛ نگاشت دقیقه لازم است."
        )
    snapshot = {
        "producer": PRODUCER,
        "source_id": str(sheet.pk),
        "revision": sheet.revision,
        "status": sheet.state,
        "employee_id": str(sheet.employee_id),
        "period_start": sheet.period_start.isoformat(),
        "period_end": sheet.period_end.isoformat(),
        "declared_minutes": sheet.declared_minutes,
        "rule_id": str(rule.pk),
        "rule_version": rule.version,
        "employment_configuration_id": str(configuration.pk),
        "mapping": mapping,
        "quantity": str(quantity),
        "entries": [
            {
                "id": str(e.pk),
                "work_date": e.work_date.isoformat(),
                "minutes": e.minutes,
                "project_id": str(e.project_id),
                "site_id": str(e.site_id) if e.site_id else None,
                "activity_id": str(e.activity_id) if e.activity_id else None,
            }
            for e in entries
        ],
    }
    review = sheet.reviews.filter(
        organization=organization, decision="approved"
    ).latest("created_at")
    snapshot["approval"] = {
        "id": str(review.pk),
        "reviewer_id": str(review.reviewer_id),
        "reviewed_at": review.created_at.isoformat(),
    }
    snapshot["digest"] = hashlib.sha256(
        json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return sheet, first, quantity, snapshot


@transaction.atomic
def record_timesheet_input(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    timesheet: Timesheet,
    rule: PayrollRule,
) -> PayrollInput:
    from .services import record_input

    run = (
        PayrollRun.objects.select_for_update()
        .select_related("period")
        .get(
            pk=run.pk,
            organization=organization,
        )
    )
    if run.status != PayrollRunStatus.DRAFT:
        raise ValidationError("فقط ورودی اجرای پیش‌نویس قابل ثبت است.")
    sheet, entry, quantity, snapshot = _derive(
        organization=organization,
        actor=actor,
        run=run,
        timesheet=timesheet,
        rule=rule,
        lock=True,
    )
    return record_input(
        organization=organization,
        actor=actor,
        run=run,
        employee=sheet.employee,
        rule=rule,
        quantity=quantity,
        source_type=PayrollInputSource.APPROVED_TIMESHEET,
        source_reference=str(sheet.pk),
        source_version=str(sheet.revision),
        source_status=sheet.state,
        source_payload=snapshot,
        project=entry.project,
        site=entry.site,
    )


def validate_timesheet_input(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    payroll_input: PayrollInput,
) -> None:
    """Recheck source and mapping under the run lock before snapshot finalization."""
    try:
        sheet = Timesheet.objects.get(
            pk=payroll_input.source_reference, organization=organization
        )
    except (Timesheet.DoesNotExist, ValueError, ValidationError) as exc:
        raise ValidationError("منبع کارکرد ورودی حقوق معتبر نیست.") from exc
    _, entry, quantity, snapshot = _derive(
        organization=organization,
        actor=actor,
        run=run,
        timesheet=sheet,
        rule=payroll_input.rule,
        lock=True,
    )
    if (
        payroll_input.source_payload != snapshot
        or payroll_input.quantity != quantity
        or payroll_input.source_version != str(sheet.revision)
        or payroll_input.source_status != sheet.state
        or payroll_input.employee_id != sheet.employee_id
        or payroll_input.project_id != entry.project_id
        or payroll_input.site_id != entry.site_id
    ):
        raise ValidationError("منبع یا نگاشت ورودی کارکرد پس از ثبت تغییر کرده است.")
