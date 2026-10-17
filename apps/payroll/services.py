from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounting.policy_calculations import (
    AccountingRoundingPolicy,
    MoneyPrecisionPolicy,
    accounting_rounding_policy_from_version,
    money_precision_policy_from_version,
    resolve_monetary_policies,
    round_final_monetary_amount,
)
from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.projects.models import Project, ProjectSite
from apps.workforce.models import Employee
from core.identifiers import canonicalize_upper_identifier

from .models import (
    CalculationMethod,
    ComponentKind,
    ConfigurationStatus,
    EmploymentPayConfiguration,
    PayrollAdjustment,
    PayrollComponent,
    PayrollException,
    PayrollExceptionSeverity,
    PayrollInput,
    PayrollInputSnapshot,
    PayrollPeriod,
    PayrollPeriodStatus,
    PayrollResultLine,
    PayrollReversal,
    PayrollRule,
    PayrollRun,
    PayrollRunEmployee,
    PayrollRunKind,
    PayrollRunStatus,
    Payslip,
    RateSource,
    ResultStatus,
    RuleStatus,
)

INTERMEDIATE_QUANTUM = Decimal("0.00000001")
FINAL_SOURCE_STATUSES = frozenset({"approved", "final"})
PAYROLL_MONETARY_POLICY_CONSUMER = "payroll.run.lock"
CORE_STATUTORY_GATE_MESSAGE = (
    "این رفتار به مرجع قانونی مالیات یا بیمه نیاز دارد و تا P7-S23–S28 فعال نیست."
)


def _money(
    value: Decimal,
    *,
    precision: MoneyPrecisionPolicy,
    rounding: AccountingRoundingPolicy,
) -> Decimal:
    return round_final_monetary_amount(
        value, precision=precision, rounding=rounding
    )


def _intermediate(value: Decimal) -> Decimal:
    return value.quantize(INTERMEDIATE_QUANTUM, rounding=ROUND_HALF_UP)


def _monetary_policy_snapshot(
    *,
    currency: str,
    precision: MoneyPrecisionPolicy,
    rounding: AccountingRoundingPolicy,
) -> dict[str, Any]:
    return {
        "currency": currency,
        "money_scale": precision.money_scale,
        "intermediate_calculation_scale": precision.intermediate_calculation_scale,
        "preserve_unrounded_intermediates": precision.preserve_unrounded_intermediates,
        "final_quantum": format(Decimal(1).scaleb(-precision.money_scale), "f"),
        "rounding_method": rounding.method,
        "rounding_output_boundary": rounding.output_boundary,
        "rounding_tie_behavior": rounding.tie_behavior,
        "precision_policy_id": str(precision.version.pk),
        "precision_policy_version": precision.version.version,
        "rounding_policy_id": str(rounding.version.pk),
        "rounding_policy_version": rounding.version.version,
    }


def _locked_monetary_policies(
    run: PayrollRun,
) -> tuple[MoneyPrecisionPolicy, AccountingRoundingPolicy]:
    if not run.precision_policy_version_id or not run.rounding_policy_version_id:
        raise ValidationError("اجرای قفل‌شده باید سیاست دقت و گردکردن پول را داشته باشد.")
    precision = money_precision_policy_from_version(
        run.precision_policy_version,
        consumer=PAYROLL_MONETARY_POLICY_CONSUMER,
    )
    rounding = accounting_rounding_policy_from_version(
        run.rounding_policy_version,
        consumer=PAYROLL_MONETARY_POLICY_CONSUMER,
    )
    snapshot = _monetary_policy_snapshot(
        currency=run.currency, precision=precision, rounding=rounding
    )
    if run.monetary_policy_snapshot != snapshot:
        raise ValidationError("تصویر سیاست پول اجرای حقوق با نسخه‌های پین‌شده ناسازگار است.")
    return precision, rounding


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(
        _json_value(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _scope(
    permission: BusinessPermissionCode,
    *,
    organization: Organization,
    actor: User,
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> None:
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=project,
        site=site,
        message="مجوز صریح حقوق و دستمزد یا دامنه لازم را ندارید.",
    )


def _ensure_tenant(organization: Organization, **objects: Any) -> None:
    errors = {
        name: "رکورد مرتبط باید متعلق به همین شرکت باشد."
        for name, obj in objects.items()
        if obj is not None and getattr(obj, "organization_id", None) != organization.pk
    }
    if errors:
        raise ValidationError(errors)


def _audit(
    *,
    action: str,
    organization: Organization,
    actor: User,
    entity: Any,
    metadata: dict[str, Any] | None = None,
) -> None:
    record_audit_event(
        action=action,
        organization=organization,
        actor=actor,
        entity_type=entity._meta.label_lower,
        entity_id=str(entity.pk),
        metadata=_json_value(metadata or {}),
    )


@transaction.atomic
def create_employment_configuration(
    *,
    organization: Organization,
    actor: User,
    employee: Employee,
    pay_model: str,
    base_rate: Decimal,
    rate_unit: str,
    effective_from: date,
    source_reference: str,
    evidence: dict[str, Any] | None = None,
    effective_to: date | None = None,
    project: Project | None = None,
    site: ProjectSite | None = None,
    predecessor: EmploymentPayConfiguration | None = None,
) -> EmploymentPayConfiguration:
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(
        organization,
        employee=employee,
        project=project,
        site=site,
        predecessor=predecessor,
    )
    Employee.objects.select_for_update().get(pk=employee.pk)
    latest = (
        EmploymentPayConfiguration.objects.select_for_update()
        .filter(organization=organization, employee=employee)
        .order_by("-version")
        .first()
    )
    if predecessor is None:
        predecessor = latest
    elif latest and predecessor.pk != latest.pk:
        raise ValidationError({"predecessor": "نسخه پیشین باید آخرین نسخه کارمند باشد."})
    configuration = EmploymentPayConfiguration.objects.create(
        organization=organization,
        employee=employee,
        version=(latest.version + 1) if latest else 1,
        predecessor=predecessor,
        pay_model=pay_model,
        base_rate=Decimal(base_rate),
        rate_unit=rate_unit,
        currency=organization.settings.currency,
        project=project,
        site=site,
        effective_from=effective_from,
        effective_to=effective_to,
        source_reference=source_reference,
        evidence=evidence or {},
        created_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_CONFIGURATION_RECORDED,
        organization=organization,
        actor=actor,
        entity=configuration,
        metadata={"employee_id": str(employee.pk), "version": configuration.version},
    )
    return configuration


@transaction.atomic
def activate_employment_configuration(
    *,
    organization: Organization,
    actor: User,
    configuration: EmploymentPayConfiguration,
) -> EmploymentPayConfiguration:
    configuration = EmploymentPayConfiguration.objects.select_for_update().get(
        pk=configuration.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=configuration.project,
        site=configuration.site,
    )
    if configuration.status == ConfigurationStatus.ACTIVE:
        return configuration
    if configuration.status != ConfigurationStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قابل فعال‌سازی است.")
    overlaps = EmploymentPayConfiguration.objects.select_for_update().filter(
        employee=configuration.employee,
        status__in=[ConfigurationStatus.ACTIVE, ConfigurationStatus.RETIRED],
        effective_from__lte=configuration.effective_to or date.max,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=configuration.effective_from))
    if overlaps.exists():
        raise ValidationError("نسخه فعال هم‌پوشان وجود دارد؛ ابتدا پایان آن را ثبت کنید.")
    configuration.status = ConfigurationStatus.ACTIVE
    configuration.activated_by = actor
    configuration.activated_at = timezone.now()
    configuration.save(update_fields=["status", "activated_by", "activated_at", "updated_at"])
    _audit(
        action=AuditAction.PAYROLL_CONFIGURATION_ACTIVATED,
        organization=organization,
        actor=actor,
        entity=configuration,
        metadata={"employee_id": str(configuration.employee_id), "version": configuration.version},
    )
    return configuration


@transaction.atomic
def retire_employment_configuration(
    *,
    organization: Organization,
    actor: User,
    configuration: EmploymentPayConfiguration,
    effective_to: date,
) -> EmploymentPayConfiguration:
    configuration = EmploymentPayConfiguration.objects.select_for_update().get(
        pk=configuration.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=configuration.project,
        site=configuration.site,
    )
    if configuration.status != ConfigurationStatus.ACTIVE:
        raise ValidationError("فقط نسخه فعال قابل بازنشستگی است.")
    if effective_to < configuration.effective_from:
        raise ValidationError("تاریخ پایان پیش از تاریخ شروع است.")
    EmploymentPayConfiguration.objects.filter(pk=configuration.pk).update(
        status=ConfigurationStatus.RETIRED, effective_to=effective_to
    )
    configuration.refresh_from_db()
    _audit(
        action=AuditAction.PAYROLL_CONFIGURATION_RETIRED,
        organization=organization,
        actor=actor,
        entity=configuration,
        metadata={"effective_to": effective_to},
    )
    return configuration


@transaction.atomic
def create_component(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    kind: str,
    net_effect: str,
    description: str = "",
    is_statutory_reserved: bool = False,
) -> PayrollComponent:
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
    )
    PayrollComponent.objects.select_for_update().filter(
        organization=organization, code__iexact=code
    ).exists()
    component = PayrollComponent.objects.create(
        organization=organization,
        code=code,
        name=name,
        kind=kind,
        net_effect=net_effect,
        description=description.strip(),
        is_statutory_reserved=is_statutory_reserved,
        created_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_COMPONENT_CONFIGURED,
        organization=organization,
        actor=actor,
        entity=component,
        metadata={"code": component.code, "kind": component.kind},
    )
    return component


