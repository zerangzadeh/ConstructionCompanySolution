"""Governed indexation construction; no official rule or adapter ships here.

Adapters are trusted deployed code, never tenant expressions. Activation requires
an independently verified approval receipt bound to the complete request. Results
are billing snapshots only; no posting, claim adjustment or settlement occurs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.organizations.authorization import require_business_permission
from apps.organizations.models import BusinessPermissionCode, Organization

from .models import IndexationCalculation, IndexationRuleVersion

SPECIFICATION_FIELDS = frozenset(
    {
        "measurement_basis",
        "index_source",
        "formula_reference",
        "rounding_policy",
        "adjustment_target",
        "evidence_reference",
    }
)
INPUT_FIELDS = frozenset({"base_period", "current_period", "indexes", "values"})


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _json(value: Any, depth: int = 0) -> None:
    # Decimal quantities must be explicit strings; binary floats are forbidden.
    if depth > 12:
        raise ValidationError("ساختار ورودی بیش از حد پیچیده است.")
    if isinstance(value, dict) and value:
        if not all(_text(k) for k in value):
            raise ValidationError("کلید ورودی معتبر نیست.")
        for v in value.values():
            _json(v, depth + 1)
    elif isinstance(value, list) and value:
        for v in value:
            _json(v, depth + 1)
    elif not _text(value):
        raise ValidationError("مقادیر صریح متنی لازم است؛ عدد اعشاری دودویی مجاز نیست.")


def digest(value: dict[str, Any]) -> str:
    _json(value)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    if len(encoded.encode()) > 100_000:
        raise ValidationError("اندازه تصویر ورودی مجاز نیست.")
    return hashlib.sha256(encoded.encode()).hexdigest()


def validate_specification(specification: dict[str, str]) -> None:
    if (
        not isinstance(specification, dict)
        or set(specification) != SPECIFICATION_FIELDS
    ):
        raise ValidationError("تمام ارجاعات صریح قانون لازم است.")
    if not all(_text(v) for v in specification.values()):
        raise ValidationError("سیاست پیش‌فرض یا خالی مجاز نیست.")


def validate_inputs(inputs: dict[str, Any]) -> None:
    if (
        not isinstance(inputs, dict)
        or set(inputs) != INPUT_FIELDS
        or not _text(inputs["base_period"])
        or not _text(inputs["current_period"])
        or not isinstance(inputs["indexes"], dict)
        or not inputs["indexes"]
        or not isinstance(inputs["values"], dict)
        or not inputs["values"]
    ):
        raise ValidationError("دوره‌ها، شاخص‌ها و مقادیر صریح لازم است.")
    for index in inputs["indexes"].values():
        if (
            not isinstance(index, dict)
            or set(index)
            != {
                "source_reference",
                "source_version",
                "evidence_reference",
                "period",
                "value",
            }
            or not all(_text(v) for v in index.values())
        ):
            raise ValidationError("منبع، نسخه، مدرک، دوره و مقدار شاخص لازم است.")
        try:
            if not Decimal(index["value"]).is_finite():
                raise ValueError
        except (ArithmeticError, ValueError) as exc:
            raise ValidationError("مقدار شاخص معتبر نیست.") from exc
    digest(inputs)


def rule_snapshot(rule: IndexationRuleVersion) -> dict[str, Any]:
    return {
        "organization": str(rule.organization_id),
        "contract": str(rule.contract_id),
        "code": rule.code,
        "version": str(rule.version),
        "effective_from": rule.effective_from.isoformat(),
        "effective_to": rule.effective_to.isoformat(),
        "adapter_key": rule.adapter_key,
        "specification": rule.specification,
    }


def rule_digest(rule: IndexationRuleVersion) -> str:
    return digest(rule_snapshot(rule))


@dataclass(frozen=True)
class ApprovalReceipt:
    rule_sha256: str
    request_sha256: str
    source_snapshot_sha256: str
    approval_reference: str
    evidence_reference: str
    adapter_version: str


@dataclass(frozen=True)
class IndexationAdapter:
    # resolve_approval must verify source authenticity, contract applicability,
    # periods, effective dates, formula, rounding and operation eligibility.
    resolve_approval: Callable[[dict[str, Any]], ApprovalReceipt | None]
    calculate: Callable[[dict[str, Any]], Decimal]


ADAPTERS: dict[str, IndexationAdapter] = {}


def register_adapter(key: str, adapter: IndexationAdapter) -> None:
    if not _text(key) or key in ADAPTERS or not isinstance(adapter, IndexationAdapter):
        raise ValueError("شناسه یکتای تطبیق‌دهنده لازم است.")
    ADAPTERS[key] = adapter


def _contract(
    *,
    actor: User,
    organization: Organization,
    contract: Contract,
    permission: BusinessPermissionCode,
) -> Contract:
    # Refresh/lock tenant state; do not trust a caller's stale Organization object.
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    try:
        locked = (
            Contract.objects.select_for_update()
            .select_related("project")
            .get(pk=contract.pk, organization=organization, deleted_at__isnull=True)
        )
    except Contract.DoesNotExist as exc:
        raise PermissionDenied("قرارداد مجاز یافت نشد.") from exc
    require_business_permission(
        user=actor,
        organization=organization,
        permission=BusinessPermissionCode.CONTRACT_TERMS_MANAGE,
        project=locked.project,
        message="اجازه مدیریت شرایط قرارداد را ندارید.",
    )
    require_business_permission(
        user=actor,
        organization=organization,
        permission=permission,
        project=locked.project,
        message="مجوز عملیات تعدیل را ندارید.",
    )
    return locked


@transaction.atomic
def stage_rule(
    *,
    actor: User,
    organization: Organization,
    contract: Contract,
    code: str,
    effective_from: date,
    effective_to: date,
    adapter_key: str,
    specification: dict[str, str],
    reason: str,
) -> IndexationRuleVersion:
    locked = _contract(
        actor=actor,
        organization=organization,
        contract=contract,
        permission=BusinessPermissionCode.INDEXATION_RULES_MANAGE,
    )
    version = (
        IndexationRuleVersion.objects.filter(contract=locked, code=code).aggregate(
            v=Max("version")
        )["v"]
        or 0
    ) + 1
    rule = IndexationRuleVersion(
        organization_id=locked.organization_id,
        contract=locked,
        actor=actor,
        code=code,
        version=version,
        effective_from=effective_from,
        effective_to=effective_to,
        adapter_key=adapter_key,
        specification=specification,
        reason=reason,
    )
    rule.sha256 = rule_digest(rule)
    rule.save()
    return rule


def validate_calculation_snapshot(record: IndexationCalculation) -> None:
    snapshot = record.snapshot
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "request",
        "approval",
        "result",
    }:
        raise ValidationError("تصویر محاسبه کامل نیست.")
    request = snapshot["request"]
    if not isinstance(request, dict) or set(request) != {
        "rule",
        "rule_id",
        "rule_sha256",
        "calculation_date",
        "operation",
        "inputs",
        "prior_id",
        "prior_sha256",
        "reason",
    }:
        raise ValidationError("درخواست محاسبه کامل نیست.")
    if (
        request["rule"] != rule_snapshot(record.rule)
        or request["rule_id"] != str(record.rule_id)
        or request["rule_sha256"] != record.rule.sha256
        or request["operation"] != record.operation
        or request["calculation_date"] != record.calculation_date.isoformat()
        or request["reason"] != record.reason
        or request["prior_id"] != (str(record.prior_id) if record.prior_id else "NONE")
        or request["prior_sha256"]
        != (record.prior.sha256 if record.prior_id else "NONE")
        or digest(request) != record.request_sha256
    ):
        raise ValidationError("هویت منبع محاسبه سازگار نیست.")
    inputs = request["inputs"]
    validate_inputs(inputs)
    try:
        receipt = ApprovalReceipt(**snapshot["approval"])
        result = snapshot["result"]
        if not _text(result) or not Decimal(result).is_finite():
            raise ValueError
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise ValidationError("مدرک تأیید و نتیجه معتبر لازم است.") from exc
    _validate_receipt(receipt, record.rule, request)
    if (
        not record.rule.effective_from
        <= record.calculation_date
        <= record.rule.effective_to
    ):
        raise ValidationError("تاریخ محاسبه خارج از بازه اثر است.")


def _validate_receipt(
    receipt: ApprovalReceipt | None,
    rule: IndexationRuleVersion,
    request: dict[str, Any],
) -> None:
    if (
        not isinstance(receipt, ApprovalReceipt)
        or not all(_text(v) for v in asdict(receipt).values())
        or receipt.rule_sha256 != rule.sha256
        or receipt.request_sha256 != digest(request)
        or receipt.source_snapshot_sha256 != digest(request["inputs"]["indexes"])
    ):
        raise ValidationError("سیاست و منبع رسمی تأییدشده برای محاسبه وجود ندارد.")


@transaction.atomic
def calculate(
    *,
    actor: User,
    organization: Organization,
    contract: Contract,
    rule: IndexationRuleVersion,
    calculation_date: date,
    inputs: dict[str, Any],
    idempotency_key: str,
    reason: str,
    operation: str = "calculate",
    prior: IndexationCalculation | None = None,
) -> IndexationCalculation:
    locked = _contract(
        actor=actor,
        organization=organization,
        contract=contract,
        permission=BusinessPermissionCode.INDEXATION_CALCULATE
        if operation == "calculate"
        else BusinessPermissionCode.INDEXATION_CORRECT,
    )
    if not _text(idempotency_key) or not _text(reason):
        raise ValidationError("کلید تکرارپذیری و دلیل لازم است.")
    try:
        rule = IndexationRuleVersion.objects.get(pk=rule.pk, contract=locked)
        if prior is not None:
            prior = IndexationCalculation.objects.select_for_update().get(
                pk=prior.pk, contract=locked
            )
    except (
        IndexationRuleVersion.DoesNotExist,
        IndexationCalculation.DoesNotExist,
    ) as exc:
        raise PermissionDenied("منبع مجاز یافت نشد.") from exc
    rule.full_clean()
    if (
        operation not in {"calculate", "correct", "reverse"}
        or ((operation == "calculate") != (prior is None))
        or (prior is not None and prior.operation == "reverse")
    ):
        raise ValidationError("عملیات و سابقه معتبر لازم است.")
    if not rule.effective_from <= calculation_date <= rule.effective_to:
        raise ValidationError("قانون در تاریخ محاسبه مؤثر نیست.")
    validate_inputs(inputs)
    request = {
        "rule": rule_snapshot(rule),
        "rule_id": str(rule.pk),
        "rule_sha256": rule.sha256,
        "calculation_date": calculation_date.isoformat(),
        "operation": operation,
        "inputs": inputs,
        "prior_id": str(prior.pk) if prior else "NONE",
        "prior_sha256": prior.sha256 if prior else "NONE",
        "reason": reason,
    }
    request_hash = digest(request)
    existing = IndexationCalculation.objects.filter(
        contract=locked, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.request_sha256 != request_hash:
            raise ValidationError(
                "کلید تکرارپذیری قبلاً برای ورودی متفاوت مصرف شده است."
            )
        return existing
    if prior and IndexationCalculation.objects.filter(prior=prior).exists():
        raise ValidationError("این سابقه قبلاً اصلاح یا برگشت شده است.")
    if prior:
        prior.full_clean()
    adapter = ADAPTERS.get(rule.adapter_key)
    if adapter is None:
        raise ValidationError("سیاست تعدیل فعال نیست؛ محاسبه مجاز نیست.")
    # Pass copies to trusted adapters so their mutation cannot corrupt pinned input.
    receipt = adapter.resolve_approval(json.loads(json.dumps(request)))
    _validate_receipt(receipt, rule, request)
    result = adapter.calculate(json.loads(json.dumps(request)))
    if not isinstance(result, Decimal) or not result.is_finite():
        raise ValidationError("نتیجه اعشاری معتبر لازم است.")
    snapshot = {"request": request, "approval": asdict(receipt), "result": str(result)}
    record = IndexationCalculation(
        organization_id=locked.organization_id,
        contract=locked,
        actor=actor,
        rule=rule,
        calculation_date=calculation_date,
        idempotency_key=idempotency_key,
        reason=reason,
        operation=operation,
        prior=prior,
        request_sha256=request_hash,
        snapshot=snapshot,
        sha256=digest(snapshot),
    )
    record.save()
    return record
