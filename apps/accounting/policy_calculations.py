"""Typed, version-pinned monetary policy resolution and rounding semantics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError

from apps.organizations.models import Organization, PlatformPolicyVersion
from apps.organizations.policy_services import resolve_active_tenant_policy
from apps.organizations.policy_specs import (
    ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    ACCOUNTING_ROUNDING_POLICY_CODE,
    validate_policy_for_consumer,
)

ACCOUNTING_JOURNAL_SUBMIT_CONSUMER = "accounting.journal.submit"


@dataclass(frozen=True)
class MoneyPrecisionPolicy:
    money_scale: int
    intermediate_calculation_scale: int
    preserve_unrounded_intermediates: bool
    version: PlatformPolicyVersion


@dataclass(frozen=True)
class AccountingRoundingPolicy:
    method: str
    output_boundary: str
    tie_behavior: str
    version: PlatformPolicyVersion


def money_precision_policy_from_version(
    version: PlatformPolicyVersion,
) -> MoneyPrecisionPolicy:
    validate_policy_for_consumer(
        policy_version=version,
        consumer=ACCOUNTING_JOURNAL_SUBMIT_CONSUMER,
        expected_policy_code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    )
    return MoneyPrecisionPolicy(
        money_scale=version.parameters["money_scale"],
        intermediate_calculation_scale=version.parameters[
            "intermediate_calculation_scale"
        ],
        preserve_unrounded_intermediates=version.parameters[
            "preserve_unrounded_intermediates"
        ],
        version=version,
    )


def accounting_rounding_policy_from_version(
    version: PlatformPolicyVersion,
) -> AccountingRoundingPolicy:
    validate_policy_for_consumer(
        policy_version=version,
        consumer=ACCOUNTING_JOURNAL_SUBMIT_CONSUMER,
        expected_policy_code=ACCOUNTING_ROUNDING_POLICY_CODE,
    )
    return AccountingRoundingPolicy(
        method=version.parameters["rounding_method"],
        output_boundary=version.parameters["output_boundary"],
        tie_behavior=version.parameters["tie_behavior"],
        version=version,
    )


def resolve_accounting_posting_policies(
    *, organization: Organization
) -> tuple[MoneyPrecisionPolicy, AccountingRoundingPolicy]:
    """Resolve both exact policy contracts; missing/invalid configuration fails closed."""

    precision_version = resolve_active_tenant_policy(
        organization=organization,
        policy_code=ACCOUNTING_MONEY_PRECISION_POLICY_CODE,
    )
    rounding_version = resolve_active_tenant_policy(
        organization=organization,
        policy_code=ACCOUNTING_ROUNDING_POLICY_CODE,
    )
    return (
        money_precision_policy_from_version(precision_version),
        accounting_rounding_policy_from_version(rounding_version),
    )


def preserve_intermediate_calculation(
    value: Decimal, *, precision: MoneyPrecisionPolicy
) -> Decimal:
    """Keep an intermediate result exact until a declared output boundary.

    The configured six-place intermediate scale is a versioned calculation contract,
    not permission to silently quantize each operation. Future persisted
    intermediate outputs must declare their own boundary before quantization.
    """

    _require_finite_decimal(value)
    if not precision.preserve_unrounded_intermediates:
        raise ValidationError("سیاست دقت، نگهداری مقدار میانی بدون گردکردن را مجاز نمی‌داند.")
    return value


def round_final_monetary_amount(
    value: Decimal,
    *,
    precision: MoneyPrecisionPolicy,
    rounding: AccountingRoundingPolicy,
) -> Decimal:
    """Round once at the approved final journal-line monetary boundary."""

    _require_finite_decimal(value)
    if rounding.output_boundary != "final_monetary_line":
        raise ValidationError("مرز خروجی سیاست گردکردن برای ردیف مالی معتبر نیست.")
    if rounding.method != "ROUND_HALF_UP" or rounding.tie_behavior != "ROUND_HALF_UP":
        raise ValidationError("روش یا رفتار tie سیاست گردکردن معتبر نیست.")
    quantum = Decimal(1).scaleb(-precision.money_scale)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def require_final_monetary_amount(
    value: Decimal,
    *,
    precision: MoneyPrecisionPolicy,
    rounding: AccountingRoundingPolicy,
) -> None:
    """Reject a manual/opening final line that has not reached the policy boundary."""

    rounded = round_final_monetary_amount(
        value, precision=precision, rounding=rounding
    )
    if value != rounded:
        raise ValidationError(
            "مبلغ نهایی ردیف با مقیاس پول سیاست سازگار نیست؛ "
            "گردکردن ضمنی در ثبت دستی/افتتاحیه مجاز نیست."
        )


def _require_finite_decimal(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValidationError("مقدار حسابداری باید Decimal متناهی باشد.")