@transaction.atomic
def create_rule(
    *,
    organization: Organization,
    actor: User,
    component: PayrollComponent,
    code: str,
    name: str,
    sequence: int,
    method: str,
    effective_from: date,
    source_reference: str,
    fixed_amount: Decimal | None = None,
    rate_source: str = RateSource.RULE,
    rate: Decimal | None = None,
    percentage: Decimal | None = None,
    basis_component: PayrollComponent | None = None,
    applicable_pay_models: list[str] | None = None,
    project: Project | None = None,
    site: ProjectSite | None = None,
    effective_to: date | None = None,
    evidence: dict[str, Any] | None = None,
    requires_statutory_authority: bool = False,
    predecessor: PayrollRule | None = None,
) -> PayrollRule:
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(
        organization,
        component=component,
        basis_component=basis_component,
        project=project,
        site=site,
        predecessor=predecessor,
    )
    latest = (
        PayrollRule.objects.select_for_update()
        .filter(organization=organization, code__iexact=code)
        .order_by("-version")
        .first()
    )
    if predecessor is None:
        predecessor = latest
    elif latest and predecessor.pk != latest.pk:
        raise ValidationError({"predecessor": "نسخه پیشین باید آخرین نسخه قاعده باشد."})
    rule = PayrollRule.objects.create(
        organization=organization,
        component=component,
        code=code,
        version=(latest.version + 1) if latest else 1,
        predecessor=predecessor,
        name=name,
        sequence=sequence,
        method=method,
        fixed_amount=fixed_amount,
        rate_source=rate_source,
        rate=rate,
        percentage=percentage,
        basis_component=basis_component,
        applicable_pay_models=applicable_pay_models or [],
        project=project,
        site=site,
        effective_from=effective_from,
        effective_to=effective_to,
        source_reference=source_reference,
        evidence=evidence or {},
        requires_statutory_authority=requires_statutory_authority,
        created_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_RULE_RECORDED,
        organization=organization,
        actor=actor,
        entity=rule,
        metadata={"code": rule.code, "version": rule.version},
    )
    return rule


@transaction.atomic
def activate_rule(
    *, organization: Organization, actor: User, rule: PayrollRule
) -> PayrollRule:
    rule = PayrollRule.objects.select_for_update().select_related("component").get(
        pk=rule.pk, organization=organization
    )
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=rule.project,
        site=rule.site,
    )
    if rule.status == RuleStatus.ACTIVE:
        return rule
    if rule.status != RuleStatus.DRAFT:
        raise ValidationError("فقط نسخه پیش‌نویس قاعده قابل فعال‌سازی است.")
    if rule.requires_statutory_authority or rule.component.is_statutory_reserved:
        raise ValidationError(CORE_STATUTORY_GATE_MESSAGE)
    overlaps = PayrollRule.objects.select_for_update().filter(
        component=rule.component,
        status__in=[RuleStatus.ACTIVE, RuleStatus.RETIRED],
        effective_from__lte=rule.effective_to or date.max,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=rule.effective_from))
    if overlaps.exists():
        raise ValidationError("نسخه فعال هم‌پوشان برای این جزء وجود دارد.")
    rule.status = RuleStatus.ACTIVE
    rule.activated_by = actor
    rule.activated_at = timezone.now()
    rule.save(update_fields=["status", "activated_by", "activated_at", "updated_at"])
    _audit(
        action=AuditAction.PAYROLL_RULE_ACTIVATED,
        organization=organization,
        actor=actor,
        entity=rule,
        metadata={"code": rule.code, "version": rule.version},
    )
    return rule


@transaction.atomic
def retire_rule(
    *, organization: Organization, actor: User, rule: PayrollRule, effective_to: date
) -> PayrollRule:
    rule = PayrollRule.objects.select_for_update().get(pk=rule.pk, organization=organization)
    _scope(
        BusinessPermissionCode.PAYROLL_CONFIGURATION_MANAGE,
        organization=organization,
        actor=actor,
        project=rule.project,
        site=rule.site,
    )
    if rule.status != RuleStatus.ACTIVE:
        raise ValidationError("فقط قاعده فعال قابل بازنشستگی است.")
    if effective_to < rule.effective_from:
        raise ValidationError("تاریخ پایان پیش از شروع قاعده است.")
    PayrollRule.objects.filter(pk=rule.pk).update(
        status=RuleStatus.RETIRED, effective_to=effective_to
    )
    rule.refresh_from_db()
    _audit(
        action=AuditAction.PAYROLL_RULE_RETIRED,
        organization=organization,
        actor=actor,
        entity=rule,
        metadata={"effective_to": effective_to},
    )
    return rule


