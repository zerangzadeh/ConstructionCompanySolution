from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import record_audit_event
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization
from apps.organizations.policy_services import (
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
    PAYROLL_TAX_REGULATORY_POLICY_CODE,
)

from .models import (
    PayrollRun,
    PayrollRunStatus,
    ResultStatus,
    StatutoryCalculation,
    StatutoryCalculationKind,
    StatutoryCalculationLine,
    StatutoryEmployeeResult,
    StatutoryExportEvidence,
    StatutoryExportStatus,
    StatutoryIdentityEvidence,
    StatutoryIdentitySubject,
    StatutoryOutput,
    StatutoryReconciliation,
    StatutoryReconciliationStatus,
    StatutoryRecordKind,
    StatutoryReviewDisposition,
    StatutoryReviewEvidence,
    StatutorySubmissionResolution,
)

ROUNDING_METHODS = {
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_DOWN": ROUND_DOWN,
    "ROUND_UP": ROUND_UP,
}


@dataclass(frozen=True)
class EmployeeCalculation:
    run_employee: Any
    basis: Decimal
    work_days: Decimal | None
    employee_amount: Decimal
    employer_amount: Decimal
    other_amount: Decimal
    snapshot: dict[str, Any]
    source_digest: str
    lines: tuple[dict[str, Any], ...]


def _require(*, actor: User, organization: Organization, permission: str) -> None:
    if not organization.is_active:
        raise PermissionDenied("Tenant فعال نیست.")
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        message="اجازه عملیات حساس مقرراتی حقوق را ندارید.",
    )


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value: object, *, name: str, minimum: Decimal | None = None) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"مقدار {name} باید Decimal معتبر باشد.") from exc
    if not parsed.is_finite() or (minimum is not None and parsed < minimum):
        raise ValidationError(f"مقدار {name} خارج از دامنه مجاز است.")
    return parsed


def _round(value: Decimal, config: object) -> Decimal:
    if not isinstance(config, dict):
        raise ValidationError("سیاست گرد کردن مقرراتی معتبر نیست.")
    method = config.get("method")
    scale = config.get("scale")
    stage = config.get("stage")
    if method not in ROUNDING_METHODS or type(scale) is not int or not 0 <= scale <= 8:
        raise ValidationError("روش یا دقت گرد کردن مقرراتی پشتیبانی نمی‌شود.")
    if stage != "line":
        raise ValidationError("مرحله گرد کردن باید صریحاً line باشد.")
    quantum = Decimal(1).scaleb(-scale)
    return value.quantize(quantum, rounding=ROUNDING_METHODS[method])


def _mapping(parameters: dict[str, Any], *, allowed: set[str]) -> dict[str, dict]:
    rows = parameters.get("component_mappings")
    if not isinstance(rows, list) or not rows:
        raise ValidationError("نگاشت اجزای مقرراتی باید صریح و غیرخالی باشد.")
    mapped: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "component_code",
            "classification",
            "basis_factor",
        }:
            raise ValidationError("ساختار نگاشت جزء مقرراتی معتبر نیست.")
        code = str(row["component_code"]).strip().upper()
        if not code or code in mapped or row["classification"] not in allowed:
            raise ValidationError("کد یا طبقه‌بندی نگاشت جزء مقرراتی معتبر نیست.")
        factor = _decimal(row["basis_factor"], name="ضریب مبنا")
        if factor < Decimal(-1) or factor > Decimal(1):
            raise ValidationError("ضریب مبنا باید بین منفی یک و یک باشد.")
        mapped[code] = {**row, "component_code": code, "basis_factor": factor}
    return mapped


def _threshold_basis(basis: Decimal, parameters: dict[str, Any]) -> Decimal:
    thresholds = parameters.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != {"floor", "ceiling"}:
        raise ValidationError("کف و سقف مقرراتی باید صریح باشند.")
    floor = None if thresholds["floor"] is None else _decimal(
        thresholds["floor"], name="کف", minimum=Decimal(0)
    )
    ceiling = None if thresholds["ceiling"] is None else _decimal(
        thresholds["ceiling"], name="سقف", minimum=Decimal(0)
    )
    if floor is not None and ceiling is not None and ceiling < floor:
        raise ValidationError("سقف مقرراتی کمتر از کف است.")
    if floor is not None:
        basis = max(basis, floor)
    if ceiling is not None:
        basis = min(basis, ceiling)
    return basis