@transaction.atomic
def create_period(
    *,
    organization: Organization,
    actor: User,
    code: str,
    name: str,
    starts_on: date,
    ends_on: date,
    cutoff_at,
) -> PayrollPeriod:
    _scope(
        BusinessPermissionCode.PAYROLL_PREPARE,
        organization=organization,
        actor=actor,
    )
    if PayrollPeriod.objects.select_for_update().filter(
        organization=organization,
        status__in=[
            PayrollPeriodStatus.OPEN,
            PayrollPeriodStatus.LOCKED,
            PayrollPeriodStatus.FINALIZED,
        ],
        starts_on__lte=ends_on,
        ends_on__gte=starts_on,
    ).exists():
        raise ValidationError("دوره باز/قفل/قطعی هم‌پوشان وجود دارد.")
    period = PayrollPeriod.objects.create(
        organization=organization,
        code=code,
        name=name,
        starts_on=starts_on,
        ends_on=ends_on,
        cutoff_at=cutoff_at,
        created_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_PERIOD_CREATED,
        organization=organization,
        actor=actor,
        entity=period,
        metadata={"starts_on": starts_on, "ends_on": ends_on},
    )
    return period


@transaction.atomic
def create_run(
    *,
    organization: Organization,
    actor: User,
    period: PayrollPeriod,
    code: str,
    idempotency_key: str,
    employees: Iterable[Employee],
    kind: str = PayrollRunKind.REGULAR,
    predecessor: PayrollRun | None = None,
    replaces: PayrollRun | None = None,
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_PREPARE, organization=organization, actor=actor)
    _ensure_tenant(
        organization, period=period, predecessor=predecessor, replaces=replaces
    )
    period = PayrollPeriod.objects.select_for_update().get(
        pk=period.pk, organization=organization
    )
    if kind == PayrollRunKind.REGULAR and period.status != PayrollPeriodStatus.OPEN:
        raise ValidationError("اجرای عادی فقط در دوره باز ساخته می‌شود.")
    existing = PayrollRun.objects.select_for_update().filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if (
            existing.period_id,
            existing.code,
            existing.kind,
            existing.replaces_id,
        ) != (period.pk, canonicalize_upper_identifier(code), kind, getattr(replaces, "pk", None)):
            raise ValidationError("کلید idempotency با درخواست دیگری استفاده شده است.")
        return existing
    employee_list = list(dict.fromkeys(employees))
    if not employee_list:
        raise ValidationError("حداقل یک کارمند باید صریحاً به اجرا افزوده شود.")
    for employee in employee_list:
        _ensure_tenant(organization, employee=employee)
    try:
        with transaction.atomic():
            run = PayrollRun.objects.create(
                organization=organization,
                period=period,
                code=code,
                kind=kind,
                idempotency_key=idempotency_key,
                predecessor=predecessor,
                replaces=replaces,
                currency=organization.settings.currency,
                created_by=actor,
            )
    except IntegrityError:
        existing = PayrollRun.objects.filter(
            organization=organization, idempotency_key=idempotency_key
        ).first()
        if existing and (
            existing.period_id,
            existing.code,
            existing.kind,
            existing.replaces_id,
        ) == (
            period.pk,
            canonicalize_upper_identifier(code),
            kind,
            getattr(replaces, "pk", None),
        ):
            return existing
        raise
    predecessor_results = {
        item.employee_id: item
        for item in (
            replaces.employee_results.all() if replaces is not None else []
        )
    }
    for employee in employee_list:
        prior = predecessor_results.get(employee.pk)
        PayrollRunEmployee.objects.create(
            organization=organization,
            run=run,
            employee=employee,
            predecessor_result=prior,
        )
    _audit(
        action=AuditAction.PAYROLL_RUN_CREATED,
        organization=organization,
        actor=actor,
        entity=run,
        metadata={"kind": kind, "employee_count": len(employee_list)},
    )
    return run


@transaction.atomic
def record_input(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    employee: Employee,
    rule: PayrollRule,
    quantity: Decimal,
    source_type: str,
    source_reference: str,
    source_version: str,
    source_status: str,
    source_payload: dict[str, Any],
    project: Project | None = None,
    site: ProjectSite | None = None,
) -> PayrollInput:
    _scope(
        BusinessPermissionCode.PAYROLL_PREPARE,
        organization=organization,
        actor=actor,
        project=project,
        site=site,
    )
    _ensure_tenant(
        organization,
        run=run,
        employee=employee,
        rule=rule,
        project=project,
        site=site,
    )
    run = PayrollRun.objects.select_for_update().get(pk=run.pk, organization=organization)
    if run.status != PayrollRunStatus.DRAFT:
        raise ValidationError("ورودی اجرای قفل‌شده قابل تغییر نیست.")
    if not run.employee_results.filter(employee=employee).exists():
        raise ValidationError({"employee": "کارمند در این اجرای حقوق ثبت نشده است."})
    if source_status not in FINAL_SOURCE_STATUSES:
        raise ValidationError({"source_status": "فقط واقعیت تأیید یا قطعی قابل مصرف است."})
    item, _ = PayrollInput.objects.update_or_create(
        run=run,
        employee=employee,
        rule=rule,
        defaults={
            "organization": organization,
            "quantity": Decimal(quantity),
            "source_type": source_type,
            "source_reference": source_reference,
            "source_version": source_version,
            "source_status": source_status,
            "source_payload": _json_value(source_payload),
            "project": project,
            "site": site,
            "recorded_by": actor,
        },
    )
    _audit(
        action=AuditAction.PAYROLL_INPUT_RECORDED,
        organization=organization,
        actor=actor,
        entity=item,
        metadata={"run_id": str(run.pk), "employee_id": str(employee.pk)},
    )
    return item


@transaction.atomic
def record_adjustment(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    employee: Employee,
    component: PayrollComponent,
    kind: str,
    amount: Decimal,
    effective_on: date,
    source_reference: str,
    reason: str,
    source_payload: dict[str, Any] | None = None,
    original_result: PayrollRunEmployee | None = None,
) -> PayrollAdjustment:
    _scope(BusinessPermissionCode.PAYROLL_ADJUST, organization=organization, actor=actor)
    _ensure_tenant(
        organization,
        run=run,
        employee=employee,
        component=component,
        original_result=original_result,
    )
    run = PayrollRun.objects.select_for_update().get(pk=run.pk, organization=organization)
    if not run.employee_results.filter(employee=employee).exists():
        raise ValidationError({"employee": "کارمند در اجرای تعدیلی ثبت نشده است."})
    adjustment = PayrollAdjustment.objects.create(
        organization=organization,
        run=run,
        employee=employee,
        component=component,
        original_result=original_result,
        kind=kind,
        amount=Decimal(amount),
        effective_on=effective_on,
        source_reference=source_reference,
        source_payload=_json_value(source_payload or {}),
        reason=reason,
        recorded_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_ADJUSTMENT_RECORDED,
        organization=organization,
        actor=actor,
        entity=adjustment,
        metadata={
            "run_id": str(run.pk),
            "employee_id": str(employee.pk),
            "kind": kind,
        },
    )
    return adjustment


def _applicable_rules(
    *, organization: Organization, configuration: EmploymentPayConfiguration, as_of: date
) -> list[PayrollRule]:
    candidates = (
        PayrollRule.objects.filter(
            organization=organization,
            status__in=[RuleStatus.ACTIVE, RuleStatus.RETIRED],
            effective_from__lte=as_of,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related("component", "basis_component")
        .order_by("sequence", "code", "version")
    )
    rules = []
    for rule in candidates:
        if rule.requires_statutory_authority or rule.component.is_statutory_reserved:
            continue
        if rule.applicable_pay_models and configuration.pay_model not in rule.applicable_pay_models:
            continue
        if rule.project_id and rule.project_id != configuration.project_id:
            continue
        if rule.site_id and rule.site_id != configuration.site_id:
            continue
        rules.append(rule)
    return rules


def _snapshot_spec(
    *,
    result: PayrollRunEmployee,
    configuration: EmploymentPayConfiguration,
    rule: PayrollRule,
    payroll_input: PayrollInput | None,
) -> dict[str, Any]:
    if rule.method == CalculationMethod.FIXED_AMOUNT:
        quantity = None
        rate = None
        fixed_value = rule.fixed_amount
        source_type = "rule"
        source_reference = rule.source_reference
        source_version = str(rule.version)
        source_payload = rule.evidence
    elif rule.method == CalculationMethod.QUANTITY_TIMES_RATE:
        if payroll_input is None:
            raise ValidationError("ورودی مقداری موردنیاز وجود ندارد.")
        quantity = payroll_input.quantity
        rate = configuration.base_rate if rule.rate_source == RateSource.EMPLOYMENT else rule.rate
        fixed_value = None
        source_type = payroll_input.source_type
        source_reference = payroll_input.source_reference
        source_version = payroll_input.source_version
        source_payload = payroll_input.source_payload
    else:
        quantity = None
        rate = rule.percentage
        fixed_value = None
        source_type = "derived_component"
        source_reference = rule.source_reference
        source_version = str(rule.version)
        source_payload = rule.evidence
    payload = {
        "employee_id": str(result.employee_id),
        "employment_configuration_id": str(configuration.pk),
        "employment_version": configuration.version,
        "pay_model": configuration.pay_model,
        "component_id": str(rule.component_id),
        "component_code": rule.component.code,
        "component_name": rule.component.name,
        "component_kind": rule.component.kind,
        "net_effect": rule.component.net_effect,
        "rule_id": str(rule.pk),
        "rule_code": rule.code,
        "rule_version": rule.version,
        "method": rule.method,
        "rate_source": rule.rate_source,
        "basis_component_id": str(rule.basis_component_id) if rule.basis_component_id else None,
        "percentage": rule.percentage,
        "quantity": quantity,
        "rate": rate,
        "fixed_value": fixed_value,
        "source_type": source_type,
        "source_reference": source_reference,
        "source_version": source_version,
        "source_payload": source_payload,
    }
    return {
        "result": result,
        "configuration": configuration,
        "component": rule.component,
        "rule": rule,
        "adjustment": None,
        "sequence": rule.sequence,
        "quantity": quantity,
        "rate": rate,
        "basis": None,
        "fixed_value": fixed_value,
        "rule_version": rule.version,
        "employment_version": configuration.version,
        "source_type": source_type,
        "source_reference": source_reference,
        "source_version": source_version,
        "source_payload": source_payload,
        "snapshot_payload": _json_value(payload),
        "digest": _digest(payload),
    }


def _adjustment_snapshot_spec(
    *,
    result: PayrollRunEmployee,
    configuration: EmploymentPayConfiguration,
    adjustment: PayrollAdjustment,
    sequence: int,
) -> dict[str, Any]:
    payload = {
        "employee_id": str(result.employee_id),
        "employment_configuration_id": str(configuration.pk),
        "employment_version": configuration.version,
        "component_id": str(adjustment.component_id),
        "component_code": adjustment.component.code,
        "component_name": adjustment.component.name,
        "component_kind": adjustment.component.kind,
        "net_effect": adjustment.component.net_effect,
        "adjustment_id": str(adjustment.pk),
        "adjustment_kind": adjustment.kind,
        "amount": adjustment.amount,
        "effective_on": adjustment.effective_on,
        "source_reference": adjustment.source_reference,
        "source_payload": adjustment.source_payload,
        "reason": adjustment.reason,
        "original_result_id": (
            str(adjustment.original_result_id) if adjustment.original_result_id else None
        ),
    }
    return {
        "result": result,
        "configuration": configuration,
        "component": adjustment.component,
        "rule": None,
        "adjustment": adjustment,
        "sequence": sequence,
        "quantity": None,
        "rate": None,
        "basis": None,
        "fixed_value": adjustment.amount,
        "rule_version": None,
        "employment_version": configuration.version,
        "source_type": "adjustment",
        "source_reference": adjustment.source_reference,
        "source_version": str(adjustment.pk),
        "source_payload": adjustment.source_payload,
        "snapshot_payload": _json_value(payload),
        "digest": _digest(payload),
    }


def lock_run_inputs(
    *, organization: Organization, actor: User, run: PayrollRun
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_PREPARE, organization=organization, actor=actor)
    errors: list[str] = []
    with transaction.atomic():
        run = PayrollRun.objects.select_for_update().select_related("period").get(
            pk=run.pk, organization=organization
        )
        if run.status == PayrollRunStatus.INPUTS_LOCKED:
            return run
        if run.status != PayrollRunStatus.DRAFT:
            raise ValidationError("فقط اجرای پیش‌نویس قابل قفل ورودی است.")
        results = list(
            PayrollRunEmployee.objects.select_for_update(of=("self",))
            .filter(run=run)
            .select_related("employee")
        )
        if not results:
            raise ValidationError("اجرای حقوق فاقد کارمند است.")
        all_specs: list[dict[str, Any]] = []
        inputs = {
            (item.employee_id, item.rule_id): item
            for item in PayrollInput.objects.filter(run=run).select_related("rule")
        }
        adjustments = list(
            PayrollAdjustment.objects.filter(run=run).select_related("component")
        )
        adjustments_by_employee: dict[Any, list[PayrollAdjustment]] = {}
        for adjustment in adjustments:
            adjustments_by_employee.setdefault(adjustment.employee_id, []).append(adjustment)
        for result in results:
            configuration = (
                EmploymentPayConfiguration.objects.select_for_update()
                .filter(
                    organization=organization,
                    employee=result.employee,
                    status__in=[
                        ConfigurationStatus.ACTIVE,
                        ConfigurationStatus.RETIRED,
                    ],
                    effective_from__lte=run.period.ends_on,
                )
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=run.period.ends_on))
                .first()
            )
            if configuration is None:
                PayrollException.objects.update_or_create(
                    run=run,
                    run_employee=result,
                    code="MISSING_PAY_CONFIGURATION",
                    is_resolved=False,
                    defaults={
                        "organization": organization,
                        "severity": PayrollExceptionSeverity.ERROR,
                        "message": "نسخه فعال پیکربندی پرداخت برای تاریخ دوره وجود ندارد.",
                        "details": {"employee_id": str(result.employee_id)},
                    },
                )
                errors.append(f"کارمند {result.employee_id}: پیکربندی پرداخت موجود نیست.")
                continue
            result.employment_configuration = configuration
            result.project = configuration.project
            result.site = configuration.site
            result.status = ResultStatus.READY
            result.save()
            rules = _applicable_rules(
                organization=organization,
                configuration=configuration,
                as_of=run.period.ends_on,
            )
            if run.kind in {PayrollRunKind.ADJUSTMENT, PayrollRunKind.OFF_CYCLE}:
                explicit_rule_ids = {
                    rule_id for employee_id, rule_id in inputs if employee_id == result.employee_id
                }
                rules = [rule for rule in rules if rule.pk in explicit_rule_ids]
            for rule in rules:
                payroll_input = inputs.get((result.employee_id, rule.pk))
                if (
                    rule.method == CalculationMethod.QUANTITY_TIMES_RATE
                    and payroll_input is None
                ):
                    PayrollException.objects.update_or_create(
                        run=run,
                        run_employee=result,
                        code=f"MISSING_INPUT_{rule.code}",
                        is_resolved=False,
                        defaults={
                            "organization": organization,
                            "severity": PayrollExceptionSeverity.ERROR,
                            "message": f"ورودی صریح برای قاعده {rule.code} وجود ندارد.",
                            "details": {"rule_id": str(rule.pk)},
                        },
                    )
                    errors.append(
                        f"کارمند {result.employee_id}: ورودی قاعده {rule.code} موجود نیست."
                    )
                    continue
                all_specs.append(
                    _snapshot_spec(
                        result=result,
                        configuration=configuration,
                        rule=rule,
                        payroll_input=payroll_input,
                    )
                )
            for offset, adjustment in enumerate(
                adjustments_by_employee.get(result.employee_id, []), start=900000
            ):
                all_specs.append(
                    _adjustment_snapshot_spec(
                        result=result,
                        configuration=configuration,
                        adjustment=adjustment,
                        sequence=offset,
                    )
                )
            if not rules and not adjustments_by_employee.get(result.employee_id):
                PayrollException.objects.update_or_create(
                    run=run,
                    run_employee=result,
                    code="NO_APPLICABLE_RULE_OR_ADJUSTMENT",
                    is_resolved=False,
                    defaults={
                        "organization": organization,
                        "severity": PayrollExceptionSeverity.ERROR,
                        "message": "هیچ قاعده یا تعدیل صریح قابل اعمال نیست.",
                        "details": {},
                    },
                )
                errors.append(f"کارمند {result.employee_id}: قاعده یا تعدیل موجود نیست.")
        if errors:
            _audit(
                action=AuditAction.PAYROLL_PREFLIGHT_FAILED,
                organization=organization,
                actor=actor,
                entity=run,
                metadata={"exception_count": len(errors)},
            )
        else:
            precision, rounding = resolve_monetary_policies(
                organization=organization,
                consumer=PAYROLL_MONETARY_POLICY_CONSUMER,
            )
            PayrollException.objects.filter(
                run=run,
                is_resolved=False,
                code__startswith="MISSING_",
            ).update(
                is_resolved=True,
                resolved_by=actor,
                resolved_at=timezone.now(),
                resolution="با تکمیل ورودی پیش از قفل رفع شد.",
            )
            snapshots = []
            for spec in all_specs:
                snapshots.append(
                    PayrollInputSnapshot.objects.create(
                        organization=organization,
                        run=run,
                        run_employee=spec["result"],
                        employment_configuration=spec["configuration"],
                        component=spec["component"],
                        rule=spec["rule"],
                        adjustment=spec["adjustment"],
                        sequence=spec["sequence"],
                        quantity=spec["quantity"],
                        rate=spec["rate"],
                        basis=spec["basis"],
                        fixed_value=spec["fixed_value"],
                        rule_version=spec["rule_version"],
                        employment_version=spec["employment_version"],
                        source_type=spec["source_type"],
                        source_reference=spec["source_reference"],
                        source_version=spec["source_version"],
                        source_payload=_json_value(spec["source_payload"]),
                        snapshot_payload=spec["snapshot_payload"],
                        digest=spec["digest"],
                    )
                )
            run.input_digest = _digest(sorted(item.digest for item in snapshots))
            run.precision_policy_version = precision.version
            run.rounding_policy_version = rounding.version
            run.monetary_policy_snapshot = _monetary_policy_snapshot(
                currency=run.currency, precision=precision, rounding=rounding
            )
            run.status = PayrollRunStatus.INPUTS_LOCKED
            run.inputs_locked_by = actor
            run.inputs_locked_at = timezone.now()
            run.save()
            if run.kind == PayrollRunKind.REGULAR:
                PayrollPeriod.objects.filter(pk=run.period_id).update(
                    status=PayrollPeriodStatus.LOCKED, locked_at=timezone.now()
                )
            _audit(
                action=AuditAction.PAYROLL_INPUTS_LOCKED,
                organization=organization,
                actor=actor,
                entity=run,
                metadata={"input_digest": run.input_digest, "snapshot_count": len(snapshots)},
            )
    if errors:
        raise ValidationError(errors)
    return run