def _source_basis(run_employee, mapping: dict[str, dict]) -> tuple[Decimal, list[dict]]:
    source_lines = list(run_employee.lines.select_related("component").all())
    source_codes = {line.component.code for line in source_lines}
    missing = sorted(source_codes - set(mapping))
    if missing:
        raise ValidationError(
            "طبقه‌بندی مقرراتی برای اجزای حقوق کامل نیست: " + ", ".join(missing)
        )
    evidence: list[dict] = []
    basis = Decimal(0)
    for line in source_lines:
        rule = mapping[line.component.code]
        contribution = line.unrounded_amount * rule["basis_factor"]
        basis += contribution
        evidence.append(
            {
                "component_id": str(line.component_id),
                "component_code": line.component.code,
                "payroll_result_line_id": str(line.pk),
                "payroll_amount": str(line.amount),
                "payroll_unrounded_amount": str(line.unrounded_amount),
                "classification": rule["classification"],
                "basis_factor": str(rule["basis_factor"]),
                "basis_contribution": str(contribution),
            }
        )
    if basis < 0:
        raise ValidationError("مبنای مقرراتی حاصل منفی است.")
    return basis, evidence


def _tax_employee(run_employee, parameters: dict[str, Any]) -> EmployeeCalculation:
    if parameters.get("calculation_basis") not in {"period", "cumulative"}:
        raise ValidationError("مبنای محاسبه مالیات ناشناخته است.")
    if parameters["calculation_basis"] == "cumulative":
        raise ValidationError("محاسبه تجمعی بدون مانده افتتاحیه رسمی fail-closed است.")
    if parameters.get("correction_mode") != "successor_only":
        raise ValidationError("رفتار اصلاح مالیات باید successor_only باشد.")
    mapping = _mapping(parameters, allowed={"taxable", "non_taxable"})
    raw_basis, source_evidence = _source_basis(run_employee, mapping)
    exemptions = parameters.get("exemptions")
    if not isinstance(exemptions, list):
        raise ValidationError("معافیت‌های مالیاتی باید صریح باشند.")
    exemption_total = Decimal(0)
    normalized_exemptions = []
    for item in exemptions:
        if not isinstance(item, dict) or set(item) != {"code", "amount"}:
            raise ValidationError("ساختار معافیت مالیاتی معتبر نیست.")
        amount = _decimal(item["amount"], name="معافیت", minimum=Decimal(0))
        exemption_total += amount
        normalized_exemptions.append({"code": str(item["code"]), "amount": str(amount)})
    basis = _threshold_basis(max(Decimal(0), raw_basis - exemption_total), parameters)
    brackets = parameters.get("brackets")
    if not isinstance(brackets, list) or not brackets:
        raise ValidationError("طبقات مالیاتی باید صریح و غیرخالی باشند.")
    cursor = Decimal(0)
    tax = Decimal(0)
    lines: list[dict[str, Any]] = []
    for index, bracket in enumerate(brackets, start=1):
        if not isinstance(bracket, dict) or set(bracket) != {"lower", "upper", "rate"}:
            raise ValidationError("ساختار طبقه مالیاتی معتبر نیست.")
        lower = _decimal(bracket["lower"], name="کران پایین", minimum=Decimal(0))
        upper = None if bracket["upper"] is None else _decimal(
            bracket["upper"], name="کران بالا", minimum=Decimal(0)
        )
        rate = _decimal(bracket["rate"], name="نرخ مالیات", minimum=Decimal(0))
        if rate > 100 or lower != cursor or (upper is not None and upper <= lower):
            raise ValidationError("طبقات مالیاتی پیوسته یا معتبر نیستند.")
        taxable_slice = max(Decimal(0), min(basis, upper or basis) - lower)
        unrounded = taxable_slice * rate / Decimal(100)
        amount = _round(unrounded, parameters.get("rounding"))
        tax += amount
        lines.append(
            {
                "line_code": f"TAX-BRACKET-{index}",
                "classification": "tax_bracket",
                "payer": "employee",
                "basis_amount": taxable_slice,
                "rate": rate,
                "unrounded_amount": unrounded,
                "amount": amount,
                "evidence": {"lower": str(lower), "upper": None if upper is None else str(upper)},
            }
        )
        if upper is None:
            cursor = basis
            break
        cursor = upper
    if basis > cursor:
        raise ValidationError("طبقات مالیاتی کل مبنای محاسبه را پوشش نمی‌دهند.")
    snapshot = {
        "raw_basis": str(raw_basis),
        "exemptions": normalized_exemptions,
        "basis": str(basis),
        "tax": str(tax),
        "source_lines": source_evidence,
    }
    return EmployeeCalculation(
        run_employee=run_employee,
        basis=basis,
        work_days=None,
        employee_amount=tax,
        employer_amount=Decimal(0),
        other_amount=Decimal(0),
        snapshot=snapshot,
        source_digest=_digest(source_evidence),
        lines=tuple(lines),
    )