def _line_amount(
    snapshot: PayrollInputSnapshot, component_unrounded: dict[str, Decimal]
) -> tuple[Decimal, Decimal | None]:
    if snapshot.adjustment_id:
        return Decimal(snapshot.fixed_value or 0), None
    if snapshot.rule_id is None:
        raise ValidationError("snapshot قاعده ندارد.")
    method = snapshot.snapshot_payload.get("method")
    if method == CalculationMethod.FIXED_AMOUNT:
        return Decimal(snapshot.fixed_value or 0), None
    if method == CalculationMethod.QUANTITY_TIMES_RATE:
        if snapshot.quantity is None or snapshot.rate is None:
            raise ValidationError("مقدار یا نرخ snapshot ناقص است.")
        return Decimal(snapshot.quantity) * Decimal(snapshot.rate), None
    if method != CalculationMethod.PERCENT_OF_COMPONENT:
        raise ValidationError("روش محاسبه snapshot نامعتبر است.")
    basis_component_id = snapshot.snapshot_payload.get("basis_component_id")
    basis = component_unrounded.get(str(basis_component_id))
    if basis is None:
        raise ValidationError(
            "جزء مبنای snapshot پیش از قاعده وابسته محاسبه نشده است."
        )
    return basis * Decimal(snapshot.rate or 0) / Decimal(100), basis