def _insurance_employee(run_employee, parameters: dict[str, Any]) -> EmployeeCalculation:
    if parameters.get("correction_mode") != "successor_only":
        raise ValidationError("رفتار اصلاح بیمه باید successor_only باشد.")
    mapping = _mapping(parameters, allowed={"insurable", "non_insurable", "work_days"})
    raw_basis, source_evidence = _source_basis(run_employee, mapping)
    basis_mode = parameters.get("basis_mode")
    if basis_mode not in {"wage", "wage_and_days"}:
        raise ValidationError("مبنای بیمه کارکنان ناشناخته است.")
    day_lines = [
        line
        for line in run_employee.lines.select_related("component")
        if mapping[line.component.code]["classification"] == "work_days"
    ]
    work_days = None
    if basis_mode == "wage_and_days":
        if len(day_lines) != 1 or day_lines[0].quantity is None:
            raise ValidationError("شاهد روزکار رسمی برای محاسبه بیمه موجود نیست.")
        work_days = day_lines[0].quantity
    exemptions = parameters.get("exemptions")
    if not isinstance(exemptions, list):
        raise ValidationError("معافیت‌های بیمه باید صریح باشند.")
    exemption_total = Decimal(0)
    normalized_exemptions = []
    for item in exemptions:
        if not isinstance(item, dict) or set(item) != {"code", "amount"}:
            raise ValidationError("ساختار معافیت بیمه معتبر نیست.")
        amount = _decimal(item["amount"], name="معافیت بیمه", minimum=Decimal(0))
        exemption_total += amount
        normalized_exemptions.append({"code": str(item["code"]), "amount": str(amount)})
    basis = _threshold_basis(max(Decimal(0), raw_basis - exemption_total), parameters)
    categories = parameters.get("contribution_categories")
    if not isinstance(categories, list) or not categories:
        raise ValidationError("سهم‌های بیمه باید صریح و غیرخالی باشند.")
    totals = {"employee": Decimal(0), "employer": Decimal(0), "other": Decimal(0)}
    lines = []
    seen = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != {"code", "payer", "rate"}:
            raise ValidationError("ساختار سهم بیمه معتبر نیست.")
        code = str(item["code"]).strip()
        payer = item["payer"]
        rate = _decimal(item["rate"], name="نرخ بیمه", minimum=Decimal(0))
        if not code or code in seen or payer not in totals or rate > 100:
            raise ValidationError("کد، پرداخت‌کننده یا نرخ سهم بیمه معتبر نیست.")
        seen.add(code)
        unrounded = basis * rate / Decimal(100)
        amount = _round(unrounded, parameters.get("rounding"))
        totals[payer] += amount
        lines.append(
            {
                "line_code": code,
                "classification": "insurance_contribution",
                "payer": payer,
                "basis_amount": basis,
                "rate": rate,
                "unrounded_amount": unrounded,
                "amount": amount,
                "evidence": {"basis_mode": basis_mode},
            }
        )
    snapshot = {
        "raw_basis": str(raw_basis),
        "exemptions": normalized_exemptions,
        "basis": str(basis),
        "work_days": None if work_days is None else str(work_days),
        "source_lines": source_evidence,
        "totals": {key: str(value) for key, value in totals.items()},
    }
    return EmployeeCalculation(
        run_employee=run_employee,
        basis=basis,
        work_days=work_days,
        employee_amount=totals["employee"],
        employer_amount=totals["employer"],
        other_amount=totals["other"],
        snapshot=snapshot,
        source_digest=_digest(source_evidence),
        lines=tuple(lines),
    )


@transaction.atomic
def calculate_statutory(
    *,
    organization: Organization,
    actor: User,
    run: PayrollRun,
    kind: str,
    reason: str,
    record_kind: str = StatutoryRecordKind.ORIGINAL,
    corrects: StatutoryCalculation | None = None,
) -> StatutoryCalculation:
    permission = (
        BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE
        if record_kind == StatutoryRecordKind.ORIGINAL
        else BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT
    )
    _require(actor=actor, organization=organization, permission=permission)
    try:
        locked_run = (
            PayrollRun.objects.select_for_update()
            .select_related("period")
            .get(pk=run.pk, organization=organization)
        )
    except PayrollRun.DoesNotExist as exc:
        raise PermissionDenied("اجرای حقوق متعلق به این Tenant نیست.") from exc
    if locked_run.status != PayrollRunStatus.FINALIZED or not locked_run.finalized_at:
        raise ValidationError("فقط اجرای قطعی حقوق قابل محاسبه مقرراتی است.")
    if kind not in StatutoryCalculationKind.values or record_kind not in StatutoryRecordKind.values:
        raise ValidationError("نوع محاسبه یا سابقه مقرراتی معتبر نیست.")
    locked_corrects = None
    if record_kind == StatutoryRecordKind.ORIGINAL:
        if corrects is not None:
            raise ValidationError("محاسبه اصلی سابقه اصلاح ندارد.")
        series_id, revision = None, 1
    else:
        if corrects is None:
            raise ValidationError("اصلاح یا ابطال باید سابقه قبلی را مشخص کند.")
        try:
            locked_corrects = StatutoryCalculation.objects.select_for_update().get(
                pk=corrects.pk, organization=organization, kind=kind
            )
        except StatutoryCalculation.DoesNotExist as exc:
            raise PermissionDenied("سابقه اصلاح متعلق به این Tenant نیست.") from exc
        if not (
            locked_run.replaces_id == locked_corrects.run_id
            or locked_run.predecessor_id == locked_corrects.run_id
        ):
            raise ValidationError("lineage اجرای حقوق و اصلاح مقرراتی هم‌خوان نیست.")
        if locked_corrects.successors.exists():
            raise ValidationError("برای این سابقه قبلاً جانشین ثبت شده است.")
        series_id, revision = locked_corrects.series_id, locked_corrects.revision + 1
    policy_code, consumer = {
        StatutoryCalculationKind.PAYROLL_TAX: (
            PAYROLL_TAX_REGULATORY_POLICY_CODE,
            "payroll.statutory_tax.calculate",
        ),
        StatutoryCalculationKind.EMPLOYEE_INSURANCE: (
            EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
            "payroll.employee_insurance.calculate",
        ),
    }[kind]
    policy = resolve_effective_platform_regulatory_policy(
        code=policy_code, consumer=consumer, on_date=locked_run.period.ends_on
    )
    if record_kind == StatutoryRecordKind.CANCELLATION:
        employee_calculations: list[EmployeeCalculation] = []
    else:
        run_employees = list(
            locked_run.employee_results.select_for_update()
            .select_related("employee")
            .prefetch_related("lines__component")
        )
        if not run_employees or any(
            item.status != ResultStatus.FINALIZED for item in run_employees
        ):
            raise ValidationError("همه نتایج کارکنان باید قطعی باشند.")
        calculator = (
            _tax_employee
            if kind == StatutoryCalculationKind.PAYROLL_TAX
            else _insurance_employee
        )
        employee_calculations = [
            calculator(item, policy.parameters) for item in run_employees
        ]
    totals = {
        "basis": sum((item.basis for item in employee_calculations), Decimal(0)),
        "employee": sum(
            (item.employee_amount for item in employee_calculations), Decimal(0)
        ),
        "employer": sum(
            (item.employer_amount for item in employee_calculations), Decimal(0)
        ),
        "other": sum((item.other_amount for item in employee_calculations), Decimal(0)),
    }
    source_snapshot = {
        "run_id": str(locked_run.pk),
        "run_code": locked_run.code,
        "run_calculation_digest": locked_run.calculation_digest,
        "run_finalized_at": locked_run.finalized_at.isoformat(),
        "period_start": locked_run.period.starts_on.isoformat(),
        "period_end": locked_run.period.ends_on.isoformat(),
        "employee_source_digests": [
            item.source_digest for item in employee_calculations
        ],
    }
    policy_snapshot = {
        "policy_id": str(policy.policy_id),
        "policy_version_id": str(policy.pk),
        "version": policy.version,
        "effective_from": policy.effective_from.isoformat(),
        "effective_to": policy.effective_to.isoformat() if policy.effective_to else None,
        "source_ids": [str(value) for value in policy.sources.values_list("pk", flat=True)],
        "parameters": policy.parameters,
    }
    digest_payload = {
        "kind": kind,
        "record_kind": record_kind,
        "policy": policy_snapshot,
        "source": source_snapshot,
        "results": [item.snapshot for item in employee_calculations],
        "totals": {key: str(value) for key, value in totals.items()},
    }
    calculation = StatutoryCalculation(
        organization=organization,
        run=locked_run,
        kind=kind,
        policy_version=policy,
        revision=revision,
        record_kind=record_kind,
        corrects=locked_corrects,
        effective_on=locked_run.period.ends_on,
        currency=locked_run.currency,
        total_basis=totals["basis"],
        employee_amount=totals["employee"],
        employer_amount=totals["employer"],
        other_amount=totals["other"],
        policy_snapshot=policy_snapshot,
        source_snapshot=source_snapshot,
        monetary_policy_snapshot=locked_run.monetary_policy_snapshot,
        content_digest=_digest(digest_payload),
        reason=reason.strip(),
        prepared_by=actor,
    )
    if series_id is not None:
        calculation.series_id = series_id
    try:
        calculation.save()
    except IntegrityError as exc:
        raise ValidationError("محاسبه اصلی این اجرا قبلاً ثبت شده است.") from exc
    for item in employee_calculations:
        employee_result = StatutoryEmployeeResult.objects.create(
            calculation=calculation,
            organization=organization,
            run_employee=item.run_employee,
            basis_amount=item.basis,
            work_days=item.work_days,
            employee_amount=item.employee_amount,
            employer_amount=item.employer_amount,
            other_amount=item.other_amount,
            calculation_snapshot=item.snapshot,
            source_digest=item.source_digest,
        )
        for line in item.lines:
            StatutoryCalculationLine.objects.create(
                organization=organization,
                employee_result=employee_result,
                component=None,
                **line,
            )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_CALCULATED,
        entity_type="payroll.StatutoryCalculation",
        entity_id=calculation.pk,
        organization=organization,
        actor=actor,
        metadata={
            "run_id": str(locked_run.pk),
            "kind": kind,
            "record_kind": record_kind,
            "policy_version_id": str(policy.pk),
            "digest": calculation.content_digest,
        },
    )
    return calculation