@transaction.atomic
def calculate_run(
    *, organization: Organization, actor: User, run: PayrollRun
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_PREPARE, organization=organization, actor=actor)
    run = PayrollRun.objects.select_for_update(of=("self",)).select_related(
        "precision_policy_version__policy", "rounding_policy_version__policy"
    ).get(pk=run.pk, organization=organization)
    if run.status in {
        PayrollRunStatus.CALCULATED,
        PayrollRunStatus.EXCEPTION,
        PayrollRunStatus.IN_REVIEW,
        PayrollRunStatus.APPROVED,
        PayrollRunStatus.FINALIZED,
    }:
        return run
    if run.status != PayrollRunStatus.INPUTS_LOCKED:
        raise ValidationError("ابتدا ورودی‌های اجرا باید قفل شوند.")
    precision, rounding = _locked_monetary_policies(run)
    results = list(
        PayrollRunEmployee.objects.select_for_update(of=("self",))
        .filter(run=run)
        .select_related("employee", "employment_configuration")
    )
    calculation_evidence: list[dict[str, Any]] = []
    any_exception = False
    for result in results:
        snapshots = list(
            PayrollInputSnapshot.objects.filter(run_employee=result)
            .select_related("component", "rule", "rule__basis_component", "adjustment")
            .order_by("sequence", "created_at")
        )
        gross = Decimal(0)
        deductions = Decimal(0)
        reimbursements = Decimal(0)
        employer = Decimal(0)
        informational = Decimal(0)
        component_unrounded: dict[str, Decimal] = {}
        for snapshot in snapshots:
            unrounded, basis = _line_amount(snapshot, component_unrounded)
            unrounded = _intermediate(unrounded)
            amount = _money(unrounded, precision=precision, rounding=rounding)
            component_key = str(snapshot.component_id)
            component_unrounded[component_key] = (
                component_unrounded.get(component_key, Decimal(0)) + unrounded
            )
            kind = snapshot.snapshot_payload.get("component_kind")
            if kind not in ComponentKind.values:
                raise ValidationError("نوع جزء در snapshot نامعتبر است.")
            if kind in {ComponentKind.EARNING, ComponentKind.ALLOWANCE}:
                gross += amount
            elif kind == ComponentKind.DEDUCTION:
                deductions += amount
            elif kind == ComponentKind.REIMBURSEMENT:
                reimbursements += amount
            elif kind == ComponentKind.EMPLOYER:
                employer += amount
            else:
                informational += amount
            explanation = {
                "method": snapshot.snapshot_payload.get("method", "adjustment"),
                "input_snapshot_id": str(snapshot.pk),
                "input_digest": snapshot.digest,
                "source_type": snapshot.source_type,
                "source_reference": snapshot.source_reference,
                "source_version": snapshot.source_version,
                "employment_configuration_id": str(snapshot.employment_configuration_id),
                "employment_version": snapshot.employment_version,
                "rule_id": str(snapshot.rule_id) if snapshot.rule_id else None,
                "rule_version": snapshot.rule_version,
                "component_code": snapshot.snapshot_payload.get("component_code"),
                "component_name": snapshot.snapshot_payload.get("component_name"),
                "component_kind": kind,
                "net_effect": snapshot.snapshot_payload.get("net_effect"),
                "basis": basis,
                "quantity": snapshot.quantity,
                "rate": snapshot.rate,
                "unrounded_amount": unrounded,
                "rounded_amount": amount,
                "rounding": f"{rounding.method}:{run.monetary_policy_snapshot['final_quantum']}",
                "precision_policy_version": precision.version.version,
                "rounding_policy_version": rounding.version.version,
            }
            line = PayrollResultLine.objects.create(
                organization=organization,
                run=run,
                run_employee=result,
                component=snapshot.component,
                rule=snapshot.rule,
                snapshot=snapshot,
                sequence=snapshot.sequence,
                component_kind=kind,
                rule_version=snapshot.rule_version,
                basis=basis,
                quantity=snapshot.quantity,
                rate=snapshot.rate,
                unrounded_amount=unrounded,
                amount=amount,
                explanation=_json_value(explanation),
            )
            calculation_evidence.append(
                {"line_id": str(line.pk), "snapshot_digest": snapshot.digest, "amount": amount}
            )
        net = _money(
            gross + reimbursements - deductions, precision=precision, rounding=rounding
        )
        result.gross_amount = _money(gross, precision=precision, rounding=rounding)
        result.deduction_amount = _money(
            deductions, precision=precision, rounding=rounding
        )
        result.reimbursement_amount = _money(
            reimbursements, precision=precision, rounding=rounding
        )
        result.employer_amount = _money(
            employer, precision=precision, rounding=rounding
        )
        result.informational_amount = _money(
            informational, precision=precision, rounding=rounding
        )
        result.net_amount = net
        result.status = ResultStatus.CALCULATED
        if net < 0:
            result.status = ResultStatus.EXCEPTION
            any_exception = True
            PayrollException.objects.create(
                organization=organization,
                run=run,
                run_employee=result,
                code="NEGATIVE_NET_PAY",
                severity=PayrollExceptionSeverity.ERROR,
                message="خالص پرداخت منفی است و به اصلاح/تعدیل کنترل‌شده نیاز دارد.",
                details={"net_amount": format(net, "f")},
            )
        result.save()
    run.calculation_digest = _digest(
        {"input_digest": run.input_digest, "lines": calculation_evidence}
    )
    run.status = PayrollRunStatus.EXCEPTION if any_exception else PayrollRunStatus.CALCULATED
    run.calculated_by = actor
    run.calculated_at = timezone.now()
    run.save()
    _audit(
        action=AuditAction.PAYROLL_RUN_CALCULATED,
        organization=organization,
        actor=actor,
        entity=run,
        metadata={
            "calculation_digest": run.calculation_digest,
            "employee_count": len(results),
            "has_exception": any_exception,
        },
    )
    return run


@transaction.atomic
def submit_run_for_review(
    *, organization: Organization, actor: User, run: PayrollRun
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_PREPARE, organization=organization, actor=actor)
    run = PayrollRun.objects.select_for_update().get(pk=run.pk, organization=organization)
    if run.status == PayrollRunStatus.IN_REVIEW:
        return run
    if run.status != PayrollRunStatus.CALCULATED:
        raise ValidationError("فقط اجرای محاسبه‌شده بدون استثنای باز قابل ارسال است.")
    if run.exceptions.filter(is_resolved=False, severity=PayrollExceptionSeverity.ERROR).exists():
        raise ValidationError("استثنای خطای باز مانع ارسال برای بررسی است.")
    run.status = PayrollRunStatus.IN_REVIEW
    run.submitted_by = actor
    run.submitted_at = timezone.now()
    run.save()
    _audit(
        action=AuditAction.PAYROLL_RUN_SUBMITTED,
        organization=organization,
        actor=actor,
        entity=run,
    )
    return run