@transaction.atomic
def review_statutory_calculation(
    *,
    organization: Organization,
    actor: User,
    calculation: StatutoryCalculation,
    disposition: str,
    reason: str,
) -> StatutoryReviewEvidence:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_STATUTORY_REVIEW,
    )
    try:
        locked = StatutoryCalculation.objects.select_for_update().get(
            pk=calculation.pk, organization=organization
        )
    except StatutoryCalculation.DoesNotExist as exc:
        raise PermissionDenied("محاسبه متعلق به این Tenant نیست.") from exc
    if disposition not in StatutoryReviewDisposition.values:
        raise ValidationError("نتیجه بررسی معتبر نیست.")
    evidence = StatutoryReviewEvidence.objects.create(
        organization=organization,
        calculation=locked,
        disposition=disposition,
        reason=reason.strip(),
        reviewed_by=actor,
        reviewed_at=timezone.now(),
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_REVIEWED,
        entity_type="payroll.StatutoryReviewEvidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={"calculation_id": str(locked.pk), "disposition": disposition},
    )
    return evidence


@transaction.atomic
def record_statutory_identity(
    *,
    organization: Organization,
    actor: User,
    kind: str,
    schema_version,
    identifiers: dict[str, str],
    effective_from,
    source_reference: str,
    employee=None,
    effective_to=None,
    supersedes: StatutoryIdentityEvidence | None = None,
) -> StatutoryIdentityEvidence:
    """Record only identifier keys explicitly named by reviewed official schema."""

    _require(
        actor=actor,
        organization=organization,
        permission=(
            BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT
            if supersedes
            else BusinessPermissionCode.PAYROLL_STATUTORY_PREPARE
        ),
    )
    if kind not in StatutoryCalculationKind.values:
        raise ValidationError("نوع هویت مقرراتی معتبر نیست.")
    schema_code, consumer = {
        StatutoryCalculationKind.PAYROLL_TAX: (
            PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
            "payroll.statutory_tax.output",
        ),
        StatutoryCalculationKind.EMPLOYEE_INSURANCE: (
            EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
            "payroll.employee_insurance.output",
        ),
    }[kind]
    resolved = resolve_effective_platform_regulatory_policy(
        code=schema_code, consumer=consumer, on_date=effective_from
    )
    if resolved.pk != schema_version.pk:
        raise ValidationError("نسخه طرح هویت با نسخه رسمی مؤثر هم‌خوان نیست.")
    allowed = resolved.parameters.get("official_identifiers")
    if (
        not isinstance(allowed, list)
        or not identifiers
        or not set(identifiers).issubset(set(allowed))
    ):
        raise ValidationError("شناسه Tenant در طرح رسمی مجاز نشده است.")
    if employee is not None and employee.organization_id != organization.pk:
        raise PermissionDenied("کارمند هویت مقرراتی متعلق به این Tenant نیست.")
    subject = (
        StatutoryIdentitySubject.EMPLOYEE
        if employee is not None
        else StatutoryIdentitySubject.EMPLOYER
    )
    locked_previous = None
    if supersedes is not None:
        try:
            locked_previous = StatutoryIdentityEvidence.objects.select_for_update().get(
                pk=supersedes.pk,
                organization=organization,
                kind=kind,
                subject=subject,
                employee=employee,
            )
        except StatutoryIdentityEvidence.DoesNotExist as exc:
            raise PermissionDenied("نسخه قبلی هویت متعلق به این Tenant نیست.") from exc
        if locked_previous.successors.exists():
            raise ValidationError("برای نسخه هویت قبلی جانشین ثبت شده است.")
        version = locked_previous.version + 1
    else:
        existing = StatutoryIdentityEvidence.objects.filter(
            organization=organization,
            kind=kind,
            subject=subject,
            employee=employee,
        )
        if existing.exists():
            raise ValidationError("هویت موجود باید با جانشین نسخه‌دار اصلاح شود.")
        version = 1
    evidence = StatutoryIdentityEvidence.objects.create(
        organization=organization,
        employee=employee,
        subject=subject,
        kind=kind,
        schema_version=resolved,
        version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        identifiers=identifiers,
        source_reference=source_reference.strip(),
        supersedes=locked_previous,
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_IDENTITY_RECORDED,
        entity_type="payroll.StatutoryIdentityEvidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={
            "kind": kind,
            "subject": subject,
            "schema_version_id": str(resolved.pk),
            "identifier_keys": sorted(identifiers),
        },
    )
    return evidence