@transaction.atomic
def approve_run(
    *, organization: Organization, actor: User, run: PayrollRun
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_REVIEW, organization=organization, actor=actor)
    run = PayrollRun.objects.select_for_update().get(pk=run.pk, organization=organization)
    if run.status == PayrollRunStatus.APPROVED:
        return run
    if run.status != PayrollRunStatus.IN_REVIEW:
        raise ValidationError("فقط اجرای در حال بررسی قابل تأیید است.")
    if run.exceptions.filter(is_resolved=False, severity=PayrollExceptionSeverity.ERROR).exists():
        raise ValidationError("استثنای خطای باز مانع تأیید است.")
    run.status = PayrollRunStatus.APPROVED
    run.reviewed_by = actor
    run.reviewed_at = timezone.now()
    run.save()
    _audit(
        action=AuditAction.PAYROLL_RUN_APPROVED,
        organization=organization,
        actor=actor,
        entity=run,
        metadata={"same_user_allowed": True},
    )
    return run


def _payslip_payload(result: PayrollRunEmployee) -> dict[str, Any]:
    lines = []
    for line in result.lines.select_related("component", "rule").order_by(
        "sequence", "created_at"
    ):
        lines.append(
            {
                "component_code": line.explanation.get(
                    "component_code", line.component.code
                ),
                "component_name": line.explanation.get(
                    "component_name", line.component.name
                ),
                "component_kind": line.component_kind,
                "rule_version": line.rule_version,
                "quantity": line.quantity,
                "rate": line.rate,
                "amount": line.amount,
            }
        )
    return _json_value(
        {
            "run_id": str(result.run_id),
            "result_id": str(result.pk),
            "employee_id": str(result.employee_id),
            "employee_number": result.employee.employee_number,
            "employee_name": str(result.employee),
            "period_code": result.run.period.code,
            "period_start": result.run.period.starts_on,
            "period_end": result.run.period.ends_on,
            "currency": result.run.currency,
            "monetary_policy": result.run.monetary_policy_snapshot,
            "gross_amount": result.gross_amount,
            "deduction_amount": result.deduction_amount,
            "reimbursement_amount": result.reimbursement_amount,
            "employer_amount": result.employer_amount,
            "net_amount": result.net_amount,
            "lines": lines,
            "calculation_digest": result.run.calculation_digest,
        }
    )


@transaction.atomic
def finalize_run(
    *, organization: Organization, actor: User, run: PayrollRun
) -> PayrollRun:
    _scope(BusinessPermissionCode.PAYROLL_FINALIZE, organization=organization, actor=actor)
    run = PayrollRun.objects.select_for_update().select_related("period").get(
        pk=run.pk, organization=organization
    )
    if run.status == PayrollRunStatus.FINALIZED:
        return run
    if run.status != PayrollRunStatus.APPROVED:
        raise ValidationError("فقط اجرای تأییدشده قابل قطعی‌سازی است.")
    if run.exceptions.filter(is_resolved=False, severity=PayrollExceptionSeverity.ERROR).exists():
        raise ValidationError("استثنای خطای باز مانع قطعی‌سازی است.")
    results = list(
        PayrollRunEmployee.objects.select_for_update(of=("self",))
        .filter(run=run)
        .select_related("employee", "run__period")
    )
    if any(result.net_amount < 0 for result in results):
        raise ValidationError("خالص منفی از مسیر عادی قابل قطعی‌سازی نیست.")
    now = timezone.now()
    for result in results:
        result.status = ResultStatus.FINALIZED
        result.save()
        payload = _payslip_payload(result)
        Payslip.objects.create(
            organization=organization,
            run=run,
            run_employee=result,
            number=f"{run.code}-{result.employee.employee_number}",
            issued_at=now,
            content_digest=Payslip.digest_payload(payload),
            presentation_snapshot=payload,
        )
    run.status = PayrollRunStatus.FINALIZED
    run.finalized_by = actor
    run.finalized_at = now
    run.save()
    if run.kind == PayrollRunKind.REGULAR:
        PayrollPeriod.objects.filter(pk=run.period_id).update(
            status=PayrollPeriodStatus.FINALIZED, finalized_at=now
        )
    _audit(
        action=AuditAction.PAYROLL_RUN_FINALIZED,
        organization=organization,
        actor=actor,
        entity=run,
        metadata={"employee_count": len(results), "calculation_digest": run.calculation_digest},
    )
    from .cumulative_services import record_cumulative_for_run

    record_cumulative_for_run(
        organization=organization,
        actor=actor,
        run=run,
        require_approved_year=False,
    )
    return run


@transaction.atomic
def resolve_exception(
    *,
    organization: Organization,
    actor: User,
    exception: PayrollException,
    resolution: str,
) -> PayrollException:
    _scope(BusinessPermissionCode.PAYROLL_ADJUST, organization=organization, actor=actor)
    exception = PayrollException.objects.select_for_update().get(
        pk=exception.pk, organization=organization
    )
    if exception.is_resolved:
        return exception
    if exception.code == "NEGATIVE_NET_PAY":
        raise ValidationError("خالص منفی فقط با اجرای اصلاحی/برگشت قابل رسیدگی است.")
    if not resolution.strip():
        raise ValidationError("شرح رفع استثنا الزامی است.")
    exception.is_resolved = True
    exception.resolved_by = actor
    exception.resolved_at = timezone.now()
    exception.resolution = resolution.strip()
    exception.save()
    _audit(
        action=AuditAction.PAYROLL_EXCEPTION_RESOLVED,
        organization=organization,
        actor=actor,
        entity=exception,
        metadata={"code": exception.code},
    )
    return exception