def _serialized_money(value: Decimal, scale: int) -> str:
    if not 0 <= scale <= 8:
        raise ValidationError("دقت پول طرح خروجی معتبر نیست.")
    quantum = Decimal(1).scaleb(-scale)
    rendered = value.quantize(quantum)
    if rendered != value:
        raise ValidationError("دقت طرح خروجی باعث از دست رفتن مبلغ می‌شود.")
    return f"{rendered:.{scale}f}"


@transaction.atomic
def generate_statutory_output(
    *,
    organization: Organization,
    actor: User,
    calculation: StatutoryCalculation,
    output_identifier: str,
    corrects: StatutoryOutput | None = None,
) -> StatutoryOutput:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_STATUTORY_OUTPUT_GENERATE,
    )
    try:
        locked = (
            StatutoryCalculation.objects.select_for_update()
            .select_related("run", "run__period")
            .get(pk=calculation.pk, organization=organization)
        )
    except StatutoryCalculation.DoesNotExist as exc:
        raise PermissionDenied("محاسبه متعلق به این Tenant نیست.") from exc
    if locked.review.disposition != StatutoryReviewDisposition.ACCEPTED:
        raise ValidationError("فقط محاسبه بررسی و پذیرفته‌شده خروجی می‌گیرد.")
    schema_code, consumer = {
        StatutoryCalculationKind.PAYROLL_TAX: (
            PAYROLL_TAX_OUTPUT_SCHEMA_POLICY_CODE,
            "payroll.statutory_tax.output",
        ),
        StatutoryCalculationKind.EMPLOYEE_INSURANCE: (
            EMPLOYEE_INSURANCE_OUTPUT_SCHEMA_POLICY_CODE,
            "payroll.employee_insurance.output",
        ),
    }[locked.kind]
    schema = resolve_effective_platform_regulatory_policy(
        code=schema_code, consumer=consumer, on_date=locked.effective_on
    )
    parameters = schema.parameters
    expected_keys = {
        "schema_identifier",
        "official_identifiers",
        "calendar_mapping",
        "monetary_scale",
        "field_mapping",
        "required_fields",
        "encoding",
    }
    if set(parameters) != expected_keys:
        raise ValidationError("قرارداد طرح رسمی خروجی کامل نیست.")
    calendar = parameters["calendar_mapping"]
    if calendar != {"mode": "gregorian_iso"}:
        raise ValidationError("نگاشت تقویم رسمی پشتیبانی/تأیید نشده و خروجی متوقف است.")
    mapping = parameters["field_mapping"]
    required = parameters["required_fields"]
    official_identifiers = parameters["official_identifiers"]
    if (
        not isinstance(mapping, dict)
        or not isinstance(required, list)
        or not isinstance(official_identifiers, list)
        or not all(isinstance(value, str) and value.strip() for value in official_identifiers)
    ):
        raise ValidationError("نگاشت، فیلدها یا شناسه‌های رسمی طرح معتبر نیستند.")
    scale = parameters["monetary_scale"]
    if type(scale) is not int:
        raise ValidationError("دقت پول طرح باید عدد صحیح باشد.")
    locked_corrects = None
    if locked.record_kind == StatutoryRecordKind.ORIGINAL:
        if corrects is not None:
            raise ValidationError("خروجی اصلی سابقه اصلاح ندارد.")
        series_id, revision = None, 1
    else:
        if corrects is None:
            raise ValidationError("خروجی اصلاحی/ابطالی باید سابقه قبلی را مشخص کند.")
        try:
            locked_corrects = StatutoryOutput.objects.select_for_update().get(
                pk=corrects.pk, organization=organization
            )
        except StatutoryOutput.DoesNotExist as exc:
            raise PermissionDenied("خروجی قبلی متعلق به این Tenant نیست.") from exc
        if locked.corrects_id != locked_corrects.calculation_id:
            raise ValidationError("lineage خروجی و محاسبه مقرراتی هم‌خوان نیست.")
        if locked_corrects.successors.exists():
            raise ValidationError("برای خروجی قبلی جانشین ثبت شده است.")
        series_id, revision = locked_corrects.series_id, locked_corrects.revision + 1
    records = []
    identity_evidence_ids: list[str] = []
    employer_identity = (
        StatutoryIdentityEvidence.objects.filter(
            organization=organization,
            employee__isnull=True,
            subject=StatutoryIdentitySubject.EMPLOYER,
            kind=locked.kind,
            schema_version=schema,
            effective_from__lte=locked.effective_on,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=locked.effective_on))
        .order_by("-effective_from", "-version")
        .first()
    )
    employer_identifiers = employer_identity.identifiers if employer_identity else {}
    if employer_identity:
        identity_evidence_ids.append(str(employer_identity.pk))
    available_fields = {
        "output_identifier",
        "schema_identifier",
        "run_code",
        "period_start",
        "period_end",
        "currency",
        "employee_number",
        "employee_first_name",
        "employee_last_name",
        "basis_amount",
        "employee_amount",
        "employer_amount",
        "other_amount",
        "total_amount",
        "work_days",
    }
    available_fields.update(official_identifiers)
    unknown = sorted(set(mapping.values()) - available_fields)
    if unknown:
        raise ValidationError("نگاشت طرح به داده ناشناخته اشاره دارد: " + ", ".join(unknown))
    for result in locked.employee_results.select_related(
        "run_employee__employee"
    ).all():
        employee = result.run_employee.employee
        employee_identity = (
            StatutoryIdentityEvidence.objects.filter(
                organization=organization,
                employee=employee,
                subject=StatutoryIdentitySubject.EMPLOYEE,
                kind=locked.kind,
                schema_version=schema,
                effective_from__lte=locked.effective_on,
            )
            .filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gt=locked.effective_on)
            )
            .order_by("-effective_from", "-version")
            .first()
        )
        employee_identifiers = employee_identity.identifiers if employee_identity else {}
        duplicate_identifiers = set(employer_identifiers) & set(employee_identifiers)
        if duplicate_identifiers:
            raise ValidationError("دامنه شناسه رسمی کارفرما و کارمند مبهم است.")
        identity_values = {**employer_identifiers, **employee_identifiers}
        missing_identifiers = sorted(set(official_identifiers) - set(identity_values))
        if missing_identifiers:
            raise ValidationError(
                "شاهد شناسه رسمی مؤثر موجود نیست: " + ", ".join(missing_identifiers)
            )
        if employee_identity:
            identity_evidence_ids.append(str(employee_identity.pk))
        facts = {
            "output_identifier": output_identifier.strip(),
            "schema_identifier": parameters["schema_identifier"],
            "run_code": locked.run.code,
            "period_start": locked.run.period.starts_on.isoformat(),
            "period_end": locked.run.period.ends_on.isoformat(),
            "currency": locked.currency,
            "employee_number": employee.employee_number,
            "employee_first_name": employee.first_name,
            "employee_last_name": employee.last_name,
            "basis_amount": _serialized_money(result.basis_amount, scale),
            "employee_amount": _serialized_money(result.employee_amount, scale),
            "employer_amount": _serialized_money(result.employer_amount, scale),
            "other_amount": _serialized_money(result.other_amount, scale),
            "total_amount": _serialized_money(
                result.employee_amount + result.employer_amount + result.other_amount,
                scale,
            ),
            "work_days": None if result.work_days is None else str(result.work_days),
            **identity_values,
        }
        record = {external: facts[internal] for external, internal in mapping.items()}
        missing = [key for key in required if record.get(key) in {None, ""}]
        if missing:
            raise ValidationError("فیلد الزامی خروجی فاقد مقدار است: " + ", ".join(missing))
        records.append(record)
    payload = {
        "schema_identifier": parameters["schema_identifier"],
        "official_identifiers": official_identifiers,
        "encoding": parameters["encoding"],
        "record_kind": locked.record_kind,
        "records": records,
    }
    output = StatutoryOutput(
        organization=organization,
        calculation=locked,
        schema_version=schema,
        output_identifier=output_identifier.strip(),
        revision=revision,
        record_kind=locked.record_kind,
        corrects=locked_corrects,
        schema_identifier=parameters["schema_identifier"],
        schema_snapshot={
            "policy_version_id": str(schema.pk),
            "version": schema.version,
            "source_ids": [str(value) for value in schema.sources.values_list("pk", flat=True)],
            "parameters": parameters,
            "identity_evidence_ids": sorted(set(identity_evidence_ids)),
        },
        payload=payload,
        content_digest=_digest(payload),
        generated_by=actor,
        generated_at=timezone.now(),
    )
    if series_id is not None:
        output.series_id = series_id
    output.save()
    calculation_total = locked.employee_amount + locked.employer_amount + locked.other_amount
    output_total = sum(
        (
            result.employee_amount + result.employer_amount + result.other_amount
            for result in locked.employee_results.all()
        ),
        Decimal(0),
    )
    difference = output_total - calculation_total
    StatutoryReconciliation.objects.create(
        organization=organization,
        output=output,
        calculation_total=calculation_total,
        output_total=output_total,
        difference=difference,
        status=(
            StatutoryReconciliationStatus.MATCHED
            if difference == 0
            else StatutoryReconciliationStatus.EXCEPTION
        ),
        evidence={
            "calculation_digest": locked.content_digest,
            "output_digest": output.content_digest,
            "employee_count": len(records),
        },
        reconciled_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_OUTPUT_GENERATED,
        entity_type="payroll.StatutoryOutput",
        entity_id=output.pk,
        organization=organization,
        actor=actor,
        metadata={
            "calculation_id": str(locked.pk),
            "schema_version_id": str(schema.pk),
            "digest": output.content_digest,
        },
    )
    return output


@transaction.atomic
def record_export_evidence(
    *,
    organization: Organization,
    actor: User,
    output: StatutoryOutput,
    idempotency_key: str,
    correlation_id: str,
    status: str,
    artifact_name: str,
    provider_reference: str = "",
    error_code: str = "",
    error_message: str = "",
    retry_of: StatutoryExportEvidence | None = None,
) -> StatutoryExportEvidence:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_STATUTORY_EXPORT,
    )
    try:
        locked_output = StatutoryOutput.objects.select_for_update().get(
            pk=output.pk, organization=organization
        )
    except StatutoryOutput.DoesNotExist as exc:
        raise PermissionDenied("خروجی متعلق به این Tenant نیست.") from exc
    if status not in StatutoryExportStatus.values:
        raise ValidationError("وضعیت شاهد خروجی معتبر نیست.")
    existing = StatutoryExportEvidence.objects.filter(
        organization=organization, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.output_id != locked_output.pk:
            raise ValidationError("کلید idempotency برای خروجی دیگری استفاده شده است.")
        return existing
    locked_retry = None
    if retry_of is not None:
        try:
            locked_retry = StatutoryExportEvidence.objects.select_for_update().get(
                pk=retry_of.pk, organization=organization, output=locked_output
            )
        except StatutoryExportEvidence.DoesNotExist as exc:
            raise PermissionDenied("شاهد تلاش قبلی متعلق به این Tenant نیست.") from exc
        if not locked_retry.resolutions.filter(action="retry_authorized").exists():
            raise ValidationError("تلاش مجدد به تعیین تکلیف انسانی نیاز دارد.")
    attempt = (
        locked_output.export_evidence.order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
        or 0
    ) + 1
    artifact_snapshot = {
        "output_id": str(locked_output.pk),
        "schema_identifier": locked_output.schema_identifier,
        "encoding": locked_output.payload.get("encoding"),
        "payload": locked_output.payload,
    }
    evidence = StatutoryExportEvidence.objects.create(
        organization=organization,
        output=locked_output,
        retry_of=locked_retry,
        attempt_number=attempt,
        idempotency_key=idempotency_key.strip(),
        correlation_id=correlation_id.strip(),
        status=status,
        artifact_name=artifact_name.strip(),
        artifact_media_type="application/json",
        artifact_digest=_digest(artifact_snapshot),
        artifact_snapshot=artifact_snapshot,
        provider_reference=provider_reference.strip(),
        error_code=error_code.strip(),
        error_message=error_message.strip(),
        recorded_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_EXPORT_RECORDED,
        entity_type="payroll.StatutoryExportEvidence",
        entity_id=evidence.pk,
        organization=organization,
        actor=actor,
        metadata={
            "output_id": str(locked_output.pk),
            "attempt": attempt,
            "status": status,
            "artifact_digest": evidence.artifact_digest,
        },
    )
    return evidence


@transaction.atomic
def resolve_export_evidence(
    *,
    organization: Organization,
    actor: User,
    evidence: StatutoryExportEvidence,
    action: str,
    note: str,
) -> StatutorySubmissionResolution:
    _require(
        actor=actor,
        organization=organization,
        permission=BusinessPermissionCode.PAYROLL_STATUTORY_CORRECT,
    )
    try:
        locked = StatutoryExportEvidence.objects.select_for_update().get(
            pk=evidence.pk, organization=organization
        )
    except StatutoryExportEvidence.DoesNotExist as exc:
        raise PermissionDenied("شاهد خروجی متعلق به این Tenant نیست.") from exc
    resolution = StatutorySubmissionResolution.objects.create(
        organization=organization,
        export_evidence=locked,
        action=action,
        note=note.strip(),
        resolved_by=actor,
    )
    record_audit_event(
        action=AuditAction.PAYROLL_STATUTORY_RESOLVED,
        entity_type="payroll.StatutorySubmissionResolution",
        entity_id=resolution.pk,
        organization=organization,
        actor=actor,
        metadata={"export_evidence_id": str(locked.pk), "action": action},
    )
    return resolution