@transaction.atomic
def reverse_run(
    *,
    organization: Organization,
    actor: User,
    original_run: PayrollRun,
    reason: str,
    idempotency_key: str,
    create_replacement: bool = True,
    replacement_code: str | None = None,
) -> PayrollReversal:
    _scope(BusinessPermissionCode.PAYROLL_ADJUST, organization=organization, actor=actor)
    original_run = PayrollRun.objects.select_for_update(of=("self",)).select_related(
        "period", "precision_policy_version__policy", "rounding_policy_version__policy"
    ).get(
        pk=original_run.pk, organization=organization
    )
    existing = PayrollReversal.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.original_run_id != original_run.pk:
            raise ValidationError("کلید idempotency برای برگشت دیگری استفاده شده است.")
        return existing
    if original_run.status != PayrollRunStatus.FINALIZED:
        raise ValidationError("فقط اجرای قطعی قابل برگشت است.")
    if not reason.strip():
        raise ValidationError("دلیل برگشت الزامی است.")
    _locked_monetary_policies(original_run)
    now = timezone.now()
    reversal_run = PayrollRun.objects.create(
        organization=organization,
        period=original_run.period,
        code=f"{original_run.code}-REV",
        kind=PayrollRunKind.REVERSAL,
        status=PayrollRunStatus.APPROVED,
        idempotency_key=f"reversal:{idempotency_key}",
        predecessor=original_run,
        reversal_of=original_run,
        input_digest=original_run.input_digest,
        precision_policy_version=original_run.precision_policy_version,
        rounding_policy_version=original_run.rounding_policy_version,
        monetary_policy_snapshot=original_run.monetary_policy_snapshot,
        currency=original_run.currency,
        created_by=actor,
        inputs_locked_by=actor,
        inputs_locked_at=now,
        calculated_by=actor,
        calculated_at=now,
        submitted_by=actor,
        submitted_at=now,
        reviewed_by=actor,
        reviewed_at=now,
        reversal_reason=reason.strip(),
    )
    original_results = list(
        PayrollRunEmployee.objects.select_for_update(of=("self",))
        .filter(run=original_run)
        .select_related("employee", "employment_configuration")
    )
    reversal_line_evidence: list[dict[str, Any]] = []
    for original_result in original_results:
        reversal_result = PayrollRunEmployee.objects.create(
            organization=organization,
            run=reversal_run,
            employee=original_result.employee,
            employment_configuration=original_result.employment_configuration,
            project=original_result.project,
            site=original_result.site,
            status=ResultStatus.FINALIZED,
            gross_amount=-original_result.gross_amount,
            deduction_amount=-original_result.deduction_amount,
            reimbursement_amount=-original_result.reimbursement_amount,
            employer_amount=-original_result.employer_amount,
            informational_amount=-original_result.informational_amount,
            net_amount=-original_result.net_amount,
            predecessor_result=original_result,
        )
        for original_line in original_result.lines.select_related("component", "rule"):
            line = PayrollResultLine.objects.create(
                organization=organization,
                run=reversal_run,
                run_employee=reversal_result,
                component=original_line.component,
                rule=original_line.rule,
                snapshot=None,
                sequence=original_line.sequence,
                component_kind=original_line.component_kind,
                rule_version=original_line.rule_version,
                basis=(-original_line.basis if original_line.basis is not None else None),
                quantity=(-original_line.quantity if original_line.quantity is not None else None),
                rate=original_line.rate,
                unrounded_amount=-original_line.unrounded_amount,
                amount=-original_line.amount,
                explanation={
                    "method": "reversal",
                    "original_run_id": str(original_run.pk),
                    "original_result_id": str(original_result.pk),
                    "original_line_id": str(original_line.pk),
                    "original_calculation_digest": original_run.calculation_digest,
                    "component_code": original_line.explanation.get(
                        "component_code", original_line.component.code
                    ),
                    "component_name": original_line.explanation.get(
                        "component_name", original_line.component.name
                    ),
                    "component_kind": original_line.component_kind,
                    "net_effect": original_line.explanation.get("net_effect"),
                    "reason": reason.strip(),
                },
                is_reversal=True,
            )
            reversal_line_evidence.append(
                {"line_id": str(line.pk), "original_line_id": str(original_line.pk)}
            )
        payload = _payslip_payload(reversal_result)
        Payslip.objects.create(
            organization=organization,
            run=reversal_run,
            run_employee=reversal_result,
            number=f"{reversal_run.code}-{reversal_result.employee.employee_number}",
            issued_at=now,
            content_digest=Payslip.digest_payload(payload),
            presentation_snapshot=payload,
        )
    reversal_run.calculation_digest = _digest(
        {
            "reversal_of": str(original_run.pk),
            "original_digest": original_run.calculation_digest,
            "lines": reversal_line_evidence,
        }
    )
    reversal_run.status = PayrollRunStatus.FINALIZED
    reversal_run.finalized_by = actor
    reversal_run.finalized_at = now
    reversal_run.save()
    PayrollRun.objects.filter(pk=original_run.pk).update(
        status=PayrollRunStatus.REVERSED, reversal_reason=reason.strip()
    )
    PayrollRunEmployee.objects.filter(run=original_run).update(status=ResultStatus.REVERSED)
    replacement_run = None
    if create_replacement:
        replacement_run = PayrollRun.objects.create(
            organization=organization,
            period=original_run.period,
            code=replacement_code or f"{original_run.code}-RPL",
            kind=PayrollRunKind.REPLACEMENT,
            idempotency_key=f"replacement:{idempotency_key}",
            predecessor=reversal_run,
            replaces=original_run,
            currency=original_run.currency,
            created_by=actor,
        )
        for original_result in original_results:
            PayrollRunEmployee.objects.create(
                organization=organization,
                run=replacement_run,
                employee=original_result.employee,
                predecessor_result=original_result,
            )
    reversal = PayrollReversal.objects.create(
        organization=organization,
        original_run=original_run,
        reversal_run=reversal_run,
        replacement_run=replacement_run,
        reason=reason.strip(),
        idempotency_key=idempotency_key,
        reversed_by=actor,
    )
    _audit(
        action=AuditAction.PAYROLL_RUN_REVERSED,
        organization=organization,
        actor=actor,
        entity=reversal,
        metadata={
            "original_run_id": str(original_run.pk),
            "reversal_run_id": str(reversal_run.pk),
            "replacement_run_id": str(replacement_run.pk) if replacement_run else None,
        },
    )
    from .cumulative_services import record_cumulative_for_run

    record_cumulative_for_run(
        organization=organization,
        actor=actor,
        run=original_run,
        require_approved_year=False,
    )
    record_cumulative_for_run(
        organization=organization,
        actor=actor,
        run=reversal_run,
        require_approved_year=False,
    )
    return reversal


def view_payslip(
    *, organization: Organization, actor: User, payslip: Payslip
) -> Payslip:
    _scope(
        BusinessPermissionCode.PAYSLIPS_VIEW,
        organization=organization,
        actor=actor,
        project=payslip.run_employee.project,
        site=payslip.run_employee.site,
    )
    _ensure_tenant(organization, payslip=payslip)
    _audit(
        action=AuditAction.PAYSLIP_VIEWED,
        organization=organization,
        actor=actor,
        entity=payslip,
        metadata={"run_id": str(payslip.run_id)},
    )
    return payslip


def export_payslip(
    *, organization: Organization, actor: User, payslip: Payslip
) -> dict[str, Any]:
    _scope(
        BusinessPermissionCode.PAYSLIPS_EXPORT,
        organization=organization,
        actor=actor,
        project=payslip.run_employee.project,
        site=payslip.run_employee.site,
    )
    _ensure_tenant(organization, payslip=payslip)
    _audit(
        action=AuditAction.PAYSLIP_EXPORTED,
        organization=organization,
        actor=actor,
        entity=payslip,
        metadata={"run_id": str(payslip.run_id), "content_digest": payslip.content_digest},
    )
    return payslip.presentation_snapshot
